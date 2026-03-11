"""
Tests for ChatHistory.

Run with: pytest tests/test_chat_history.py -v
"""

import pytest

from wukong.core.session import (
    ChatHistory,
    ChatHistoryItem,
    ChatMessage,
    ContextItem,
    Role,
    ToolCallState,
    ToolStatus,
)


@pytest.fixture
def history():
    """Create an empty ChatHistory."""
    return ChatHistory()


@pytest.fixture
def history_with_messages():
    """Create a ChatHistory with some messages."""
    h = ChatHistory()
    h.add_system_message("You are a helpful assistant.")
    h.add_user_message("Hello!")
    h.add_assistant_message("Hi there! How can I help?")
    return h


class TestMessageAdd:
    """Test message adding methods."""

    def test_add_user_message(self, history: ChatHistory):
        """Test adding a user message."""
        item = history.add_user_message("Hello, world!")

        assert len(history) == 1
        assert item.message.role == "user"
        assert item.message.content == "Hello, world!"

    def test_add_user_message_with_context(self, history: ChatHistory):
        """Test adding a user message with context items."""
        context = [
            ContextItem(
                id="ctx_1",
                provider="file",
                name="test.py",
                content="file content here",
            )
        ]
        item = history.add_user_message("Analyze this file", context_items=context)

        assert len(item.context_items) == 1
        assert item.context_items[0].provider == "file"

    def test_add_assistant_message(self, history: ChatHistory):
        """Test adding an assistant message."""
        item = history.add_assistant_message("Hello! How can I help?")

        assert item.message.role == "assistant"
        assert item.message.content == "Hello! How can I help?"

    def test_add_assistant_message_with_tool_calls(self, history: ChatHistory):
        """Test adding an assistant message with tool calls."""
        tool_calls = [
            ToolCallState(
                tool_call_id="call_123",
                tool_name="read_file",
                arguments={"path": "src/main.py"},
                status=ToolStatus.PENDING,
            )
        ]
        item = history.add_assistant_message(
            "Let me read that file...",
            tool_calls=tool_calls,
        )

        assert len(item.tool_call_states) == 1
        assert item.tool_call_states[0].tool_name == "read_file"

    def test_add_system_message(self, history: ChatHistory):
        """Test adding a system message."""
        item = history.add_system_message("You are a coding assistant.")

        assert item.message.role == "system"
        assert item.message.content == "You are a coding assistant."

    def test_add_tool_result(self, history: ChatHistory):
        """Test adding a tool result."""
        # First add an assistant message with tool call
        history.add_assistant_message(
            "",
            tool_calls=[
                ToolCallState(
                    tool_call_id="call_123",
                    tool_name="read_file",
                    arguments={"path": "test.py"},
                    status=ToolStatus.PENDING,
                )
            ],
        )

        # Add tool result
        item = history.add_tool_result(
            tool_call_id="call_123",
            tool_name="read_file",
            result="print('hello')",
        )

        assert item.message.role == "tool"
        assert item.message.tool_call_id == "call_123"
        assert item.message.name == "read_file"
        assert "print('hello')" in item.message.content

    def test_add_tool_result_with_error(self, history: ChatHistory):
        """Test adding a tool result with error."""
        history.add_assistant_message(
            "",
            tool_calls=[
                ToolCallState(
                    tool_call_id="call_456",
                    tool_name="run_shell",
                    arguments={"command": "rm -rf /"},
                    status=ToolStatus.PENDING,
                )
            ],
        )

        item = history.add_tool_result(
            tool_call_id="call_456",
            tool_name="run_shell",
            error="Permission denied",
            status=ToolStatus.FAILED,
        )

        assert "Error: Permission denied" in item.message.content


