"""
Tool base classes.

Defines the abstract base class for all tools,
the ToolResult data structure, and tool-related exceptions.
"""

from abc import ABC, abstractmethod
from typing import Any, Type

from pydantic import BaseModel, Field


class ToolResult(BaseModel):
    """Result of tool execution.
    
    Represents the outcome of a tool call, either success or failure.
    This will be converted to ChatMessage(role="tool") for LLM.
    
    Example (success):
        ToolResult(
            success=True,
            output="File content here...",
        )
    
    Example (failure):
        ToolResult(
            success=False,
            error="File not found: /path/to/file",
        )
    """
    
    success: bool = True
    output: str | None = None   # Output content when success
    error: str | None = None    # Error message when failed
    
    # Optional metadata for debugging or UI display
    metadata: dict[str, Any] = Field(default_factory=dict)
    
    def to_content(self) -> str:
        """Convert to content string for LLM message.
        
        Returns:
            Output if success, error message if failed.
        """
        if self.success:
            return self.output or ""
        else:
            return f"Error: {self.error}" if self.error else "Unknown error"
    
    @classmethod
    def ok(cls, output: str, **metadata: Any) -> "ToolResult":
        """Create a successful result.
        
        Args:
            output: The output content.
            **metadata: Optional metadata.
            
        Returns:
            ToolResult with success=True.
        """
        return cls(success=True, output=output, metadata=metadata)
    
    @classmethod
    def fail(cls, error: str, **metadata: Any) -> "ToolResult":
        """Create a failed result.
        
        Args:
            error: The error message.
            **metadata: Optional metadata.
            
        Returns:
            ToolResult with success=False.
        """
        return cls(success=False, error=error, metadata=metadata)


class EmptyParameters(BaseModel):
    """Empty parameters model for tools that don't need any input."""
    pass


class Tool(ABC):
    """Abstract base class for tools.
    
    Tools are callable functions that LLM can invoke to perform actions.
    Each tool has:
    - name: Unique identifier for the tool
    - description: Human-readable description (shown to LLM)
    - parameters: Pydantic Model defining input parameters
    
    Tools are stateless - workspace_dir and other context is passed
    at execution time.
    
    Example:
        class ReadFileTool(Tool):
            name = "read_file"
            description = "Read contents of a file"
            parameters = ReadFileParams  # Pydantic Model
            
            async def execute(self, path: str, **kwargs) -> ToolResult:
                # Read file and return content
                ...
    """
    
    # Tool metadata (must be set by subclasses)
    name: str = ""                              # Unique identifier
    description: str = ""                       # Description for LLM
    parameters: Type[BaseModel] = EmptyParameters  # Pydantic Model for input params
    
    # Execution context keys this tool requires from AgentLoop.
    # AgentLoop will automatically inject these as kwargs when executing.
    # Available keys: "session_manager", "parent_session", "llm",
    #                 "tool_registry", "on_progress"
    context_keys: list[str] = []
    
    # Permission level placeholder (for future implementation)
    # permission_level: PermissionLevel = PermissionLevel.SAFE
    
    @abstractmethod
    async def execute(
        self,
        *,
        workspace_dir: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        """Execute the tool.
        
        Args:
            workspace_dir: The workspace directory path (passed at runtime).
            **kwargs: Tool-specific parameters (validated against self.parameters).
            
        Returns:
            ToolResult indicating success/failure with output/error.
            
        Raises:
            ToolError: If execution fails.
        """
        pass
    
    def validate_params(self, **kwargs: Any) -> BaseModel:
        """Validate parameters against the schema.
        
        Args:
            **kwargs: Raw parameters to validate.
            
        Returns:
            Validated Pydantic model instance.
            
        Raises:
            ValidationError: If parameters are invalid.
        """
        return self.parameters(**kwargs)
    
    def get_json_schema(self) -> dict[str, Any]:
        """Get JSON Schema for parameters.
        
        Uses Pydantic's model_json_schema() for automatic generation.
        
        Returns:
            JSON Schema dict for tool parameters.
        """
        return self.parameters.model_json_schema()
    
    def __repr__(self) -> str:
        return f"<Tool: {self.name}>"


class ToolError(Exception):
    """Base exception for tool errors.
    
    Raised when tool execution fails. The error message
    will be returned to LLM as ToolResult.error.
    """
    
    def __init__(self, message: str, tool_name: str = ""):
        self.tool_name = tool_name
        super().__init__(f"[{tool_name}] {message}" if tool_name else message)
