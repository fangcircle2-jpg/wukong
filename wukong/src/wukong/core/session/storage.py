"""
Storage layer for session, message, and part persistence.

Directory structure:
.wukong/storage/
├── session/{project_id}/
│   └── {session_id}.json
├── message/{session_id}/
│   └── {message_id}.json
└── part/{message_id}/
    └── {part_id}.json
"""

import json
from pathlib import Path
from typing import TypeVar, Generic

from pydantic import BaseModel

from wukong.core.session.models import (
    Message,
    Part,
    Session,
    SessionIndex,
    SessionSummary,
)
from wukong.core.utils.id import generate_project_id

# Type variable for generic storage
T = TypeVar("T", bound=BaseModel)


class BaseStorage(Generic[T]):
    """Base storage class with common file operations."""

    def __init__(self, base_path: Path):
        """Initialize base storage.
        
        Args:
            base_path: Base directory for storage.
        """
        self.base_path = base_path

    def _ensure_dir(self, path: Path) -> None:
        """Ensure directory exists."""
        path.mkdir(parents=True, exist_ok=True)

    def _read_json(self, file_path: Path) -> dict | None:
        """Read JSON file."""
        if not file_path.exists():
            return None
        try:
            with open(file_path, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return None

    def _write_json(self, file_path: Path, data: dict) -> None:
        """Write JSON file."""
        self._ensure_dir(file_path.parent)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2, default=str)

    def _delete_file(self, file_path: Path) -> bool:
        """Delete file if exists."""
        if file_path.exists():
            file_path.unlink()
            return True
        return False

    def _list_json_files(self, directory: Path) -> list[Path]:
        """List all JSON files in directory."""
        if not directory.exists():
            return []
        return list(directory.glob("*.json"))


class SessionStorage(BaseStorage[Session]):
    """Storage for Session objects.
    
    Path: .wukong/storage/session/{project_id}/{session_id}.json
    """

    INDEX_FILE = "index.json"

    def __init__(self, storage_root: Path):
        """Initialize session storage.
        
        Args:
            storage_root: Root storage directory (.wu-zhao/storage).
        """
        super().__init__(storage_root / "session")
        self._index: SessionIndex | None = None

    def _get_session_dir(self, project_id: str) -> Path:
        """Get session directory for a project."""
        return self.base_path / project_id

    def _get_session_file(self, project_id: str, session_id: str) -> Path:
        """Get session file path."""
        return self._get_session_dir(project_id) / f"{session_id}.json"

    def _get_index_file(self, project_id: str) -> Path:
        """Get index file path for a project."""
        return self._get_session_dir(project_id) / self.INDEX_FILE

    def save(self, session: Session) -> None:
        """Save session to disk."""
        session.touch()
        file_path = self._get_session_file(session.project_id, session.session_id)
        self._write_json(file_path, session.model_dump(mode="json"))
        
        # Update index
        self._update_index(session)

    def load(self, project_id: str, session_id: str) -> Session | None:
        """Load session from disk."""
        file_path = self._get_session_file(project_id, session_id)
        data = self._read_json(file_path)
        if data is None:
            return None
        try:
            return Session.model_validate(data)
        except ValueError:
            return None

    def delete(self, project_id: str, session_id: str) -> bool:
        """Delete session from disk."""
        file_path = self._get_session_file(project_id, session_id)
        result = self._delete_file(file_path)
        if result:
            self._remove_from_index(project_id, session_id)
        return result

    def list_sessions(self, project_id: str) -> list[Session]:
        """List all sessions for a project."""
        session_dir = self._get_session_dir(project_id)
        sessions = []
        for file_path in self._list_json_files(session_dir):
            if file_path.name == self.INDEX_FILE:
                continue
            data = self._read_json(file_path)
            if data:
                try:
                    sessions.append(Session.model_validate(data))
                except ValueError:
                    pass
        return sessions

    def load_index(self, project_id: str) -> SessionIndex:
        """Load session index for a project."""
        file_path = self._get_index_file(project_id)
        data = self._read_json(file_path)
        if data is None:
            return SessionIndex()
        try:
            return SessionIndex.model_validate(data)
        except ValueError:
            return SessionIndex()

    def save_index(self, project_id: str, index: SessionIndex) -> None:
        """Save session index for a project."""
        file_path = self._get_index_file(project_id)
        self._write_json(file_path, index.model_dump(mode="json"))

    def _update_index(self, session: Session) -> None:
        """Update index with session info."""
        index = self.load_index(session.project_id)
        index.add_session(session)
        self.save_index(session.project_id, index)

    def _remove_from_index(self, project_id: str, session_id: str) -> None:
        """Remove session from index."""
        index = self.load_index(project_id)
        index.remove_session(session_id)
        self.save_index(project_id, index)


