"""
Tool Registry.

Manages registration and lookup of tools.
Provides unified conversion to LLM ToolDefinition format.
"""

import logging
from typing import Any

from wukong.core.llm.schema import FunctionDefinition, ToolDefinition
from wukong.core.tools.base import Tool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for tools.
    
    Manages tool registration, lookup, and conversion to LLM format.
    Follows the same design pattern as ContextRegistry.
    
    Usage:
        registry = ToolRegistry()
        
        # Register tools
        registry.register(ReadFileTool())
        registry.register(WriteFileTool())
        
        # Or use defaults
        registry.register_defaults()
        
        # Lookup
        read_tool = registry.get("read_file")
        all_tools = registry.get_all()
        
        # Get definitions for LLM
        definitions = registry.get_definitions()
        
        # Execute tool
        result = await read_tool.execute(path="src/main.py", workspace_dir="/project")
    """
    
    def __init__(self):
        """Initialize empty registry."""
        self._tools: dict[str, Tool] = {}
    
    def register(self, tool: Tool) -> bool:
        """Register a tool.
        
        If a tool with the same name is already registered,
        the registration is ignored and a warning is logged.
        
        Args:
            tool: Tool instance to register.
            
        Returns:
            True if registered successfully, False if already exists.
        """
        if tool.name in self._tools:
            logger.warning(
                f"Tool '{tool.name}' is already registered, ignoring duplicate registration"
            )
            return False
        
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")
        return True
    
    def unregister(self, name: str) -> bool:
        """Unregister a tool.
        
        Args:
            name: Name of tool to unregister.
            
        Returns:
            True if unregistered successfully, False if not found.
        """
        if name not in self._tools:
            logger.warning(f"Tool '{name}' not found, cannot unregister")
            return False
        
        del self._tools[name]
        logger.debug(f"Unregistered tool: {name}")
        return True
    
    def get(self, name: str) -> Tool | None:
        """Get a tool by name.
        
        Args:
            name: Tool name (e.g., "read_file", "write_file").
            
        Returns:
            Tool instance if found, None otherwise.
        """
        return self._tools.get(name)
    
    def get_all(self) -> list[Tool]:
        """Get all registered tools.
        
        Returns:
            List of all tool instances.
        """
        return list(self._tools.values())
    
    def list_names(self) -> list[str]:
        """Get list of all registered tool names.
        
        Returns:
            List of tool names.
        """
        return list(self._tools.keys())
    
    def __len__(self) -> int:
        """Get number of registered tools."""
        return len(self._tools)
    
    def __contains__(self, name: str) -> bool:
        """Check if tool is registered (supports 'in' operator)."""
        return name in self._tools
    
    def __iter__(self):
        """Iterate over registered tools."""
        return iter(self._tools.values())
    
    # ========================================
    # LLM Format Conversion
    # ========================================
    
    def get_definitions(self) -> list[ToolDefinition]:
        """Get all tools as LLM ToolDefinition format.
        
        Converts all registered tools to the format required by LLM APIs.
        Uses Pydantic's model_json_schema() for automatic JSON Schema generation.
        
        Returns:
            List of ToolDefinition objects ready for LLM.
            
        Example:
            definitions = registry.get_definitions()
            response = await llm.stream_chat(messages, tools=definitions)
        """
        definitions = []
        
        for tool in self._tools.values():
            # Get JSON Schema from Pydantic model
            json_schema = tool.get_json_schema()
            
            # Create ToolDefinition (OpenAI-compatible format)
            definition = ToolDefinition(
                type="function",
                function=FunctionDefinition(
                    name=tool.name,
                    description=tool.description,
                    parameters=json_schema,
                ),
            )
            definitions.append(definition)
        
        return definitions
    
    # ========================================
    # Default Tool Registration
    # ========================================
    
    def register_defaults(self, enabled_tools: list[str] | None = None) -> list[str]:
        """Register default/builtin tools.
        
        Convenience method to register commonly used tools.
        
        Available tools:
        - read_file: Read file contents
        - write_file: Write/create files
        - list_dir: List directory contents
        - grep: Search file contents
        - glob: Find files by pattern
        - bash: Execute shell commands
        - batch: Execute multiple tools in parallel
        - task: Launch subagent to execute independent tasks
        
        Args:
            enabled_tools: List of tool names to enable.
                          If None, all available tools are registered.
            
        Returns:
            List of successfully registered tool names.
        """
        from wukong.core.tools.builtins import (
            BashTool,
            BatchTool,
            GlobTool,
            GrepTool,
            ListDirTool,
            ReadFileTool,
            TaskTool,
            WriteFileTool,
        )
        
        # All available builtin tools
        all_tools = {
            "bash": BashTool,
            "batch": BatchTool,
            "glob": GlobTool,
            "grep": GrepTool,
            "list_dir": ListDirTool,
            "read_file": ReadFileTool,
            "task": TaskTool,
            "write_file": WriteFileTool,
        }
        
        # Default: enable all tools
        if enabled_tools is None:
            enabled_tools = list(all_tools.keys())
        
        registered = []
        for name in enabled_tools:
            if name in all_tools:
                if self.register(all_tools[name]()):
                    registered.append(name)
        
        logger.info(f"Registered {len(registered)} default tools: {registered}")
        return registered


# ========================================
# Factory Function
# ========================================

def create_default_registry(enabled_tools: list[str] | None = None) -> ToolRegistry:
    """Create a registry with default tools registered.
    
    Convenience function for quick setup.
    
    Args:
        enabled_tools: List of tool names to enable.
                      If None, all available tools are registered.
        
    Returns:
        Configured ToolRegistry instance.
        
    Example:
        registry = create_default_registry()
        definitions = registry.get_definitions()
    """
    registry = ToolRegistry()
    registry.register_defaults(enabled_tools=enabled_tools)
    return registry