class TestToolStateManagement:
    """Test tool state management."""

    def test_update_tool_status(self, history: ChatHistory):
        """Test updating tool status."""
        history.add_assistant_message(
            "",
            tool_calls=[
                ToolCallState(
                    tool_call_id="call_123",
                    tool_name="read_file",
                    arguments={},
                    status=ToolStatus.PENDING,
                )
            ],
        )

        history.update_tool_status("call_123", ToolStatus.RUNNING)

        state = history.get_tool_state("call_123")
        assert state is not None
        assert state.status == ToolStatus.RUNNING

    def test_update_tool_call_state(self, history: ChatHistory):
        """Test updating tool call state with multiple fields."""
        history.add_assistant_message(
            "",
            tool_calls=[
                ToolCallState(
                    tool_call_id="call_123",
                    tool_name="read_file",
                    arguments={},
                )
            ],
        )

        history.update_tool_call_state(
            0,
            "call_123",
            {"status": ToolStatus.DONE, "output": "file content"},
        )

        state = history.get_tool_state("call_123")
        assert state.status == ToolStatus.DONE
        assert state.result == "file content"

    def test_get_tool_state_not_found(self, history: ChatHistory):
        """Test getting non-existent tool state."""
        result = history.get_tool_state("nonexistent")
        assert result is None

    def test_update_tool_status_not_found(self, history: ChatHistory):
        """Test updating non-existent tool status."""
        with pytest.raises(ValueError, match="not found"):
            history.update_tool_status("nonexistent", ToolStatus.RUNNING)


class TestUndoRedo:
    """Test undo/redo functionality."""

    def test_begin_turn_creates_undo_point(self, history: ChatHistory):
        """Test that begin_turn creates an undo point."""
        history.add_system_message("System prompt")

        history.begin_turn()
        history.add_user_message("Hello")
        history.add_assistant_message("Hi")

        assert history.can_undo() is True

    def test_undo_restores_previous_state(self, history: ChatHistory):
        """Test that undo restores previous state."""
        history.add_system_message("System prompt")

        history.begin_turn()
        history.add_user_message("Hello")
        history.add_assistant_message("Hi")

        assert len(history) == 3

        result = history.undo()

        assert result is True
        assert len(history) == 1
        assert history.get_messages()[0].message.content == "System prompt"

    def test_redo_after_undo(self, history: ChatHistory):
        """Test redo after undo."""
        history.begin_turn()
        history.add_user_message("Hello")
        history.add_assistant_message("Hi")

        history.undo()
        assert len(history) == 0

        result = history.redo()

        assert result is True
        assert len(history) == 2

    def test_undo_empty_stack(self, history: ChatHistory):
        """Test undo with empty stack."""
        result = history.undo()
        assert result is False

    def test_redo_empty_stack(self, history: ChatHistory):
        """Test redo with empty stack."""
        result = history.redo()
        assert result is False

    def test_new_turn_clears_redo_stack(self, history: ChatHistory):
        """Test that beginning a new turn clears redo stack."""
        history.begin_turn()
        history.add_user_message("First")

        history.begin_turn()
        history.add_user_message("Second")

        history.undo()
        assert history.can_redo() is True

        # Start new turn, should clear redo
        history.begin_turn()
        assert history.can_redo() is False

    def test_multiple_undo(self, history: ChatHistory):
        """Test multiple undo operations."""
        history.begin_turn()
        history.add_user_message("Turn 1")

        history.begin_turn()
        history.add_user_message("Turn 2")

        history.begin_turn()
        history.add_user_message("Turn 3")

        assert len(history) == 3

        history.undo()  # Remove Turn 3
        assert len(history) == 2

        history.undo()  # Remove Turn 2
        assert len(history) == 1

        history.undo()  # Remove Turn 1
        assert len(history) == 0

    def test_clear_undo_history(self, history: ChatHistory):
        """Test clearing undo history."""
        history.begin_turn()
        history.add_user_message("Hello")

        history.clear_undo_history()

        assert history.can_undo() is False
        assert history.can_redo() is False


