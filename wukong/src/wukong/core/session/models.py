"""
Session data models.

Defines all data structures for session management using Pydantic.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# Import unified ChatMessage from llm.schema
from wukong.core.llm.schema import ChatMessage, Role, ToolCall

# Import ContextItem from context module (single source of truth)
from wukong.core.context.base import ContextItem

# Import ID generator
from wukong.core.utils.id import generate_message_id, generate_part_id, generate_session_id


class MessageMode(str, Enum):
    """Message mode."""

    NORMAL = "normal"
    PLAN = "plan"
    CODE = "code"


class ToolStatus(str, Enum):
    """Tool execution status."""

    PENDING = "pending"      # Waiting to execute
    RUNNING = "running"      # Executing
    DONE = "done"            # Completed successfully
    FAILED = "failed"        # Execution failed
    CANCELLED = "cancelled"  # Cancelled by user


class ToolCallState(BaseModel):
    """Tool call state."""

    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any]
    status: ToolStatus = ToolStatus.PENDING
    result: Any | None = None
    error: str | None = None


class PartType(str, Enum):
    """Part type enum."""

    TEXT = "text"              # Plain text output
    REASONING = "reasoning"    # Model reasoning/thinking
    TOOL_CALL = "tool_call"    # Tool invocation
    TOOL_RESULT = "tool_result"  # Tool execution result
    ERROR = "error"            # Error information
    CUSTOM = "custom"          # Custom/user-defined type


class Part(BaseModel):
    """Message part - stores detailed content for a message.
    
    Parts are stored independently in: part/{message_id}/{part_id}.json
    
    Required fields:
    - part_id: Unique identifier (auto-generated)
    - message_id: Parent message ID
    - part_type: Type of content
    - created_at: Creation timestamp
    - updated_at: Last update timestamp
    
    Custom data can be stored in the 'data' field.
    """

    # Required fields (5)
    part_id: str = Field(default_factory=generate_part_id)
    message_id: str
    part_type: PartType
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Flexible data storage for custom content
    data: dict[str, Any] = Field(default_factory=dict)

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now()

    model_config = {"extra": "allow"}


class Message(BaseModel):
    """Message model - stored independently in message/{session_id}/{message_id}.json.
    
    Content details (text, reasoning, tool calls) are stored as separate Parts.
    """

    # Identity
    message_id: str = Field(default_factory=generate_message_id)
    session_id: str  # Parent session ID
    
    # Core message info
    role: Role  # user, assistant, system, tool
    
    # For tool role messages
    tool_call_id: str | None = None  # Which tool call this result is for
    name: str | None = None  # Tool name
    
    # Context and state
    context_items: list[ContextItem] = Field(default_factory=list)
    is_gathering_context: bool = False

    # Conversation compression
    conversation_summary: str | None = None
    is_summarized: bool = False
    
    # Part references (ordered list of part IDs)
    part_ids: list[str] = Field(default_factory=list)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now()

    def add_part_id(self, part_id: str) -> None:
        """Add a part ID to the message."""
        if part_id not in self.part_ids:
            self.part_ids.append(part_id)
            self.touch()


class HistoryItem(BaseModel):
    """In-memory history item for ChatHistory operations.
    
    This is the in-memory representation used by ChatHistory.
    For persistence, use Message + Part models.
    
    Provides conversion methods to/from Message + Part.
    """

    # Identity
    message_id: str = Field(default_factory=generate_message_id)
    session_id: str | None = None  # Optional for in-memory usage
    
    # Core message (embedded for convenient in-memory access)
    message: ChatMessage
    
    # Context
    context_items: list[ContextItem] = Field(default_factory=list)
    tool_call_states: list[ToolCallState] = Field(default_factory=list)

    # State flags
    is_gathering_context: bool = False

    # Conversation compression
    conversation_summary: str | None = None
    is_summarized: bool = False
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now()

    def to_message_and_parts(self, session_id: str) -> tuple["Message", list["Part"]]:
        """Convert to Message and Parts for persistence.
        
        Args:
            session_id: Session ID for the message.
            
        Returns:
            Tuple of (Message, list of Parts).
        """
        parts: list[Part] = []
        part_ids: list[str] = []
        
        # Create TEXT part for content
        if self.message.content:
            text_part = Part(
                message_id=self.message_id,
                part_type=PartType.TEXT,
                data={"content": self.message.content},
            )
            parts.append(text_part)
            part_ids.append(text_part.part_id)
        
        # Create REASONING part if present
        if self.message.reasoning_content:
            reasoning_part = Part(
                message_id=self.message_id,
                part_type=PartType.REASONING,
                data={"content": self.message.reasoning_content},
            )
            parts.append(reasoning_part)
            part_ids.append(reasoning_part.part_id)
        
        # Create TOOL_CALL parts for each tool call
        if self.message.tool_calls:
            for tc in self.message.tool_calls:
                # Find matching state
                state = None
                for ts in self.tool_call_states:
                    if ts.tool_call_id == tc.id:
                        state = ts
                        break
                
                tool_call_part = Part(
                    message_id=self.message_id,
                    part_type=PartType.TOOL_CALL,
                    data={
                        "tool_call_id": tc.id,
                        "tool_name": tc.function.name,
                        "arguments": tc.function.arguments,
                        "status": state.status.value if state else ToolStatus.PENDING.value,
                        "result": state.result if state else None,
                        "error": state.error if state else None,
                    },
                )
                parts.append(tool_call_part)
                part_ids.append(tool_call_part.part_id)
        
        # Create Message
        message = Message(
            message_id=self.message_id,
            session_id=session_id,
            role=self.message.role,
            tool_call_id=self.message.tool_call_id,
            name=self.message.name,
            context_items=self.context_items,
            is_gathering_context=self.is_gathering_context,
            conversation_summary=self.conversation_summary,
            is_summarized=self.is_summarized,
            part_ids=part_ids,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )
        
        return message, parts

    @classmethod
    def from_message_and_parts(
        cls, message: "Message", parts: list["Part"]
    ) -> "HistoryItem":
        """Create HistoryItem from Message and Parts.
        
        Args:
            message: Message model.
            parts: List of Part models.
            
        Returns:
            HistoryItem for in-memory use.
        """
        content = ""
        reasoning_content = None
        tool_calls: list[ToolCall] = []
        tool_call_states: list[ToolCallState] = []
        
        for part in parts:
            if part.part_type == PartType.TEXT:
                content = part.data.get("content", "")
            elif part.part_type == PartType.REASONING:
                reasoning_content = part.data.get("content")
            elif part.part_type == PartType.TOOL_CALL:
                # Reconstruct ToolCall
                tc = ToolCall(
                    id=part.data.get("tool_call_id", ""),
                    type="function",
                    function=ToolCall.Function(
                        name=part.data.get("tool_name", ""),
                        arguments=part.data.get("arguments", {}),
                    ),
                )
                tool_calls.append(tc)
                
                # Reconstruct ToolCallState
                status_str = part.data.get("status", ToolStatus.PENDING.value)
                try:
                    status = ToolStatus(status_str)
                except ValueError:
                    status = ToolStatus.PENDING
                    
                state = ToolCallState(
                    tool_call_id=part.data.get("tool_call_id", ""),
                    tool_name=part.data.get("tool_name", ""),
                    arguments=part.data.get("arguments", {}),
                    status=status,
                    result=part.data.get("result"),
                    error=part.data.get("error"),
                )
                tool_call_states.append(state)
        
        # Build ChatMessage
        chat_message = ChatMessage(
            role=message.role,
            content=content,
            reasoning_content=reasoning_content,
            tool_calls=tool_calls if tool_calls else None,
            tool_call_id=message.tool_call_id,
            name=message.name,
        )
        
        return cls(
            message_id=message.message_id,
            session_id=message.session_id,
            message=chat_message,
            context_items=message.context_items,
            tool_call_states=tool_call_states,
            is_gathering_context=message.is_gathering_context,
            conversation_summary=message.conversation_summary,
            is_summarized=message.is_summarized,
            created_at=message.created_at,
            updated_at=message.updated_at,
        )


# Alias for backward compatibility
ChatHistoryItem = HistoryItem


class TokenUsage(BaseModel):
    """Token usage statistics for a single message."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class SessionUsage(BaseModel):
    """Session usage statistics."""

    total_tokens: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    tool_calls_count: int = 0

    def add(self, usage: TokenUsage) -> None:
        """Add token usage from a single message."""
        self.prompt_tokens += usage.prompt_tokens
        self.completion_tokens += usage.completion_tokens
        self.total_tokens += usage.total_tokens


