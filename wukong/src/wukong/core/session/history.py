"""
Chat history manager.

Handles message operations, tool state management, undo/redo, and history compression.
"""

from copy import deepcopy
from typing import Any, Callable

from wukong.core.context.base import ContextItem
from wukong.core.llm.schema import ChatMessage, Role
from wukong.core.session.models import (
    HistoryItem,
    ToolCallState,
    ToolStatus,
)

# Type alias for clarity (ChatHistoryItem is HistoryItem)
ChatHistoryItem = HistoryItem


class ChatHistory:
    """Chat history manager.

    Responsibilities:
    - Message add/edit/remove (semantic API)
    - Tool state updates (layered API)
    - Undo/redo (per turn)
    - History compression
    """

    def __init__(self, items: list[ChatHistoryItem] | None = None):
        """Initialize chat history.

        Args:
            items: Initial history items. Will be deep copied.
        """
        self._items: list[ChatHistoryItem] = deepcopy(items) if items else []
        self._undo_stack: list[list[ChatHistoryItem]] = []
        self._redo_stack: list[list[ChatHistoryItem]] = []

    # ========================================
    # Message Add (Semantic API)
    # ========================================

    def add_user_message(
        self,
        content: str,
        context_items: list[ContextItem] | None = None,
    ) -> ChatHistoryItem:
        """Add a user message.

        Args:
            content: User input content.
            context_items: Associated context items (@file, @url parsing results).

        Returns:
            The created history item.
        """
        item = ChatHistoryItem(
            message=ChatMessage(role="user", content=content),
            context_items=context_items or [],
        )
        return self._append_item(item)

    def add_assistant_message(
        self,
        content: str,
        reasoning_content: str | None = None,
        tool_calls: list[ToolCallState] | None = None,
    ) -> ChatHistoryItem:
        """Add an assistant response.

        Args:
            content: LLM response text.
            reasoning_content: Model reasoning process (if any).
            tool_calls: Tool call list (if any).

        Returns:
            The created history item.
        """
        item = ChatHistoryItem(
            message=ChatMessage(
                role="assistant", 
                content=content,
                reasoning_content=reasoning_content
            ),
            tool_call_states=tool_calls or [],
        )
        return self._append_item(item)

    def add_system_message(self, content: str) -> ChatHistoryItem:
        """Add a system prompt.

        Args:
            content: System prompt content.

        Returns:
            The created history item.
        """
        item = ChatHistoryItem(
            message=ChatMessage(role="system", content=content),
        )
        return self._append_item(item)

    def add_tool_result(
        self,
        tool_call_id: str,
        tool_name: str,
        result: Any = None,
        error: str | None = None,
        status: ToolStatus = ToolStatus.DONE,
    ) -> ChatHistoryItem:
        """Add tool execution result.

        This method:
        1. Updates the tool call state in the original assistant message
        2. Adds a TOOL role message for LLM to see the result

        Args:
            tool_call_id: Tool call ID.
            tool_name: Tool name.
            result: Execution result (if successful).
            error: Error message (if failed).
            status: Tool status, defaults to DONE.

        Returns:
            The created history item.

        Raises:
            ValueError: If tool_call_id not found.
        """
        # Update the tool state in the original message
        msg_idx = self._find_message_with_tool_call(tool_call_id)
        self.update_tool_call_state(
            msg_idx,
            tool_call_id,
            {"status": status, "output": result, "error": error},
        )

        # Format content for the tool message
        if error:
            content = f"Error: {error}"
        elif result is not None:
            content = str(result)
        else:
            content = ""

        # Add tool role message
        item = ChatHistoryItem(
            message=ChatMessage(
                role="tool",
                content=content,
                tool_call_id=tool_call_id,
                name=tool_name,
            ),
        )
        return self._append_item(item)

    # ========================================
    # Tool State Management (Layered API)
    # ========================================

    def update_tool_call_state(
        self,
        message_index: int,
        tool_call_id: str,
        updates: dict[str, Any],
    ) -> None:
        """Update tool call state in a specific message (low-level method).

        Args:
            message_index: Message index.
            tool_call_id: Tool call ID.
            updates: Fields to update:
                - status: ToolStatus
                - output: Any (execution result)
                - error: str (error message)

        Raises:
            IndexError: If message_index is out of range.
            ValueError: If tool_call_id not found in the message.
        """
        if message_index < 0 or message_index >= len(self._items):
            raise IndexError(f"Message index {message_index} out of range")

        item = self._items[message_index]
        for tool_state in item.tool_call_states:
            if tool_state.tool_call_id == tool_call_id:
                if "status" in updates:
                    tool_state.status = updates["status"]
                if "output" in updates:
                    tool_state.result = updates["output"]
                if "error" in updates:
                    tool_state.error = updates["error"]
                return

        raise ValueError(f"Tool call {tool_call_id} not found in message {message_index}")

    def update_tool_status(
        self,
        tool_call_id: str,
        status: ToolStatus,
    ) -> None:
        """Convenience method: update only tool status (e.g., PENDING → RUNNING).

        Internally calls update_tool_call_state.

        Args:
            tool_call_id: Tool call ID.
            status: New status.

        Raises:
            ValueError: If tool_call_id not found.
        """
        msg_idx = self._find_message_with_tool_call(tool_call_id)
        self.update_tool_call_state(msg_idx, tool_call_id, {"status": status})

    def get_tool_state(self, tool_call_id: str) -> ToolCallState | None:
        """Get tool call state by ID.

        Args:
            tool_call_id: Tool call ID.

        Returns:
            Tool call state if found, None otherwise.
        """
        for item in self._items:
            for tool_state in item.tool_call_states:
                if tool_state.tool_call_id == tool_call_id:
                    return tool_state
        return None

    # ========================================
    # Undo/Redo (Per Turn)
    # ========================================

    def begin_turn(self) -> None:
        """Begin a new turn, save undo point.

        Call this at the start of each user turn to enable undo.
        """
        self._save_undo_point()
        self._redo_stack.clear()

    def undo(self) -> bool:
        """Undo the last turn.

        Returns:
            True if undo was successful, False if nothing to undo.
        """
        if not self._undo_stack:
            return False
        self._redo_stack.append(self._snapshot())
        self._items = self._undo_stack.pop()
        return True

    def redo(self) -> bool:
        """Redo the last undone turn.

        Returns:
            True if redo was successful, False if nothing to redo.
        """
        if not self._redo_stack:
            return False
        self._undo_stack.append(self._snapshot())
        self._items = self._redo_stack.pop()
        return True

    def can_undo(self) -> bool:
        """Check if undo is possible."""
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        """Check if redo is possible."""
        return len(self._redo_stack) > 0

    def clear_undo_history(self) -> None:
        """Clear all undo/redo history to free memory."""
        self._undo_stack.clear()
        self._redo_stack.clear()

    # ========================================
    # Query
    # ========================================

    def get_messages(self) -> list[ChatHistoryItem]:
        """Get all messages.

        Returns:
            List of chat history items (reference, not copy).
        """
        return self._items

    def get_messages_copy(self) -> list[ChatHistoryItem]:
        """Get a deep copy of all messages.

        Returns:
            Deep copy of chat history items.
        """
        return deepcopy(self._items)

    def get_last_user_message(self) -> ChatHistoryItem | None:
        """Get the last user message.

        Returns:
            Last user message if found, None otherwise.
        """
        for item in reversed(self._items):
            if item.message.role == "user":
                return item
        return None

    def get_last_assistant_message(self) -> ChatHistoryItem | None:
        """Get the last assistant message.

        Returns:
            Last assistant message if found, None otherwise.
        """
        for item in reversed(self._items):
            if item.message.role == "assistant":
                return item
        return None

    def get_context_window(
        self,
        max_messages: int | None = None,
    ) -> list[ChatHistoryItem]:
        """Get effective context window.

        Currently implements sliding window strategy.
        Keeps system messages and recent messages.

        Args:
            max_messages: Maximum number of messages to return.
                If None, returns all messages.

        Returns:
            List of messages for context window.
        """
        if max_messages is None or len(self._items) <= max_messages:
            return self._items

        # Keep system messages
        system_messages = [
            item for item in self._items
            if item.message.role == "system"
        ]

        # Keep recent messages
        non_system = [
            item for item in self._items
            if item.message.role != "system"
        ]

        remaining_slots = max_messages - len(system_messages)
        recent_messages = non_system[-remaining_slots:] if remaining_slots > 0 else []

        return system_messages + recent_messages

    def __len__(self) -> int:
        """Get message count."""
        return len(self._items)

    def __bool__(self) -> bool:
        """Check if history is non-empty."""
        return len(self._items) > 0

    # ========================================
    # History Compression
    # ========================================

    def compress(
        self,
        summarizer: Callable[[list[ChatHistoryItem]], str],
        keep_recent: int = 10,
    ) -> None:
        """Compress old history into a summary.

        Args:
            summarizer: Function to generate summary from messages.
                Should return a summary string.
            keep_recent: Number of recent messages to keep uncompressed.
        """
        if len(self._items) <= keep_recent:
            return

        # Split into old and recent
        old_items = self._items[:-keep_recent]
        recent_items = self._items[-keep_recent:]

        # Generate summary
        summary = summarizer(old_items)

        # Create summary item
        summary_item = ChatHistoryItem(
            message=ChatMessage(
                role="system",
                content=f"[Previous conversation summary]\n{summary}",
            ),
            is_summarized=True,
            conversation_summary=summary,
        )

        # Replace history
        self._items = [summary_item] + recent_items

    # ========================================
    # Serialization
    # ========================================

    def to_list(self) -> list[ChatHistoryItem]:
        """Export as list for serialization.

        Note: Undo/redo stacks are NOT included.

        Returns:
            List of chat history items (deep copy).
        """
        return deepcopy(self._items)

    @classmethod
    def from_list(cls, items: list[ChatHistoryItem]) -> "ChatHistory":
        """Create ChatHistory from a list of items.

        Args:
            items: List of chat history items.

        Returns:
            New ChatHistory instance.
        """
        return cls(items=items)

    # ========================================
    # Private Methods
    # ========================================

    def _append_item(self, item: ChatHistoryItem) -> ChatHistoryItem:
        """Internal: append an item to history.

        Args:
            item: Item to append.

        Returns:
            The appended item.
        """
        self._items.append(item)
        return item

    def _save_undo_point(self) -> None:
        """Save current state to undo stack."""
        self._undo_stack.append(self._snapshot())

    def _snapshot(self) -> list[ChatHistoryItem]:
        """Create a deep copy of current history."""
        return deepcopy(self._items)

    def _find_message_with_tool_call(self, tool_call_id: str) -> int:
        """Find message index containing a tool call.

        Args:
            tool_call_id: Tool call ID to find.

        Returns:
            Message index.

        Raises:
            ValueError: If tool_call_id not found.
        """
        for i, item in enumerate(self._items):
            for tool_state in item.tool_call_states:
                if tool_state.tool_call_id == tool_call_id:
                    return i
        raise ValueError(f"Tool call {tool_call_id} not found")

