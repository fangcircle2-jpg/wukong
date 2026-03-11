"""
Session management module.

Provides session lifecycle management, persistence, and CLI commands support.
"""

from wukong.core.context.base import ContextItem
from wukong.core.llm.schema import ChatMessage, Role
from wukong.core.session.history import ChatHistory
from wukong.core.session.manager import SessionManager
from wukong.core.session.models import (
    ChatHistoryItem,  # Alias for HistoryItem (backward compatibility)
    HistoryItem,
    Message,
    MessageMode,
    Part,
    PartType,
    Session,
    SessionIndex,
    SessionSummary,
    SessionUsage,
    TokenUsage,
    ToolCallState,
    ToolStatus,
)
from wukong.core.session.storage import (
    MessageStorage,
    PartStorage,
    SessionStorage,
    StorageManager,
)

__all__ = [
    # Models
    "Session",
    "SessionIndex",
    "SessionSummary",
    "SessionUsage",
    "TokenUsage",
    "Message",
    "HistoryItem",
    "ChatHistoryItem",  # Alias for backward compatibility
    "ChatMessage",  # Re-exported from llm.schema
    "ContextItem",  # Re-exported from context.base
    "ToolCallState",
    "ToolStatus",
    "Role",  # Re-exported from llm.schema (replaces MessageRole)
    "MessageMode",
    # Part models
    "Part",
    "PartType",
    # Storage
    "StorageManager",
    "SessionStorage",
    "MessageStorage",
    "PartStorage",
    # History Manager
    "ChatHistory",
    # Session Manager
    "SessionManager",
]

