"""
Agent Loop implementation.

The core orchestrator that manages LLM interactions, tool calls, and session persistence.
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, AsyncGenerator, List

from wukong.core.context import get_registry as get_context_registry
from wukong.core.context.base import ContextItem, ContextProviderError
from wukong.core.context.registry import ContextRegistry
from wukong.core.llm.base import BaseLLM
from wukong.core.llm.schema import ChatMessage, LLMResponse, ToolCall
from wukong.core.prompt import PromptBuilder
from wukong.core.session.history import ChatHistory
from wukong.core.session.manager import SessionManager
from wukong.core.session.models import HistoryItem, MessageMode, Session, ToolCallState, ToolStatus
from wukong.core.tools import get_registry as get_tool_registry
from wukong.core.tools.base import ToolResult
from wukong.core.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


@dataclass
class MentionInput:
    """Input from CLI's MentionParser.
    
    This is a simple data class to transfer mention information
    from CLI layer to Core layer without coupling to CLI's parser.
    """
    provider: str
    query: str


class AgentLoop:
    """
    Agent 核心循环。
    
    负责管理 LLM、Session 和工具调用之间的交互。
    采用 ReAct 模式进行推理和行动。
    
    Context 处理流程:
    - CLI 负责解析 @mentions (MentionParser)
    - CLI 传递 mentions 列表给 AgentLoop.run()
    - AgentLoop 调用 Registry 获取 context 内容
    
    Tool 处理流程:
    - AgentLoop 从 ToolRegistry 获取工具定义
    - LLM 返回 tool_calls 时，AgentLoop 执行工具
    - 工具结果作为 ChatMessage(role="tool") 发回 LLM
    - 循环直到 LLM 不再请求工具
    """
    
    # Default maximum tool call iterations to prevent infinite loops
    DEFAULT_MAX_ITERATIONS = 20
    
    def __init__(
        self, 
        llm: BaseLLM, 
        session: Session,
        session_manager: SessionManager,
        context_registry: ContextRegistry | None = None,
        tool_registry: ToolRegistry | None = None,
        provider: str = "anthropic",
        history_items: list[HistoryItem] | None = None,
        max_iterations: int | None = None,
        on_progress: Any | None = None,
        mcp_manager: Any | None = None,
    ):
        """Initialize AgentLoop.
        
        Args:
            llm: LLM backend instance
            session: Session instance to use
            session_manager: Session manager for persistence
            context_registry: Context provider registry. If None, uses global registry.
            tool_registry: Tool registry. If None, uses global registry.
            provider: LLM provider name (for prompt template selection)
            history_items: Optional list of history items. If None, starts with empty history.
                          Use session_manager.load_history_items() to load from storage.
            max_iterations: Maximum tool call iterations. If None, uses DEFAULT_MAX_ITERATIONS.
            on_progress: Optional callback for reporting tool progress events.
                        Signature: on_progress(event: dict) -> None
        """
        self.llm = llm
        self.session = session
        self.session_manager = session_manager
        self.provider = provider
        self._max_iterations = max_iterations or self.DEFAULT_MAX_ITERATIONS
        self._on_progress = on_progress
        
        # Create ChatHistory from provided items or empty
        self.chat_history = ChatHistory(items=history_items)
        
        # Create PromptBuilder for system prompt generation
        self.prompt_builder = PromptBuilder(
            workspace_dir=session.workspace_directory,
            mode=session.mode or MessageMode.NORMAL,
            provider=provider,
        )
        
        # Use provided context registry or global singleton
        self._context_registry = context_registry if context_registry is not None else get_context_registry()
        
        # Use provided tool registry or global singleton
        self._tool_registry = tool_registry if tool_registry is not None else get_tool_registry()
        
        # MCP manager for injecting into MCPToolWrapper at execution time
        self._mcp_manager = mcp_manager

        # Dirty flag: tracks if there are unsaved changes
        self._dirty = False
        
        # TODO: Inject PermissionManager in the future

    async def run(
        self, 
        query: str,
        mentions: list[MentionInput] | None = None,
    ) -> AsyncGenerator[LLMResponse, None]:
        """
        运行单次 Agent 交互。
        
        处理流程：
        1. 根据 mentions 获取 context (如果有)
        2. 记录用户消息（带 context）
        3. 获取工具定义
        4. 调用 LLM（流式）
        5. 处理响应（文本 + 工具调用）
        6. 如果有 tool_calls:
           - 执行工具
           - 添加工具结果到历史
           - 继续调用 LLM
        7. 循环直到 LLM 不再请求工具
        8. 记录助手消息
        9. 自动保存
        
        Args:
            query: Clean user query text (mentions already removed by CLI)
            mentions: List of parsed mentions from CLI (provider, query pairs)
            
        Yields:
            LLMResponse objects containing text chunks or tool calls
        """
        # 1. Begin new turn (enables undo)
        self.chat_history.begin_turn()
        
        # 2. Resolve context from mentions
        context_items = await self._resolve_context(mentions or [])
        
        # 3. Add user message with context
        self.chat_history.add_user_message(query, context_items=context_items)
        self._dirty = True
        
        # 4. Get tool definitions for LLM
        tool_definitions = self._tool_registry.get_definitions()
        logger.debug(f"Available tools: {[t.function.name for t in tool_definitions]}")
        
        # 5. Tool call loop (ReAct pattern)
        iteration = 0
        has_received_any_content = False
        
        try:
            while iteration < self._max_iterations:
                iteration += 1
                logger.debug(f"LLM iteration {iteration}")
                
                # Convert history to LLM format
                llm_messages = self._convert_to_llm_messages()
                
                # Call LLM and stream response
                full_response = ""
                full_reasoning = ""
                tool_calls: list[ToolCall] = []
                has_received_content = False
                
                async for chunk in self.llm.stream_chat(
                    llm_messages, 
                    tools=tool_definitions if tool_definitions else None,
                ):
                    # Handle text content
                    if chunk.content:
                        full_response += chunk.content
                        has_received_content = True
                        has_received_any_content = True
                    
                    # Handle reasoning content
                    if chunk.reasoning_content:
                        full_reasoning += chunk.reasoning_content
                        has_received_content = True
                        has_received_any_content = True
                    
                    # Handle tool calls
                    if chunk.tool_calls:
                        tool_calls.extend(chunk.tool_calls)
                    
                    yield chunk
                
                # If LLM requested tool calls
                if tool_calls:
                    logger.info(f"Tool calls requested: {[tc.function.name for tc in tool_calls]}")
                    
                    # Convert ToolCall to ToolCallState for history
                    tool_call_states = self._convert_to_tool_call_states(tool_calls)
                    
                    # Add assistant message with tool_calls to history
                    # Note: reasoning_content is NOT stored (only displayed in CLI)
                    self.chat_history.add_assistant_message(
                        full_response if full_response else "",
                        reasoning_content=None,  # Don't persist reasoning
                        tool_calls=tool_call_states,
                    ) 
                    
                    # Execute tools and add results to history
                    tool_results = await self._execute_tool_calls(tool_calls)
                    for tool_call_id, tool_name, args, result, duration in tool_results:
                        # Use add_tool_result which handles both state update and message creation
                        self.chat_history.add_tool_result(
                            tool_call_id=tool_call_id,
                            tool_name=tool_name,
                            result=result.output if result.success else None,
                            error=result.error if not result.success else None,
                            status=ToolStatus.DONE if result.success else ToolStatus.FAILED,
                        )
                        
                        # Yield tool result as response with metadata for UI display
                        # Format: [Tool: name|success|duration|args_json]\nresult_content
                        args_json = json.dumps(args, ensure_ascii=False)
                        success_flag = "1" if result.success else "0"
                        header = f"[Tool: {tool_name}|{success_flag}|{duration:.3f}|{args_json}]"
                        
                        yield LLMResponse(
                            content=f"{header}\n{result.to_content()}",
                        )
                    
                    # Continue loop for next LLM call
                    continue
                
                # No tool calls - add final assistant message and exit loop
                if has_received_content:
                    # Note: reasoning_content is NOT stored (only displayed in CLI)
                    self.chat_history.add_assistant_message(
                        full_response, 
                        reasoning_content=None,  # Don't persist reasoning
                    )
                
                # Exit the loop - LLM is done
                break
            
            # Check for max iterations
            if iteration >= self._max_iterations:
                logger.warning(f"Reached maximum tool iterations ({self._max_iterations})")
            
            # Sync and save
            self._sync_and_save()
            
        except Exception as e:
            logger.error(f"Error in agent loop: {e}", exc_info=True)
            
            # If we received partial content, save it
            if has_received_any_content:
                partial_note = "\n\n[响应被中断，以下是已接收的部分内容]"
                # Note: reasoning_content is NOT stored (only displayed in CLI)
                self.chat_history.add_assistant_message(
                    full_response + partial_note,
                    reasoning_content=None,  # Don't persist reasoning
                )
                self._sync_and_save()
                logger.info(f"Saved partial response: {len(full_response)} chars")
            
            raise
    
    async def _execute_tool_calls(
        self, 
        tool_calls: list[ToolCall],
    ) -> list[tuple[str, str, dict, ToolResult, float]]:
        """Execute tool calls and return results.
        
        Args:
            tool_calls: List of tool calls from LLM response.
            
        Returns:
            List of (tool_call_id, tool_name, args, result, duration) tuples.
        """
        import time
        
        results = []
        workspace_dir = self.session.workspace_directory
        
        for tool_call in tool_calls:
            tool_name = tool_call.function.name
            tool_call_id = tool_call.id
            start_time = time.time()
            
            logger.debug(f"Executing tool: {tool_name} (id={tool_call_id})")
            
            # Get tool from registry
            tool = self._tool_registry.get(tool_name)
            if tool is None:
                logger.warning(f"Tool not found: {tool_name}")
                result = ToolResult.fail(f"Tool '{tool_name}' not found")
                duration = time.time() - start_time
                results.append((tool_call_id, tool_name, {}, result, duration))
                continue
            
            # Parse arguments
            try:
                args = json.loads(tool_call.function.arguments)
            except json.JSONDecodeError as e:
                logger.warning(f"Invalid tool arguments for {tool_name}: {e}")
                result = ToolResult.fail(f"Invalid arguments: {e}")
                duration = time.time() - start_time
                results.append((tool_call_id, tool_name, {}, result, duration))
                continue
            
            # Execute tool
            try:
                # TODO: Add permission check here in the future
                
                # Build extra kwargs from tool's declared context_keys
                extra_kwargs = self._build_tool_context(tool)
                
                result = await tool.execute(
                    workspace_dir=workspace_dir, 
                    **args,
                    **extra_kwargs,
                )
                logger.debug(f"Tool {tool_name} completed: success={result.success}")
            except Exception as e:
                logger.error(f"Tool execution failed: {tool_name}", exc_info=True)
                result = ToolResult.fail(f"Execution error: {e}")
            
            duration = time.time() - start_time
            results.append((tool_call_id, tool_name, args, result, duration))
        
        return results
    
    def _build_tool_context(self, tool: Any) -> dict[str, Any]:
        """Build execution context kwargs based on tool's declared context_keys.
        
        Maps context key names to AgentLoop attributes, returning only
        the keys the tool has declared it needs.
        
        Args:
            tool: Tool instance with optional context_keys attribute.
            
        Returns:
            Dict of context kwargs to pass to tool.execute().
        """
        context_keys = getattr(tool, "context_keys", [])
        if not context_keys:
            return {}
        
        available = {
            "session_manager": self.session_manager,
            "parent_session": self.session,
            "llm": self.llm,
            "tool_registry": self._tool_registry,
            "on_progress": self._on_progress,
            "mcp_manager": self._mcp_manager,
        }
        
        return {k: available[k] for k in context_keys if k in available}
    
    def _convert_to_tool_call_states(
        self, 
        tool_calls: list[ToolCall],
    ) -> list[ToolCallState]:
        """Convert LLM ToolCall objects to ToolCallState for history storage.
        
        Args:
            tool_calls: List of ToolCall from LLM response.
            
        Returns:
            List of ToolCallState for ChatHistory.
        """
        states = []
        for tc in tool_calls:
            # Parse arguments from JSON string
            try:
                args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                args = {}
            
            state = ToolCallState(
                tool_call_id=tc.id,
                tool_name=tc.function.name,
                arguments=args,
                status=ToolStatus.PENDING,
            )
            states.append(state)
        return states

    async def _resolve_context(
        self, 
        mentions: list[MentionInput],
    ) -> list[ContextItem]:
        """
        根据 mentions 获取 context 内容。
        
        处理流程：
        1. 对于每个 mention，从 Registry 获取 Provider
        2. 调用 Provider.get_context() 获取 ContextItem
        3. 返回 context 列表
        
        错误处理：
        - Provider 不存在：忽略该 mention，记录警告
        - get_context 失败：记录警告日志，跳过该 mention
        
        Args:
            mentions: List of (provider, query) pairs from CLI
            
        Returns:
            List of resolved ContextItems
        """
        if not mentions:
            return []
        
        context_items: list[ContextItem] = []
        workspace_dir = self.session.workspace_directory
        
        # Create tasks for parallel fetching
        async def fetch_one(mention: MentionInput) -> list[ContextItem]:
            provider = self._context_registry.get(mention.provider)
            
            if provider is None:
                logger.warning(
                    f"Provider '{mention.provider}' not found, "
                    f"ignoring mention"
                )
                return []
            
            try:
                items = await provider.get_context(
                    mention.query,
                    workspace_dir=workspace_dir,
                )
                logger.debug(
                    f"Resolved @{mention.provider} {mention.query}: "
                    f"{len(items)} item(s)"
                )
                return items
            except ContextProviderError as e:
                logger.warning(
                    f"Failed to get context for @{mention.provider} "
                    f"'{mention.query}': {e}"
                )
                return []
            except Exception as e:
                logger.warning(
                    f"Unexpected error getting context for @{mention.provider} "
                    f"'{mention.query}': {e}",
                    exc_info=True,
                )
                return []
        
        # Fetch all contexts in parallel
        tasks = [fetch_one(m) for m in mentions]
        results = await asyncio.gather(*tasks)
        
        for items in results:
            context_items.extend(items)
        
        return context_items

    def _convert_to_llm_messages(self) -> List[ChatMessage]:
        """
        将 ChatHistoryItem 转换为 LLM 需要的 ChatMessage 格式。
        
        处理逻辑：
        1. 首先插入 system prompt（由 PromptBuilder 构建）
        2. 对于 user 消息，如果有 context_items，附加到 content 后面
        3. 对于 assistant 消息，如果有 tool_call_states，转换回 ToolCall
        4. 跳过已有的 system 消息（避免重复）
        
        注意：不修改原始 ChatHistoryItem，而是创建新的 ChatMessage
        
        Returns:
            List of ChatMessage objects ready for LLM
        """
        messages = []
        
        # Get tool definitions for system prompt
        tool_definitions = self._tool_registry.get_definitions()
        
        # 1. 首先插入 system prompt
        system_prompt = self.prompt_builder.build(tools=tool_definitions)
        messages.append(ChatMessage(role="system", content=system_prompt))
        
        # 2. 添加历史消息
        for item in self.chat_history.get_messages():
            msg = item.message
            
            # 跳过已有的 system 消息（避免重复）
            if msg.role == "system":
                continue
            
            # 如果是 user 消息且有 context，附加 context 到 content
            if msg.role == "user" and item.context_items:
                context_text = self._format_context_items(item.context_items)
                new_content = f"{msg.content or ''}\n\n{context_text}"
                
                # 创建新的 ChatMessage，不修改原始对象
                messages.append(ChatMessage(
                    role=msg.role,
                    content=new_content,
                    tool_calls=msg.tool_calls,
                    tool_call_id=msg.tool_call_id,
                    name=msg.name,
                ))
            # 如果是 assistant 消息且有 tool_call_states，转换回 ToolCall
            elif msg.role == "assistant" and item.tool_call_states:
                tool_calls = self._convert_states_to_tool_calls(item.tool_call_states)
                messages.append(ChatMessage(
                    role=msg.role,
                    content=msg.content,
                    reasoning_content=msg.reasoning_content,
                    tool_calls=tool_calls,
                ))
            else:
                messages.append(msg)
        
        return messages
    
    def _convert_states_to_tool_calls(
        self, 
        states: list[ToolCallState],
    ) -> list[ToolCall]:
        """Convert ToolCallState back to ToolCall for LLM message format.
        
        Args:
            states: List of ToolCallState from history.
            
        Returns:
            List of ToolCall for ChatMessage.
        """
        from wukong.core.llm.schema import FunctionCall
        
        tool_calls = []
        for state in states:
            tool_call = ToolCall(
                id=state.tool_call_id,
                type="function",
                function=FunctionCall(
                    name=state.tool_name,
                    arguments=json.dumps(state.arguments),
                ),
            )
            tool_calls.append(tool_call)
        return tool_calls

    def _format_context_items(self, context_items: List[ContextItem]) -> str:
        """
        将 context_items 格式化为 XML-like 文本。
        
        格式示例：
        <context>
        <file path="src/main.py" lines="1-50">
        文件内容...
        </file>
        </context>
        
        Args:
            context_items: 上下文项列表
            
        Returns:
            格式化后的文本
        """
        if not context_items:
            return ""
        
        parts = ["<context>"]
        
        for item in context_items:
            # 根据 provider_name 选择标签类型
            tag = self._get_context_tag(item)
            attrs = self._get_context_attrs(item)
            
            # 构建属性字符串
            attrs_str = " ".join(f'{k}="{v}"' for k, v in attrs.items())
            if attrs_str:
                parts.append(f"<{tag} {attrs_str}>")
            else:
                parts.append(f"<{tag}>")
            
            parts.append(item.content)
            parts.append(f"</{tag}>")
        
        parts.append("</context>")
        
        return "\n".join(parts)

    def _get_context_tag(self, item: ContextItem) -> str:
        """根据 provider 返回对应的 XML 标签名。"""
        tag_map = {
            "file": "file",
            "url": "url",
            "docs": "docs",
            "code": "code",
        }
        return tag_map.get(item.provider, "context-item")

    def _get_context_attrs(self, item: ContextItem) -> dict:
        """从 metadata 提取关键属性。"""
        attrs = {}
        metadata = item.metadata
        
        # 文件类型：提取 path 和 lines
        if item.provider == "file":
            if "path" in metadata:
                attrs["path"] = metadata["path"]
            if "lines" in metadata:
                attrs["lines"] = metadata["lines"]
            if "language" in metadata:
                attrs["language"] = metadata["language"]
        
        # URL 类型：提取 href 和 title
        elif item.provider == "url":
            if "url" in metadata:
                attrs["href"] = metadata["url"]
            elif "href" in metadata:
                attrs["href"] = metadata["href"]
            if "title" in metadata:
                attrs["title"] = metadata["title"]
        
        # 其他类型：尝试提取 name
        else:
            if "name" in metadata:
                attrs["name"] = metadata["name"]
            if "source" in metadata:
                attrs["source"] = metadata["source"]
        
        return attrs

    def _sync_and_save(self) -> None:
        """
        同步 ChatHistory 到 Session 并持久化。
        
        Only saves if there are unsaved changes (dirty flag).
        Uses the new storage structure: Message + Parts.
        """
        if self._dirty:
            # Get history items from ChatHistory
            history_items = self.chat_history.to_list()
            
            # Save all history items (replaces existing)
            self.session_manager.save_history_items(self.session, history_items)
            
            # Clear dirty flag
            self._dirty = False
            
            logger.debug(f"Session {self.session.session_id} saved with {len(history_items)} messages")

    def save(self) -> None:
        """
        手动保存 session。
        
        可用于外部调用，例如处理 Ctrl+C 时确保数据不丢失。
        """
        self._sync_and_save()

    async def __aenter__(self):
        """Context manager entry."""
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit. Ensures session is saved."""
        self.save()
