"""
Tests for SessionManager.

Run with: pytest tests/test_session_manager.py -v
"""

import tempfile
from pathlib import Path

import pytest

from wukong.core.session import (
    ChatMessage,
    HistoryItem,
    Part,
    PartType,
    Role,
    Session,
    SessionManager,
)


@pytest.fixture
def temp_workspace():
    """Create a temporary workspace directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def manager(temp_workspace: Path):
    """Create a SessionManager with temporary workspace."""
    return SessionManager(workspace_directory=temp_workspace)


class TestSessionLifecycle:
    """Test session CRUD operations."""

    def test_create_session(self, manager: SessionManager):
        """Test creating a new session."""
        session = manager.create_session(title="Test Session", model_name="gpt-4o")

        assert session.session_id is not None
        assert session.session_id.startswith("ses_")
        assert len(session.session_id) == 30  # ses_ + 12 hex + 14 random
        assert session.title == "Test Session"
        assert session.model_name == "gpt-4o"
        assert session.is_active is True
        assert session.message_count == 0
        assert session.project_id is not None

    def test_create_session_auto_title(self, manager: SessionManager):
        """Test creating session with auto-generated title."""
        session = manager.create_session()

        assert session.title.startswith("Session ")

    def test_get_session(self, manager: SessionManager):
        """Test getting a session by ID."""
        created = manager.create_session(title="Get Test")

        retrieved = manager.get_session(created.session_id)

        assert retrieved is not None
        assert retrieved.session_id == created.session_id
        assert retrieved.title == "Get Test"

    def test_get_session_not_found(self, manager: SessionManager):
        """Test getting a non-existent session."""
        result = manager.get_session("nonexistent")

        assert result is None

    def test_save_session(self, manager: SessionManager):
        """Test saving session updates."""
        session = manager.create_session(title="Save Test")

        # Add a message using the new API
        item = HistoryItem(
            message=ChatMessage(role="user", content="Hello!")
        )
        manager.save_history_item(session, item)

        # Reload and verify
        reloaded = manager.get_session(session.session_id)
        assert reloaded is not None
        assert reloaded.message_count == 1
        
        # Load history items
        items = manager.load_history_items(session.session_id)
        assert len(items) == 1
        assert items[0].message.content == "Hello!"

    def test_delete_session(self, manager: SessionManager):
        """Test deleting a session."""
        session = manager.create_session(title="Delete Test")
        session_id = session.session_id

        result = manager.delete_session(session_id)

        assert result is True
        assert manager.get_session(session_id) is None

    def test_delete_session_not_found(self, manager: SessionManager):
        """Test deleting a non-existent session."""
        result = manager.delete_session("nonexistent")

        assert result is False


class TestSessionCommands:
    """Test CLI commands support."""

    def test_list_sessions_empty(self, manager: SessionManager):
        """Test listing when no sessions exist."""
        sessions = manager.list_sessions()

        assert sessions == []

    def test_list_sessions(self, manager: SessionManager):
        """Test listing sessions."""
        manager.create_session(title="Session 1")
        manager.create_session(title="Session 2")
        manager.create_session(title="Session 3")

        sessions = manager.list_sessions()

        assert len(sessions) == 3
        # Should be sorted by updated_at descending (newest first)
        assert sessions[0].title == "Session 3"

    def test_list_sessions_limit(self, manager: SessionManager):
        """Test listing with limit."""
        for i in range(5):
            manager.create_session(title=f"Session {i}")

        sessions = manager.list_sessions(limit=3)

        assert len(sessions) == 3

    def test_resume_session(self, manager: SessionManager):
        """Test resuming a specific session."""
        session1 = manager.create_session(title="Session 1")
        manager.create_session(title="Session 2")

        resumed = manager.resume_session(session1.session_id)

        assert resumed is not None
        assert resumed.session_id == session1.session_id
        assert manager.get_last_active_session_id() == session1.session_id

    def test_resume_last_active(self, manager: SessionManager):
        """Test resuming the last active session."""
        manager.create_session(title="Session 1")
        session2 = manager.create_session(title="Session 2")

        # session2 should be the last active
        resumed = manager.resume_session()

        assert resumed is not None
        assert resumed.session_id == session2.session_id

    def test_resume_no_sessions(self, manager: SessionManager):
        """Test resuming when no sessions exist."""
        resumed = manager.resume_session()

        assert resumed is None

    def test_fork_session(self, manager: SessionManager):
        """Test forking a session."""
        original = manager.create_session(title="Original")
        
        # Add a message using the new API
        item = HistoryItem(
            message=ChatMessage(role="user", content="Original message")
        )
        manager.save_history_item(original, item)

        forked = manager.fork_session(original.session_id, new_title="Forked")

        assert forked is not None
        assert forked.session_id != original.session_id
        assert forked.title == "Forked"
        assert forked.parent_session_id == original.session_id
        assert forked.message_count == 1
        
        # Load forked history items
        forked_items = manager.load_history_items(forked.session_id)
        assert len(forked_items) == 1
        assert forked_items[0].message.content == "Original message"

    def test_fork_session_auto_title(self, manager: SessionManager):
        """Test forking with auto-generated title."""
        original = manager.create_session(title="Original")

        forked = manager.fork_session(original.session_id)

        assert forked is not None
        assert forked.title == "Original (fork)"

    def test_fork_session_not_found(self, manager: SessionManager):
        """Test forking a non-existent session."""
        result = manager.fork_session("nonexistent")

        assert result is None


class TestTitleManagement:
    """Test title auto-generation."""

    def test_update_title_from_message(self, manager: SessionManager):
        """Test updating title from first user message."""
        session = manager.create_session()  # Auto-generated title

        manager.update_title_from_message(session, "Help me refactor this code")

        assert session.title == "Help me refactor this code"

    def test_update_title_truncate(self, manager: SessionManager):
        """Test title truncation for long messages."""
        session = manager.create_session()

        long_message = "This is a very long message that should be truncated to 30 characters"
        manager.update_title_from_message(session, long_message)

        assert len(session.title) == 33  # 30 + "..."
        assert session.title.endswith("...")

    def test_update_title_skip_custom(self, manager: SessionManager):
        """Test that custom titles are not overwritten."""
        session = manager.create_session(title="My Custom Title")

        manager.update_title_from_message(session, "New message")

        assert session.title == "My Custom Title"


class TestPersistence:
    """Test persistence behavior."""

    def test_storage_root(self, temp_workspace: Path, manager: SessionManager):
        """Test that storage root is correct."""
        storage_root = temp_workspace / ".wukong" / "storage"
        assert manager._storage.storage_root == storage_root
        assert storage_root.exists()

    def test_session_file_created(self, manager: SessionManager):
        """Test that session file is created on save."""
        session = manager.create_session(title="File Test")

        # New path: storage/session/{project_id}/{session_id}.json
        session_dir = manager._storage.storage_root / "session" / session.project_id
        session_file = session_dir / f"{session.session_id}.json"
        assert session_file.exists()

    def test_index_file_created(self, manager: SessionManager):
        """Test that index file is created."""
        session = manager.create_session(title="Index Test")

        # New path: storage/session/{project_id}/index.json
        session_dir = manager._storage.storage_root / "session" / session.project_id
        index_file = session_dir / "index.json"
        assert index_file.exists()

    def test_index_updated_on_delete(self, manager: SessionManager):
        """Test that index is updated when session is deleted."""
        session = manager.create_session(title="Delete Test")
        manager.delete_session(session.session_id)

        sessions = manager.list_sessions()
        assert len(sessions) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

