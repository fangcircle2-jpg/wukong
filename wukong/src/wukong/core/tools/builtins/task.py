"""Task tool - Launch subagent to execute independent tasks."""

import asyncio
import copy
import json
import logging
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from wukong.core.tools.base import Tool, ToolResult
from wukong.core.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


def _load_description() -> str:
    """Load tool description from text file."""
    desc_file = Path(__file__).parent / "task.txt"
    if desc_file.exists():
        return desc_file.read_text(encoding="utf-8").strip()
    return "Launch a subagent to execute an independent task."


class TaskParams(BaseModel):
    """Parameters for task tool."""
    
    agent: str = Field(
        description="Subagent name to invoke (e.g., 'general', 'explore')"
    )
    prompt: str = Field(
        description="Task description for the subagent to execute"
    )
    model: str | None = Field(
        default=None,
        description="Optional model override for the subagent"
    )
    timeout: int = Field(
        default=300000,
        description="Maximum execution time in milliseconds (default: 5 minutes)"
    )


class ToolCallSummary(BaseModel):
    """Summary of a single tool call made by the subagent."""
    
    id: str
    tool: str
    status: str  # "completed", "failed", "running"
    title: str | None = None
    args: dict[str, Any] | None = None


class TaskMetadata(BaseModel):
    """Metadata returned by the task tool."""
    
    session_id: str
    summary: list[ToolCallSummary]


