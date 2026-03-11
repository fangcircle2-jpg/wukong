"""
Session manager implementation.

Handles session lifecycle, persistence, and CLI commands support.
Uses the new storage layer for persistence.
"""

from copy import deepcopy
from datetime import datetime
from pathlib import Path

from wukong.core.session.models import (
    HistoryItem,
    Message,
    Part,
    Session,
    SessionIndex,
    SessionSummary,
)
from wukong.core.session.storage import StorageManager
from wukong.core.utils.id import generate_session_id

# Type alias
ChatHistoryItem = HistoryItem


class SessionManager:
    """Session manager.

    Responsible for:
    - Session lifecycle (CRUD)
    - Persistence via StorageManager
    - CLI commands support (ls, resume, fork)
    """

    def __init__(self, workspace_directory: str | Path | None = None):
        """Initialize session manager.

        Args:
            workspace_directory: Project root directory. Defaults to current working directory.
        """
        if workspace_directory is None:
            workspace_directory = Path.cwd()
        self.workspace_directory = Path(workspace_directory)
        
        # Initialize storage manager
        self._storage = StorageManager(self.workspace_directory)
        self._storage.ensure_storage_dirs()
        
        # Cache for current session index
        self._index: SessionIndex = self._storage.get_session_index()

    @property
    def project_id(self) -> str:
        """Get project ID for current workspace."""
        return self._storage.project_id

    @property
    def storage(self) -> StorageManager:
        """Get storage manager for direct access."""
        return self._storage

    # ========================================
    # Session Lifecycle
    # ========================================

    def create_session(
        self,
        title: str | None = None,
        model_name: str | None = None,
    ) -> Session:
        """Create a new session.

        Args:
            title: Session title. Auto-generated if not provided.
            model_name: LLM model name.

        Returns:
            New session instance.
        """
        now = datetime.now()
        session = self._storage.create_session(
            title=title or f"Session {now.strftime('%Y-%m-%d %H:%M')}",
            model_name=model_name,
        )
        
        # Update index cache
        self._index = self._storage.get_session_index()
        self._index.set_active(session.session_id)
        self._storage.sessions.save_index(self.project_id, self._index)

        return session

    def get_session(self, session_id: str) -> Session | None:
        """Get session by ID.

        Args:
            session_id: Session ID.

        Returns:
            Session if found, None otherwise.
        """
        return self._storage.get_session(session_id)

    def save_session(self, session: Session) -> None:
        """Save session to disk.

        Args:
            session: Session to save.
        """
        self._storage.save_session(session)
        # Refresh index cache
        self._index = self._storage.get_session_index()

    def delete_session(self, session_id: str, cascade: bool = True) -> bool:
        """Delete session.

        Args:
            session_id: Session ID to delete.
            cascade: If True, also delete all messages and parts.

        Returns:
            True if deleted, False if not found.
        """
        result = self._storage.delete_session(session_id, cascade=cascade)
        if result:
            self._index = self._storage.get_session_index()
        return result

    # ========================================
    # Message Operations
    # ========================================

    def add_message(self, session: Session, message: Message) -> Message:
        """Add a message to a session.
        
        Args:
            session: Session to add message to.
            message: Message to add.
            
        Returns:
            The saved message.
        """
        # Ensure message has correct session_id
        message.session_id = session.session_id
        
        # Save message
        self._storage.save_message(message)
        
        # Update session message count
        session.increment_message_count()
        self.save_session(session)
        
        return message

    def get_message(self, session_id: str, message_id: str) -> Message | None:
        """Get message by ID."""
        return self._storage.get_message(session_id, message_id)

    def get_messages(self, session_id: str) -> list[Message]:
        """Get all messages for a session."""
        return self._storage.list_messages(session_id)

    def delete_message(
        self, session: Session, message_id: str, cascade: bool = True
    ) -> bool:
        """Delete a message from a session.
        
        Args:
            session: Session containing the message.
            message_id: Message ID to delete.
            cascade: If True, also delete all parts.
            
        Returns:
            True if deleted.
        """
        result = self._storage.delete_message(
            session.session_id, message_id, cascade=cascade
        )
        if result:
            session.decrement_message_count()
            self.save_session(session)
        return result

    # ========================================
    # Part Operations
    # ========================================

    def add_part(self, message: Message, part: Part) -> Part:
        """Add a part to a message.
        
        Args:
            message: Message to add part to.
            part: Part to add.
            
        Returns:
            The saved part.
        """
        # Ensure part has correct message_id
        part.message_id = message.message_id
        
        # Save part
        self._storage.save_part(part)
        
        # Update message part_ids
        message.add_part_id(part.part_id)
        self._storage.save_message(message)
        
        return part

    def get_part(self, message_id: str, part_id: str) -> Part | None:
        """Get part by ID."""
        return self._storage.get_part(message_id, part_id)

    def get_parts(self, message: Message) -> list[Part]:
        """Get all parts for a message in order."""
        return self._storage.get_parts_by_ids(message.message_id, message.part_ids)

    def delete_part(self, message: Message, part_id: str) -> bool:
        """Delete a part from a message.
        
        Args:
            message: Message containing the part.
            part_id: Part ID to delete.
            
        Returns:
            True if deleted.
        """
        result = self._storage.delete_part(message.message_id, part_id)
        if result and part_id in message.part_ids:
            message.part_ids.remove(part_id)
            message.touch()
            self._storage.save_message(message)
        return result

    # ========================================
    # CLI Commands Support
    # ========================================

    def list_sessions(
        self,
        limit: int = 20,
        workspace_filter: bool = False,
    ) -> list[SessionSummary]:
        """List sessions.

        Args:
            limit: Maximum number of sessions to return.
            workspace_filter: If True, only return sessions from current workspace.

        Returns:
            List of session summaries, sorted by updated_at (newest first).
        """
        sessions = self._storage.list_sessions()

        if workspace_filter:
            workspace_str = str(self.workspace_directory)
            sessions = [s for s in sessions if s.workspace_directory == workspace_str]

        return sessions[:limit]

    def resume_session(self, session_id: str | None = None) -> Session | None:
        """Resume a session.

        Args:
            session_id: Session ID to resume. If None, resume the last active session.

        Returns:
            Resumed session if found, None otherwise.
        """
        if session_id is None:
            session_id = self._index.last_active_session_id

        if session_id is None:
            return None

        session = self.get_session(session_id)
        if session is None:
            return None

        # Mark as active
        session.is_active = True
        self._index.set_active(session_id)
        self._storage.sessions.save_index(self.project_id, self._index)

        return session

    def fork_session(
        self,
        session_id: str,
        new_title: str | None = None,
    ) -> Session | None:
        """Fork (copy) a session.

        Creates a new session with copies of all messages and parts.

        Args:
            session_id: Source session ID.
            new_title: Title for the new session.

        Returns:
            New forked session if source found, None otherwise.
        """
        source_session = self.get_session(session_id)
        if source_session is None:
            return None

        now = datetime.now()

        # Generate title
        if new_title is None:
            new_title = f"{source_session.title} (fork)"

        # Create new session
        new_session = Session(
            session_id=generate_session_id(),
            project_id=self.project_id,
            title=new_title,
            workspace_directory=source_session.workspace_directory,
            message_count=0,  # Will be updated as we copy messages
            created_at=now,
            updated_at=now,
            mode=source_session.mode,
            model_name=source_session.model_name,
            usage=deepcopy(source_session.usage),
            is_active=True,
            parent_session_id=session_id,
        )
        self._storage.save_session(new_session)

        # Copy all messages and their parts
        source_messages = self.get_messages(session_id)
        for source_msg in source_messages:
            # Create new message with new IDs
            new_message = Message(
                session_id=new_session.session_id,
                role=source_msg.role,
                tool_call_id=source_msg.tool_call_id,
                name=source_msg.name,
                context_items=deepcopy(source_msg.context_items),
                is_gathering_context=source_msg.is_gathering_context,
                conversation_summary=source_msg.conversation_summary,
                is_summarized=source_msg.is_summarized,
                part_ids=[],  # Will be populated as we copy parts
                created_at=now,
                updated_at=now,
            )
            self._storage.save_message(new_message)
            
            # Copy parts
            source_parts = self.get_parts(source_msg)
            for source_part in source_parts:
                new_part = Part(
                    message_id=new_message.message_id,
                    part_type=source_part.part_type,
                    data=deepcopy(source_part.data),
                    created_at=now,
                    updated_at=now,
                )
                self._storage.save_part(new_part)
                new_message.add_part_id(new_part.part_id)
            
            # Save message with updated part_ids
            self._storage.save_message(new_message)
            new_session.increment_message_count()

        # Save session with updated message_count
        self._storage.save_session(new_session)

        # Update index
        self._index = self._storage.get_session_index()
        self._index.set_active(new_session.session_id)
        self._storage.sessions.save_index(self.project_id, self._index)

        return new_session

    def get_last_active_session_id(self) -> str | None:
        """Get the last active session ID."""
        return self._index.last_active_session_id

    # ========================================
    # Title Management
    # ========================================

    def update_title_from_message(self, session: Session, user_message: str) -> None:
        """Update session title from the first user message.

        Only updates if the title is auto-generated (starts with "Session").

        Args:
            session: Session to update.
            user_message: User message content.
        """
        if session.title.startswith("Session "):
            # Extract first 30 characters as title
            title = user_message.strip()[:30]
            if len(user_message.strip()) > 30:
                title += "..."
            session.title = title

    # ========================================
    # Convenience Methods
    # ========================================

    def get_message_with_parts(
        self, session_id: str, message_id: str
    ) -> tuple[Message | None, list[Part]]:
        """Get a message with all its parts."""
        return self._storage.get_message_with_parts(session_id, message_id)

    # ========================================
    # HistoryItem Conversion
    # ========================================

    def save_history_item(self, session: Session, item: HistoryItem) -> Message:
        """Save a HistoryItem as Message + Parts.
        
        Converts in-memory HistoryItem to persistent Message and Parts.
        
        Args:
            session: Session to save to.
            item: HistoryItem to save.
            
        Returns:
            The saved Message.
        """
        message, parts = item.to_message_and_parts(session.session_id)
        
        # Save message
        self._storage.save_message(message)
        
        # Save parts
        for part in parts:
            self._storage.save_part(part)
        
        # Update session message count
        session.increment_message_count()
        self.save_session(session)
        
        return message

    def load_history_item(
        self, session_id: str, message_id: str
    ) -> HistoryItem | None:
        """Load a HistoryItem from Message + Parts.
        
        Args:
            session_id: Session ID.
            message_id: Message ID.
            
        Returns:
            HistoryItem if found, None otherwise.
        """
        message, parts = self.get_message_with_parts(session_id, message_id)
        if message is None:
            return None
        return HistoryItem.from_message_and_parts(message, parts)

    def load_history_items(self, session_id: str) -> list[HistoryItem]:
        """Load all HistoryItems for a session.
        
        Args:
            session_id: Session ID.
            
        Returns:
            List of HistoryItems in chronological order.
        """
        messages = self._storage.list_messages(session_id)
        items: list[HistoryItem] = []
        
        for message in messages:
            parts = self._storage.get_parts_by_ids(message.message_id, message.part_ids)
            item = HistoryItem.from_message_and_parts(message, parts)
            items.append(item)
        
        return items

    def save_history_items(
        self, session: Session, items: list[HistoryItem]
    ) -> list[Message]:
        """Save multiple HistoryItems.
        
        Note: This replaces all existing messages in the session.
        
        Args:
            session: Session to save to.
            items: List of HistoryItems to save.
            
        Returns:
            List of saved Messages.
        """
        # Delete existing messages
        existing_messages = self._storage.list_messages(session.session_id)
        for msg in existing_messages:
            self._storage.delete_message(session.session_id, msg.message_id, cascade=True)
        
        # Reset message count
        session.message_count = 0
        
        # Save new items
        messages: list[Message] = []
        for item in items:
            message = self.save_history_item(session, item)
            messages.append(message)
        
        return messages