class TestQuery:
    """Test query methods."""

    def test_get_messages(self, history_with_messages: ChatHistory):
        """Test getting all messages."""
        messages = history_with_messages.get_messages()

        assert len(messages) == 3
        assert messages[0].message.role == "system"

    def test_get_last_user_message(self, history_with_messages: ChatHistory):
        """Test getting last user message."""
        last = history_with_messages.get_last_user_message()

        assert last is not None
        assert last.message.content == "Hello!"

    def test_get_last_user_message_empty(self, history: ChatHistory):
        """Test getting last user message from empty history."""
        result = history.get_last_user_message()
        assert result is None

    def test_get_last_assistant_message(self, history_with_messages: ChatHistory):
        """Test getting last assistant message."""
        last = history_with_messages.get_last_assistant_message()

        assert last is not None
        assert last.message.content == "Hi there! How can I help?"

    def test_len(self, history_with_messages: ChatHistory):
        """Test __len__."""
        assert len(history_with_messages) == 3

    def test_bool_empty(self, history: ChatHistory):
        """Test __bool__ for empty history."""
        assert bool(history) is False

    def test_bool_non_empty(self, history_with_messages: ChatHistory):
        """Test __bool__ for non-empty history."""
        assert bool(history_with_messages) is True


class TestContextWindow:
    """Test context window management."""

    def test_get_context_window_all(self, history_with_messages: ChatHistory):
        """Test getting all messages when under limit."""
        window = history_with_messages.get_context_window(max_messages=10)
        assert len(window) == 3

    def test_get_context_window_limited(self, history: ChatHistory):
        """Test context window with limit."""
        history.add_system_message("System")
        for i in range(10):
            history.add_user_message(f"User {i}")

        window = history.get_context_window(max_messages=5)

        # Should keep system message + 4 recent
        assert len(window) == 5
        assert window[0].message.role == "system"

    def test_get_context_window_preserves_system(self, history: ChatHistory):
        """Test that system messages are always preserved."""
        history.add_system_message("System 1")
        history.add_system_message("System 2")
        for i in range(5):
            history.add_user_message(f"User {i}")

        window = history.get_context_window(max_messages=4)

        # Should keep both system messages + 2 recent
        system_count = sum(
            1 for item in window
            if item.message.role == "system"
        )
        assert system_count == 2


class TestSerialization:
    """Test serialization methods."""

    def test_to_list(self, history_with_messages: ChatHistory):
        """Test exporting to list."""
        items = history_with_messages.to_list()

        assert len(items) == 3
        # Should be a deep copy
        items[0].message.content = "Modified"
        assert history_with_messages.get_messages()[0].message.content != "Modified"

    def test_from_list(self):
        """Test creating from list."""
        items = [
            ChatHistoryItem(
                message=ChatMessage(role="user", content="Hello")
            ),
            ChatHistoryItem(
                message=ChatMessage(role="assistant", content="Hi")
            ),
        ]

        history = ChatHistory.from_list(items)

        assert len(history) == 2
        assert history.get_messages()[0].message.content == "Hello"

    def test_from_list_deep_copy(self):
        """Test that from_list creates a deep copy."""
        items = [
            ChatHistoryItem(
                message=ChatMessage(role="user", content="Hello")
            ),
        ]

        history = ChatHistory.from_list(items)
        items[0].message.content = "Modified"

        assert history.get_messages()[0].message.content == "Hello"


class TestCompression:
    """Test history compression."""

    def test_compress(self, history: ChatHistory):
        """Test compressing history."""
        # Add many messages
        history.add_system_message("System prompt")
        for i in range(15):
            history.add_user_message(f"User {i}")
            history.add_assistant_message(f"Assistant {i}")

        initial_len = len(history)
        assert initial_len == 31  # 1 system + 30 user/assistant

        # Compress with a simple summarizer
        def summarizer(items):
            return f"Summary of {len(items)} messages"

        history.compress(summarizer=summarizer, keep_recent=10)

        # Should have 1 summary + 10 recent
        assert len(history) == 11
        assert history.get_messages()[0].is_summarized is True
        assert "Summary of" in history.get_messages()[0].message.content

    def test_compress_not_needed(self, history_with_messages: ChatHistory):
        """Test that compress does nothing if not needed."""
        def summarizer(items):
            return "Summary"

        history_with_messages.compress(summarizer=summarizer, keep_recent=10)

        # Should be unchanged
        assert len(history_with_messages) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