class TaskTool(Tool):
    """Tool to launch subagents for independent task execution.
    
    The Task tool allows the main agent to delegate complex tasks
    to specialized subagents. Each subagent runs in its own session
    and can use a configured set of tools.
    
    Key features:
    - Subagent results are not shown directly to the user
    - Main agent must summarize and present results
    - Supports parallel task execution via multiple calls
    - Subagent session is linked to parent session
    
    Data flow:
    User request → Main Agent → Task Tool → Child Session → 
    Task Result → Main Agent Summary → User
    """
    
    name = "task"
    description = _load_description()
    parameters = TaskParams
    context_keys = ["session_manager", "parent_session", "llm", "tool_registry", "on_progress"]
    
    MAX_NESTING_DEPTH = 3
    
    async def execute(
        self,
        *,
        workspace_dir: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        """Execute a task using a subagent.
        
        Args:
            workspace_dir: Workspace directory path.
            **kwargs: Tool parameters and injected dependencies:
                - agent: Subagent name
                - prompt: Task description
                - model: Optional model override
                - timeout: Execution timeout in ms
                - session_manager: SessionManager instance (injected)
                - parent_session: Parent Session instance (injected)
                - llm: LLM instance (injected)
                - tool_registry: ToolRegistry instance (injected)
            
        Returns:
            ToolResult with task output and metadata.
        """
        # Validate parameters
        try:
            params = self.validate_params(**kwargs)
        except Exception as e:
            return ToolResult.fail(f"Invalid parameters: {e}")
        
        # Get injected dependencies
        session_manager = kwargs.get("session_manager")
        parent_session = kwargs.get("parent_session")
        llm = kwargs.get("llm")
        tool_registry = kwargs.get("tool_registry")
        
        # Validate dependencies
        if session_manager is None:
            return ToolResult.fail("session_manager not provided")
        if parent_session is None:
            return ToolResult.fail("parent_session not provided")
        if llm is None:
            return ToolResult.fail("llm not provided")
        
        # Load agent configuration
        from wukong.core.agent.config import AgentConfigLoader
        
        config_loader = AgentConfigLoader(workspace_dir)
        agent_config = config_loader.load(params.agent)
        
        if agent_config is None:
            available = config_loader.list_agents()
            return ToolResult.fail(
                f"Agent '{params.agent}' not found. "
                f"Available agents: {', '.join(available)}"
            )
        
        if not agent_config.is_subagent():
            return ToolResult.fail(
                f"Agent '{params.agent}' is not a subagent (mode: {agent_config.mode})"
            )
        
        # Check nesting depth to prevent deep recursion
        depth = self._get_nesting_depth(parent_session, session_manager)
        if depth >= self.MAX_NESTING_DEPTH:
            return ToolResult.fail(
                f"Maximum subagent nesting depth ({self.MAX_NESTING_DEPTH}) exceeded. "
                f"Current depth: {depth}"
            )
        
        # Create child session
        task_title = params.prompt[:50] + ("..." if len(params.prompt) > 50 else "")
        child_session = session_manager.create_session(
            title=f"[Task] {task_title}",
            model_name=params.model or agent_config.model,
        )
        child_session.parent_session_id = parent_session.session_id
        session_manager.save_session(child_session)
        
        logger.info(
            f"Created child session {child_session.session_id} "
            f"for agent '{params.agent}'"
        )
        
        try:
            # Create filtered tool registry for subagent
            filtered_registry = self._create_filtered_registry(
                agent_config.tools,
                tool_registry,
            )
            
            # Prepare child LLM with optional model/temperature overrides
            child_llm = self._create_child_llm(
                llm,
                model_override=params.model or agent_config.model,
                temperature_override=agent_config.temperature,
            )
            
            # Create child AgentLoop
            from wukong.core.agent.loop import AgentLoop
            from wukong.core.prompt import PromptBuilder
            
            child_agent = AgentLoop(
                llm=child_llm,
                session=child_session,
                session_manager=session_manager,
                tool_registry=filtered_registry,
                max_iterations=agent_config.max_steps,
            )
            
            # Override system prompt if agent config has one
            if agent_config.prompt:
                child_agent.prompt_builder = PromptBuilder(
                    workspace_dir=child_session.workspace_directory,
                    mode=child_session.mode,
                    provider=child_agent.provider,
                    custom_system_prompt=agent_config.prompt,
                )
            
            # Run subagent with timeout, reporting progress
            timeout_seconds = params.timeout / 1000
            timed_out = False
            on_progress = kwargs.get("on_progress")
            
            try:
                async with asyncio.timeout(timeout_seconds):
                    async for chunk in self._consume_stream(child_agent.run(params.prompt)):
                        self._report_progress(
                            on_progress, params.agent, task_title, chunk
                        )
            except asyncio.TimeoutError:
                timed_out = True
                logger.warning(
                    f"Task timed out after {params.timeout}ms "
                    f"(session: {child_session.session_id})"
                )
                child_agent.save()
            
            child_agent.save()
            
            # Load history from session to extract results
            history_items = session_manager.load_history_items(child_session.session_id)
            
            final_output = self._extract_final_output(history_items)
            summary = self._extract_tool_summary(history_items)
            
            if timed_out:
                final_output += (
                    f"\n\n[Task timed out after {timeout_seconds:.0f}s. "
                    f"Results above are partial.]"
                )
            
            metadata = TaskMetadata(
                session_id=child_session.session_id,
                summary=summary,
            )
            
            output = self._format_output(
                title=task_title,
                metadata=metadata,
                final_output=final_output,
            )
            
            title_prefix = "Task (timed out)" if timed_out else "Task"
            
            return ToolResult.ok(
                output,
                title=f"{title_prefix}: {task_title}",
                agent=params.agent,
                session_id=child_session.session_id,
                tool_calls=len(summary),
                timed_out=timed_out,
            )
            
        except Exception as e:
            logger.error(
                f"Task execution failed (session: {child_session.session_id}): {e}",
                exc_info=True,
            )
            
            # Try to extract partial results
            try:
                history_items = session_manager.load_history_items(child_session.session_id)
                final_output = self._extract_final_output(history_items)
                summary = self._extract_tool_summary(history_items)
                
                if final_output or summary:
                    metadata = TaskMetadata(
                        session_id=child_session.session_id,
                        summary=summary,
                    )
                    output = self._format_output(
                        title=task_title,
                        metadata=metadata,
                        final_output=final_output + f"\n\n[Task interrupted: {e}]",
                    )
                    return ToolResult.ok(
                        output,
                        title=f"Task (partial): {task_title}",
                        error=str(e),
                    )
            except Exception:
                pass
            
            return ToolResult.fail(f"Task execution failed: {e}")
    
    async def _consume_stream(self, stream):
        """Consume an async generator stream.
        
        This is a helper to make the stream compatible with asyncio.wait_for.
        """
        async for item in stream:
            yield item
    
    def _report_progress(
        self,
        on_progress: Any | None,
        agent_name: str,
        task_title: str,
        chunk: Any,
    ) -> None:
        """Report subagent progress via callback and logging.
        
        Extracts meaningful events from LLM response chunks and reports
        them for real-time display:
        - tool_call: when the LLM requests a tool (shown as running/orange)
        - tool_done: when a tool result arrives (updates to completed/green)
        - text: when the LLM produces text content
        
        For batch tool results, parses sub-tool information for three-level
        tree display.
        
        Errors in the callback are caught and logged to avoid disrupting
        task execution.
        
        Args:
            on_progress: Optional callback, signature: (event: dict) -> None
            agent_name: Name of the subagent.
            task_title: Short task title.
            chunk: LLMResponse chunk from subagent stream.
        """
        try:
            content = getattr(chunk, "content", None)
            tool_calls = getattr(chunk, "tool_calls", None)
            
            if tool_calls:
                for tc in tool_calls:
                    func = getattr(tc, "function", None)
                    tool_name = getattr(func, "name", "") if func else ""
                    if tool_name:
                        raw_args = getattr(func, "arguments", "") if func else ""
                        try:
                            import json as _json
                            tool_args = _json.loads(raw_args) if raw_args else {}
                        except (ValueError, TypeError):
                            tool_args = {}
                        
                        event = {
                            "type": "tool_call",
                            "agent": agent_name,
                            "task": task_title,
                            "tool": tool_name,
                            "args": tool_args,
                        }
                        logger.info(f"[Subagent:{agent_name}] Calling tool: {tool_name}")
                        if on_progress:
                            on_progress(event)
            
            if content and content.startswith("[Tool:"):
                self._report_tool_done(on_progress, agent_name, task_title, content)
                return
            
            if content and len(content.strip()) > 0:
                if on_progress:
                    on_progress({
                        "type": "text",
                        "agent": agent_name,
                        "task": task_title,
                        "content": content[:200],
                    })
        except Exception:
            logger.debug("Progress reporting failed", exc_info=True)
    
    def _report_tool_done(
        self,
        on_progress: Any | None,
        agent_name: str,
        task_title: str,
        content: str,
    ) -> None:
        """Parse a child agent tool result chunk and emit a tool_done event.
        
        Format: [Tool: name|success_flag|duration|args_json]\\nresult_content
        
        For batch tools, additionally parses sub-tool information from the
        result content and args to provide three-level display data.
        """
        import json as _json
        import re
        
        match = re.match(
            r'\[Tool: (\w+)\|([01])\|([\d.]+)\|(.*?)\]\n',
            content,
            re.DOTALL,
        )
        if not match or not on_progress:
            return
        
        tool_name = match.group(1)
        success = match.group(2) == "1"
        duration = float(match.group(3))
        try:
            args = _json.loads(match.group(4))
        except (ValueError, TypeError):
            args = {}
        
        result_content = content[match.end():]
        
        event: dict[str, Any] = {
            "type": "tool_done",
            "agent": agent_name,
            "task": task_title,
            "tool": tool_name,
            "success": success,
            "duration": duration,
            "args": args,
        }
        
        if tool_name == "batch":
            event["batch_items"] = self._parse_batch_sub_items(args, result_content)
        
        on_progress(event)
    
    @staticmethod
    def _parse_batch_sub_items(
        args: dict[str, Any],
        result_content: str,
    ) -> list[dict[str, Any]]:
        """Extract per-tool status from a batch result for three-level display.
        
        Returns a list of dicts with keys: name, args, success.
        """
        import re
        
        tool_calls = args.get("tool_calls", [])
        
        status_list: list[bool] = []
        for line in result_content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("[OK]"):
                status_list.append(True)
            elif stripped.startswith("[FAIL]"):
                status_list.append(False)
        
        items: list[dict[str, Any]] = []
        for i, tc in enumerate(tool_calls):
            if not isinstance(tc, dict):
                continue
            item_success = status_list[i] if i < len(status_list) else True
            items.append({
                "name": tc.get("name", "unknown"),
                "args": tc.get("arguments", {}),
                "success": item_success,
            })
        return items
    
    def _create_filtered_registry(
        self,
        allowed_tools: list[str],
        source_registry: ToolRegistry | None,
    ) -> ToolRegistry:
        """Create a filtered tool registry with only allowed tools.
        
        Args:
            allowed_tools: List of tool names to include.
            source_registry: Source registry to copy tools from.
            
        Returns:
            New ToolRegistry with only allowed tools.
        """
        from wukong.core.tools import get_registry
        
        if source_registry is None:
            source_registry = get_registry()
        
        filtered = ToolRegistry()
        
        for tool_name in allowed_tools:
            # Skip 'task' to prevent infinite recursion
            if tool_name == "task":
                logger.warning("Skipping 'task' tool in subagent to prevent recursion")
                continue
            
            tool = source_registry.get(tool_name)
            if tool is not None:
                filtered.register(tool)
            else:
                logger.warning(f"Tool '{tool_name}' not found in registry")
        
        return filtered
    
    def _create_child_llm(
        self,
        parent_llm: Any,
        model_override: str | None = None,
        temperature_override: float | None = None,
    ) -> Any:
        """Create a child LLM instance with optional overrides.
        
        Uses shallow copy to share the underlying client (API key, base_url)
        while allowing independent model/temperature settings.
        
        Args:
            parent_llm: Parent LLM instance to copy from.
            model_override: If set, use this model instead of parent's.
            temperature_override: If set, use this temperature instead of parent's.
            
        Returns:
            A new LLM instance (or the original if no overrides needed).
        """
        if model_override is None and temperature_override is None:
            return parent_llm
        
        child_llm = copy.copy(parent_llm)
        
        if model_override is not None:
            child_llm.model = model_override
            logger.info(f"Child LLM model override: {model_override}")
        
        if temperature_override is not None:
            child_llm.temperature = temperature_override
            logger.info(f"Child LLM temperature override: {temperature_override}")
        
        return child_llm
    
    def _get_nesting_depth(self, session: Any, session_manager: Any) -> int:
        """Calculate current nesting depth by walking the parent session chain.
        
        Args:
            session: Current session.
            session_manager: SessionManager for looking up parent sessions.
            
        Returns:
            Nesting depth (0 = top-level, 1 = first subagent, etc.)
        """
        depth = 0
        current = session
        
        while current and getattr(current, "parent_session_id", None):
            depth += 1
            if depth >= self.MAX_NESTING_DEPTH:
                break
            current = session_manager.get_session(current.parent_session_id)
        
        return depth
    
    def _extract_final_output(self, history_items: list) -> str:
        """Extract final output from the last assistant message.
        
        Args:
            history_items: List of HistoryItem from session.
            
        Returns:
            Content of the last assistant message, or empty string.
        """
        for item in reversed(history_items):
            if item.message.role == "assistant":
                return item.message.content or ""
        return ""
    
    def _extract_tool_summary(self, history_items: list) -> list[ToolCallSummary]:
        """Extract tool call summary from history.
        
        Args:
            history_items: List of HistoryItem from session.
            
        Returns:
            List of ToolCallSummary for all tool calls.
        """
        from wukong.core.session.models import ToolStatus
        
        summary = []
        
        for item in history_items:
            for state in item.tool_call_states:
                # Map status
                if state.status == ToolStatus.DONE:
                    status = "completed"
                elif state.status == ToolStatus.FAILED:
                    status = "failed"
                elif state.status == ToolStatus.CANCELLED:
                    status = "cancelled"
                else:
                    status = "running"
                
                # Generate title
                title = self._generate_tool_title(state)
                
                summary.append(ToolCallSummary(
                    id=state.tool_call_id,
                    tool=state.tool_name,
                    status=status,
                    title=title,
                    args=state.arguments if state.arguments else None,
                ))
        
        return summary
    
    def _generate_tool_title(self, state) -> str:
        """Generate a human-readable title for a tool call.
        
        Args:
            state: ToolCallState object.
            
        Returns:
            Short descriptive title.
        """
        args = state.arguments
        tool_name = state.tool_name
        
        # Generate title based on tool type
        if tool_name == "read_file":
            path = args.get("path", "file")
            # Get just the filename
            if "/" in path:
                path = path.split("/")[-1]
            elif "\\" in path:
                path = path.split("\\")[-1]
            return f"Read {path}"
        
        elif tool_name == "write_file":
            path = args.get("path", "file")
            if "/" in path:
                path = path.split("/")[-1]
            elif "\\" in path:
                path = path.split("\\")[-1]
            return f"Write {path}"
        
        elif tool_name == "grep":
            pattern = args.get("pattern", "")
            if len(pattern) > 20:
                pattern = pattern[:17] + "..."
            return f"Search '{pattern}'"
        
        elif tool_name == "glob":
            pattern = args.get("pattern", "")
            return f"Find {pattern}"
        
        elif tool_name == "bash":
            command = args.get("command", "")
            if len(command) > 30:
                command = command[:27] + "..."
            return f"Run: {command}"
        
        elif tool_name == "list_dir":
            path = args.get("path", ".")
            return f"List {path}"
        
        elif tool_name == "batch":
            invocations = args.get("invocations", [])
            return f"Batch ({len(invocations)} tools)"
        
        else:
            # Generic title
            return f"{tool_name}"
    
    def _format_output(
        self,
        title: str,
        metadata: TaskMetadata,
        final_output: str,
    ) -> str:
        """Format the task output with metadata.
        
        Args:
            title: Task title.
            metadata: Task metadata.
            final_output: Final output from subagent.
            
        Returns:
            Formatted output string.
        """
        metadata_json = json.dumps(
            metadata.model_dump(),
            ensure_ascii=False,
            indent=2,
        )
        
        return f"""<task_metadata>
{metadata_json}
</task_metadata>

{final_output}
"""
