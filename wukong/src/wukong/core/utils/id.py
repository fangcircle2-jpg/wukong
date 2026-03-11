"""
ID generation utilities.

Generates unique IDs with format: {prefix}_{timestamp_hex}{random_base62}

Example: msg_018d5a2b3c4d1AbCdEf1234567

Format breakdown:
- prefix: 3-4 chars (ses_, msg_, prt_)
- timestamp: 6 bytes (48 bits) millisecond timestamp as 12 hex chars
- random: 14 chars base62 random string

Total length: prefix(3-4) + "_"(1) + timestamp(12) + random(14) = 30-31 chars
"""

import hashlib
import secrets
import time
from pathlib import Path

# Base62 character set: 0-9, a-z, A-Z
BASE62_CHARS = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

# ID prefixes
PREFIX_PROJECT = "prj"
PREFIX_SESSION = "ses"
PREFIX_MESSAGE = "msg"
PREFIX_PART = "prt"

# Configuration
TIMESTAMP_BYTES = 6  # 48 bits for millisecond timestamp
RANDOM_LENGTH = 14   # 14 chars of base62 random


def _get_timestamp_hex() -> str:
    """Get current timestamp as hex string.
    
    Uses millisecond precision, truncated to 6 bytes (48 bits).
    This gives us unique timestamps until year 10889.
    
    Returns:
        12-character hex string representing millisecond timestamp.
    """
    # Get current time in milliseconds
    ms_timestamp = int(time.time() * 1000)
    
    # Convert to 6 bytes (48 bits) and format as hex
    # Mask to 48 bits to ensure consistent length
    ms_timestamp = ms_timestamp & 0xFFFFFFFFFFFF
    
    # Format as 12-character hex string (zero-padded)
    return f"{ms_timestamp:012x}"


def _get_random_base62(length: int = RANDOM_LENGTH) -> str:
    """Generate random base62 string.
    
    Args:
        length: Number of characters to generate.
        
    Returns:
        Random string using base62 characters.
    """
    return "".join(secrets.choice(BASE62_CHARS) for _ in range(length))


def generate_id(prefix: str) -> str:
    """Generate a unique ID with the given prefix.
    
    Format: {prefix}_{timestamp_hex}{random_base62}
    
    Args:
        prefix: ID prefix (e.g., "ses", "msg", "prt").
        
    Returns:
        Unique ID string.
        
    Example:
        >>> generate_id("msg")
        'msg_018d5a2b3c4d1AbCdEf1234567'
    """
    timestamp_hex = _get_timestamp_hex()
    random_part = _get_random_base62()
    return f"{prefix}_{timestamp_hex}{random_part}"


def generate_session_id() -> str:
    """Generate a unique session ID.
    
    Format: ses_{timestamp_hex}{random_base62}
    
    Returns:
        Unique session ID.
        
    Example:
        >>> generate_session_id()
        'ses_018d5a2b3c4d1AbCdEf1234567'
    """
    return generate_id(PREFIX_SESSION)


def generate_message_id() -> str:
    """Generate a unique message ID.
    
    Format: msg_{timestamp_hex}{random_base62}
    
    Returns:
        Unique message ID.
        
    Example:
        >>> generate_message_id()
        'msg_018d5a2b3c4d1AbCdEf1234567'
    """
    return generate_id(PREFIX_MESSAGE)


def generate_part_id() -> str:
    """Generate a unique part ID.
    
    Format: prt_{timestamp_hex}{random_base62}
    
    Returns:
        Unique part ID.
        
    Example:
        >>> generate_part_id()
        'prt_018d5a2b3c4d1AbCdEf1234567'
    """
    return generate_id(PREFIX_PART)


def generate_project_id(workspace_path: str | Path) -> str:
    """Generate a deterministic project ID from workspace path.
    
    The same workspace path always generates the same project ID.
    
    Format: prj_{sha256_hash[:16]}
    
    Args:
        workspace_path: Workspace directory path.
        
    Returns:
        Deterministic project ID.
        
    Example:
        >>> generate_project_id("d:\\code\\cli")
        'prj_a1b2c3d4e5f6g7h8'
        >>> generate_project_id("D:\\Code\\CLI")  # Same ID (case-insensitive on Windows)
        'prj_a1b2c3d4e5f6g7h8'
    """
    # Normalize path: resolve to absolute, convert to lowercase for case-insensitive systems
    path = Path(workspace_path).resolve()
    
    # Use lowercase string for consistent hashing across platforms
    # This ensures D:\Code\CLI and d:\code\cli produce the same ID on Windows
    normalized = str(path).lower()
    
    # Compute SHA256 hash
    hash_bytes = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    
    # Take first 16 characters
    return f"{PREFIX_PROJECT}_{hash_bytes[:16]}"


def parse_id(id_string: str) -> tuple[str, int, str] | None:
    """Parse an ID string into its components.
    
    Args:
        id_string: ID to parse (e.g., "msg_018d5a2b3c4d1AbCdEf1234567").
        
    Returns:
        Tuple of (prefix, timestamp_ms, random_part) if valid, None otherwise.
        
    Example:
        >>> parse_id("msg_018d5a2b3c4d1AbCdEf1234567")
        ('msg', 1704067200000, '1AbCdEf1234567')
    """
    try:
        # Split by underscore
        if "_" not in id_string:
            return None
            
        prefix, rest = id_string.split("_", 1)
        
        # Validate length
        if len(rest) != 12 + RANDOM_LENGTH:  # timestamp(12) + random(14)
            return None
        
        # Extract parts
        timestamp_hex = rest[:12]
        random_part = rest[12:]
        
        # Parse timestamp
        timestamp_ms = int(timestamp_hex, 16)
        
        return (prefix, timestamp_ms, random_part)
    except (ValueError, IndexError):
        return None


def get_timestamp_from_id(id_string: str) -> int | None:
    """Extract timestamp (milliseconds) from an ID.
    
    Args:
        id_string: ID to extract timestamp from.
        
    Returns:
        Timestamp in milliseconds, or None if invalid.
        
    Example:
        >>> get_timestamp_from_id("msg_018d5a2b3c4d1AbCdEf1234567")
        1704067200000
    """
    parsed = parse_id(id_string)
    return parsed[1] if parsed else None