class MessageStorage(BaseStorage[Message]):
    """Storage for Message objects.
    
    Path: .wukong/storage/message/{session_id}/{message_id}.json
    """

    def __init__(self, storage_root: Path):
        """Initialize message storage.
        
        Args:
            storage_root: Root storage directory (.wu-zhao/storage).
        """
        super().__init__(storage_root / "message")

    def _get_message_dir(self, session_id: str) -> Path:
        """Get message directory for a session."""
        return self.base_path / session_id

    def _get_message_file(self, session_id: str, message_id: str) -> Path:
        """Get message file path."""
        return self._get_message_dir(session_id) / f"{message_id}.json"

    def save(self, message: Message) -> None:
        """Save message to disk."""
        message.touch()
        file_path = self._get_message_file(message.session_id, message.message_id)
        self._write_json(file_path, message.model_dump(mode="json"))

    def load(self, session_id: str, message_id: str) -> Message | None:
        """Load message from disk."""
        file_path = self._get_message_file(session_id, message_id)
        data = self._read_json(file_path)
        if data is None:
            return None
        try:
            return Message.model_validate(data)
        except ValueError:
            return None

    def delete(self, session_id: str, message_id: str) -> bool:
        """Delete message from disk."""
        file_path = self._get_message_file(session_id, message_id)
        return self._delete_file(file_path)

    def list_messages(self, session_id: str) -> list[Message]:
        """List all messages for a session, sorted by created_at."""
        message_dir = self._get_message_dir(session_id)
        messages = []
        for file_path in self._list_json_files(message_dir):
            data = self._read_json(file_path)
            if data:
                try:
                    messages.append(Message.model_validate(data))
                except ValueError:
                    pass
        # Sort by created_at
        messages.sort(key=lambda m: m.created_at)
        return messages

    def delete_all(self, session_id: str) -> int:
        """Delete all messages for a session.
        
        Returns:
            Number of messages deleted.
        """
        message_dir = self._get_message_dir(session_id)
        count = 0
        for file_path in self._list_json_files(message_dir):
            if self._delete_file(file_path):
                count += 1
        # Try to remove empty directory
        try:
            message_dir.rmdir()
        except OSError:
            pass
        return count


class PartStorage(BaseStorage[Part]):
    """Storage for Part objects.
    
    Path: .wukong/storage/part/{message_id}/{part_id}.json
    """

    def __init__(self, storage_root: Path):
        """Initialize part storage.
        
        Args:
            storage_root: Root storage directory (.wu-zhao/storage).
        """
        super().__init__(storage_root / "part")

    def _get_part_dir(self, message_id: str) -> Path:
        """Get part directory for a message."""
        return self.base_path / message_id

    def _get_part_file(self, message_id: str, part_id: str) -> Path:
        """Get part file path."""
        return self._get_part_dir(message_id) / f"{part_id}.json"

    def save(self, part: Part) -> None:
        """Save part to disk."""
        part.touch()
        file_path = self._get_part_file(part.message_id, part.part_id)
        self._write_json(file_path, part.model_dump(mode="json"))

    def load(self, message_id: str, part_id: str) -> Part | None:
        """Load part from disk."""
        file_path = self._get_part_file(message_id, part_id)
        data = self._read_json(file_path)
        if data is None:
            return None
        try:
            return Part.model_validate(data)
        except ValueError:
            return None

    def delete(self, message_id: str, part_id: str) -> bool:
        """Delete part from disk."""
        file_path = self._get_part_file(message_id, part_id)
        return self._delete_file(file_path)

    def list_parts(self, message_id: str) -> list[Part]:
        """List all parts for a message, sorted by created_at."""
        part_dir = self._get_part_dir(message_id)
        parts = []
        for file_path in self._list_json_files(part_dir):
            data = self._read_json(file_path)
            if data:
                try:
                    parts.append(Part.model_validate(data))
                except ValueError:
                    pass
        # Sort by created_at
        parts.sort(key=lambda p: p.created_at)
        return parts

    def load_parts_by_ids(self, message_id: str, part_ids: list[str]) -> list[Part]:
        """Load parts by IDs in the specified order."""
        parts = []
        for part_id in part_ids:
            part = self.load(message_id, part_id)
            if part:
                parts.append(part)
        return parts

    def delete_all(self, message_id: str) -> int:
        """Delete all parts for a message.
        
        Returns:
            Number of parts deleted.
        """
        part_dir = self._get_part_dir(message_id)
        count = 0
        for file_path in self._list_json_files(part_dir):
            if self._delete_file(file_path):
                count += 1
        # Try to remove empty directory
        try:
            part_dir.rmdir()
        except OSError:
            pass
        return count


