"""
Mention Parser for CLI.

Parses @mentions in user input text.
This is a CLI-layer responsibility since it handles user input parsing
before passing to the Core layer.
"""

import re
from dataclasses import dataclass, field


@dataclass
class Mention:
    """Parsed mention from user input.
    
    Represents a single @mention like "@file src/main.py".
    
    Attributes:
        provider: Provider id (e.g., "file", "url")
        query: The argument/query part (e.g., "src/main.py")
        raw: Original text including @ symbol
        start: Start position in original text
        end: End position in original text
    """
    
    provider: str
    query: str
    raw: str
    start: int
    end: int


@dataclass
class ParseResult:
    """Result of parsing mentions from text.
    
    Attributes:
        mentions: List of parsed mentions
        clean_text: Text with mentions removed (trimmed)
    """
    
    mentions: list[Mention] = field(default_factory=list)
    clean_text: str = ""


class MentionParser:
    """Parser for @mentions in user input.
    
    Parses text to extract @mentions like "@file path/to/file".
    
    Supported syntax:
    - @provider query          : Simple format
    - @provider "query"        : Query with spaces (quoted)
    - @provider 'query'        : Query with spaces (single quoted)
    
    Examples:
        parser = MentionParser()
        
        # Simple mention
        result = parser.parse("看看 @file src/main.py 这个文件")
        # mentions: [Mention(provider="file", query="src/main.py")]
        # clean_text: "看看 这个文件"
        
        # Multiple mentions
        result = parser.parse("@file a.py @file b.py 比较一下")
        # mentions: [Mention(..., query="a.py"), Mention(..., query="b.py")]
        
        # Quoted path (with spaces)
        result = parser.parse('@file "path to/my file.py"')
        # mentions: [Mention(..., query="path to/my file.py")]
    """
    
    # Regex pattern for @mentions
    # Matches @word followed by optional quoted or unquoted argument
    SIMPLE_PATTERN = re.compile(
        r'@(\w+)'                           # @provider
        r'(?:'
        r'\s+"([^"]+)"'                     # "quoted query"
        r'|\s+\'([^\']+)\''                 # 'quoted query'  
        r'|\s+([^\s@]+)'                    # unquoted (until space or @)
        r')?'
    )
    
    def parse(self, text: str) -> ParseResult:
        """Parse @mentions from text.
        
        Args:
            text: Input text containing @mentions.
            
        Returns:
            ParseResult with extracted mentions and cleaned text.
        """
        if not text:
            return ParseResult(mentions=[], clean_text="")
        
        mentions: list[Mention] = []
        
        # Find all mentions
        for match in self.SIMPLE_PATTERN.finditer(text):
            provider = match.group(1)
            
            # Get query from one of the capture groups
            query = match.group(2) or match.group(3) or match.group(4) or ""
            
            mention = Mention(
                provider=provider,
                query=query,
                raw=match.group(0),
                start=match.start(),
                end=match.end(),
            )
            mentions.append(mention)
        
        # Build clean text by removing mentions
        clean_text = self._remove_mentions(text, mentions)
        
        return ParseResult(mentions=mentions, clean_text=clean_text)
    
    def _remove_mentions(self, text: str, mentions: list[Mention]) -> str:
        """Remove mentions from text and clean up whitespace.
        
        Args:
            text: Original text.
            mentions: List of mentions to remove.
            
        Returns:
            Cleaned text with mentions removed.
        """
        if not mentions:
            return text.strip()
        
        # Sort mentions by start position (reverse order for safe removal)
        sorted_mentions = sorted(mentions, key=lambda m: m.start, reverse=True)
        
        result = text
        for mention in sorted_mentions:
            # Remove the mention
            result = result[:mention.start] + result[mention.end:]
        
        # Clean up multiple spaces and trim
        result = re.sub(r'\s+', ' ', result).strip()
        
        return result
    
    def extract_provider_ids(self, text: str) -> list[str]:
        """Extract just the provider IDs from text.
        
        Convenience method when you only need provider names.
        
        Args:
            text: Input text.
            
        Returns:
            List of provider IDs found (may contain duplicates).
        """
        result = self.parse(text)
        return [m.provider for m in result.mentions]
    
    def has_mentions(self, text: str) -> bool:
        """Check if text contains any @mentions.
        
        Args:
            text: Input text.
            
        Returns:
            True if text contains at least one @mention.
        """
        return bool(self.SIMPLE_PATTERN.search(text))