class Session(BaseModel):
    """Session data model - stored in session/{project_id}/{session_id}.json.
    
    Messages are stored separately in message/{session_id}/ directory.
    """

    session_id: str = Field(default_factory=generate_session_id)
    project_id: str  # Project identifier (hash of workspace path)
    title: str
    workspace_directory: str
    
    # Message count (updated when messages are added/removed)
    message_count: int = 0

    # Metadata
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Optional configuration
    mode: MessageMode | None = None
    model_name: str | None = None
    usage: SessionUsage = Field(default_factory=SessionUsage)

    # State flags
    is_active: bool = True
    parent_session_id: str | None = None  # Fork source (if forked)

    def touch(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now()
    
    def increment_message_count(self) -> None:
        """Increment message count."""
        self.message_count += 1
        self.touch()
    
    def decrement_message_count(self) -> None:
        """Decrement message count."""
        if self.message_count > 0:
            self.message_count -= 1
        self.touch()


class SessionSummary(BaseModel):
    """Session summary for listing (lightweight)."""

    session_id: str
    project_id: str
    title: str
    workspace_directory: str
    model_name: str | None = None
    created_at: datetime
    updated_at: datetime
    message_count: int
    is_active: bool

    @classmethod
    def from_session(cls, session: Session) -> "SessionSummary":
        """Create summary from full session."""
        return cls(
            session_id=session.session_id,
            project_id=session.project_id,
            title=session.title,
            workspace_directory=session.workspace_directory,
            model_name=session.model_name,
            created_at=session.created_at,
            updated_at=session.updated_at,
            message_count=session.message_count,
            is_active=session.is_active,
        )


class SessionIndex(BaseModel):
    """Session index for fast lookup."""

    sessions: list[SessionSummary] = Field(default_factory=list)
    last_active_session_id: str | None = None

    def add_session(self, session: Session) -> None:
        """Add or update session in index."""
        summary = SessionSummary.from_session(session)

        # Update existing or append new
        for i, s in enumerate(self.sessions):
            if s.session_id == session.session_id:
                self.sessions[i] = summary
                return
        self.sessions.append(summary)

    def remove_session(self, session_id: str) -> bool:
        """Remove session from index."""
        for i, s in enumerate(self.sessions):
            if s.session_id == session_id:
                self.sessions.pop(i)
                if self.last_active_session_id == session_id:
                    self.last_active_session_id = None
                return True
        return False

    def get_summary(self, session_id: str) -> SessionSummary | None:
        """Get session summary by ID."""
        for s in self.sessions:
            if s.session_id == session_id:
                return s
        return None

    def set_active(self, session_id: str) -> None:
        """Set the last active session."""
        self.last_active_session_id = session_id