class StorageManager:
    """Unified storage manager for all storage types.
    
    Provides a single entry point for all storage operations.
    """

    STORAGE_DIR = ".wukong/storage"

    def __init__(self, workspace_directory: str | Path):
        """Initialize storage manager.
        
        Args:
            workspace_directory: Project workspace directory.
        """
        self.workspace_directory = Path(workspace_directory)
        self.storage_root = self.workspace_directory / self.STORAGE_DIR
        self.project_id = generate_project_id(workspace_directory)
        
        # Initialize sub-storages
        self.sessions = SessionStorage(self.storage_root)
        self.messages = MessageStorage(self.storage_root)
        self.parts = PartStorage(self.storage_root)

    def ensure_storage_dirs(self) -> None:
        """Ensure all storage directories exist."""
        self.storage_root.mkdir(parents=True, exist_ok=True)
        (self.storage_root / "session").mkdir(exist_ok=True)
        (self.storage_root / "message").mkdir(exist_ok=True)
        (self.storage_root / "part").mkdir(exist_ok=True)

    # ========================================
    # Session Operations
    # ========================================

    def create_session(self, title: str, model_name: str | None = None) -> Session:
        """Create and save a new session."""
        session = Session(
            project_id=self.project_id,
            title=title,
            workspace_directory=str(self.workspace_directory),
            model_name=model_name,
        )
        self.sessions.save(session)
        return session

    def get_session(self, session_id: str) -> Session | None:
        """Get session by ID."""
        return self.sessions.load(self.project_id, session_id)

    def save_session(self, session: Session) -> None:
        """Save session."""
        self.sessions.save(session)

    def delete_session(self, session_id: str, cascade: bool = True) -> bool:
        """Delete session.
        
        Args:
            session_id: Session ID to delete.
            cascade: If True, also delete all messages and parts.
        """
        if cascade:
            # Delete all messages (and their parts)
            messages = self.messages.list_messages(session_id)
            for message in messages:
                self.delete_message(session_id, message.message_id, cascade=True)
        
        return self.sessions.delete(self.project_id, session_id)

    def list_sessions(self) -> list[SessionSummary]:
        """List all sessions for current project."""
        index = self.sessions.load_index(self.project_id)
        return sorted(index.sessions, key=lambda s: s.updated_at, reverse=True)

    # ========================================
    # Message Operations
    # ========================================

    def save_message(self, message: Message) -> None:
        """Save message."""
        self.messages.save(message)

    def get_message(self, session_id: str, message_id: str) -> Message | None:
        """Get message by ID."""
        return self.messages.load(session_id, message_id)

    def delete_message(self, session_id: str, message_id: str, cascade: bool = True) -> bool:
        """Delete message.
        
        Args:
            session_id: Session ID.
            message_id: Message ID to delete.
            cascade: If True, also delete all parts.
        """
        if cascade:
            self.parts.delete_all(message_id)
        return self.messages.delete(session_id, message_id)

    def list_messages(self, session_id: str) -> list[Message]:
        """List all messages for a session."""
        return self.messages.list_messages(session_id)

    # ========================================
    # Part Operations
    # ========================================

    def save_part(self, part: Part) -> None:
        """Save part."""
        self.parts.save(part)

    def get_part(self, message_id: str, part_id: str) -> Part | None:
        """Get part by ID."""
        return self.parts.load(message_id, part_id)

    def delete_part(self, message_id: str, part_id: str) -> bool:
        """Delete part."""
        return self.parts.delete(message_id, part_id)

    def list_parts(self, message_id: str) -> list[Part]:
        """List all parts for a message."""
        return self.parts.list_parts(message_id)

    def get_parts_by_ids(self, message_id: str, part_ids: list[str]) -> list[Part]:
        """Get parts by IDs in order."""
        return self.parts.load_parts_by_ids(message_id, part_ids)

    # ========================================
    # Convenience Methods
    # ========================================

    def get_message_with_parts(
        self, session_id: str, message_id: str
    ) -> tuple[Message | None, list[Part]]:
        """Get message with all its parts."""
        message = self.get_message(session_id, message_id)
        if message is None:
            return None, []
        parts = self.get_parts_by_ids(message_id, message.part_ids)
        return message, parts

    def get_session_index(self) -> SessionIndex:
        """Get session index for current project."""
        return self.sessions.load_index(self.project_id)
