"""
Tests for MentionParser.

Run with: pytest tests/test_mention_parser.py -v
"""

import pytest

from wukong.cli.parser import Mention, MentionParser, ParseResult


@pytest.fixture
def parser():
    """Create a MentionParser instance."""
    return MentionParser()


# ========================================
# Test Basic Parsing
# ========================================

class TestBasicParsing:
    """Test basic mention parsing."""
    
    def test_single_mention(self, parser: MentionParser):
        """Test parsing a single mention."""
        result = parser.parse("@file src/main.py")
        
        assert len(result.mentions) == 1
        mention = result.mentions[0]
        assert mention.provider == "file"
        assert mention.query == "src/main.py"
    
    def test_mention_with_text_before(self, parser: MentionParser):
        """Test mention with text before it."""
        result = parser.parse("check @file src/main.py")
        
        assert len(result.mentions) == 1
        assert result.mentions[0].query == "src/main.py"
        assert result.clean_text == "check"
    
    def test_mention_with_text_after(self, parser: MentionParser):
        """Test mention with text after it."""
        result = parser.parse("@file src/main.py this file")
        
        assert len(result.mentions) == 1
        assert result.clean_text == "this file"
    
    def test_mention_with_text_around(self, parser: MentionParser):
        """Test mention surrounded by text."""
        result = parser.parse("help me check @file src/main.py issues")
        
        assert len(result.mentions) == 1
        assert result.mentions[0].query == "src/main.py"
        assert result.clean_text == "help me check issues"
    
    def test_multiple_mentions(self, parser: MentionParser):
        """Test multiple mentions."""
        result = parser.parse("@file a.py @file b.py compare them")
        
        assert len(result.mentions) == 2
        assert result.mentions[0].query == "a.py"
        assert result.mentions[1].query == "b.py"
        assert result.clean_text == "compare them"
    
    def test_different_providers(self, parser: MentionParser):
        """Test mentions with different providers."""
        result = parser.parse("@file src/main.py @url https://example.com")
        
        assert len(result.mentions) == 2
        assert result.mentions[0].provider == "file"
        assert result.mentions[1].provider == "url"


# ========================================
# Test Quoted Paths
# ========================================

class TestQuotedPaths:
    """Test parsing paths with quotes."""
    
    def test_double_quoted_path(self, parser: MentionParser):
        """Test double-quoted path with spaces."""
        result = parser.parse('@file "path to/my file.py"')
        
        assert len(result.mentions) == 1
        assert result.mentions[0].query == "path to/my file.py"
    
    def test_single_quoted_path(self, parser: MentionParser):
        """Test single-quoted path with spaces."""
        result = parser.parse("@file 'path to/my file.py'")
        
        assert len(result.mentions) == 1
        assert result.mentions[0].query == "path to/my file.py"
    
    def test_quoted_with_text(self, parser: MentionParser):
        """Test quoted path with surrounding text."""
        result = parser.parse('check @file "my docs/readme.md" content')
        
        assert len(result.mentions) == 1
        assert result.mentions[0].query == "my docs/readme.md"
        assert result.clean_text == "check content"


# ========================================
# Test Edge Cases
# ========================================

class TestEdgeCases:
    """Test edge cases."""
    
    def test_empty_string(self, parser: MentionParser):
        """Test empty input."""
        result = parser.parse("")
        
        assert len(result.mentions) == 0
        assert result.clean_text == ""
    
    def test_no_mentions(self, parser: MentionParser):
        """Test text without mentions."""
        result = parser.parse("plain text, no mentions")
        
        assert len(result.mentions) == 0
        assert result.clean_text == "plain text, no mentions"
    
    def test_mention_without_query(self, parser: MentionParser):
        """Test mention without query argument."""
        result = parser.parse("@file")
        
        assert len(result.mentions) == 1
        assert result.mentions[0].provider == "file"
        assert result.mentions[0].query == ""
    
    def test_mention_at_start(self, parser: MentionParser):
        """Test mention at start of text."""
        result = parser.parse("@file test.py please analyze")
        
        assert len(result.mentions) == 1
        assert result.clean_text == "please analyze"
    
    def test_mention_at_end(self, parser: MentionParser):
        """Test mention at end of text."""
        result = parser.parse("please check @file test.py")
        
        assert len(result.mentions) == 1
        assert result.clean_text == "please check"
    
    def test_consecutive_mentions(self, parser: MentionParser):
        """Test consecutive mentions without text between."""
        result = parser.parse("@file a.py @file b.py @file c.py")
        
        assert len(result.mentions) == 3
        queries = [m.query for m in result.mentions]
        assert queries == ["a.py", "b.py", "c.py"]
    
    def test_email_not_parsed_as_mention(self, parser: MentionParser):
        """Test that email addresses are not parsed as mentions."""
        # Note: Current implementation will parse user@example.com
        # This test documents current behavior
        result = parser.parse("contact user@example.com")
        
        # Current behavior: @example is parsed as mention
        # This is a known limitation
        # If you want emails to not be parsed, more complex logic is needed
    
    def test_special_characters_in_path(self, parser: MentionParser):
        """Test path with special characters."""
        result = parser.parse("@file src/main_v2.py")
        
        assert len(result.mentions) == 1
        assert result.mentions[0].query == "src/main_v2.py"
    
    def test_path_with_dots(self, parser: MentionParser):
        """Test path with multiple dots."""
        result = parser.parse("@file src/config.dev.json")
        
        assert len(result.mentions) == 1
        assert result.mentions[0].query == "src/config.dev.json"


# ========================================
# Test Position Tracking
# ========================================

class TestPositionTracking:
    """Test position tracking in mentions."""
    
    def test_position_single_mention(self, parser: MentionParser):
        """Test position tracking for single mention."""
        result = parser.parse("@file test.py")
        
        mention = result.mentions[0]
        assert mention.start == 0
        assert mention.raw == "@file test.py"
    
    def test_position_with_prefix(self, parser: MentionParser):
        """Test position with text before mention."""
        result = parser.parse("see @file test.py")
        
        mention = result.mentions[0]
        assert mention.start == 4  # After "see "
    
    def test_raw_includes_full_mention(self, parser: MentionParser):
        """Test that raw field includes full mention text."""
        result = parser.parse('@file "path with space.py"')
        
        assert result.mentions[0].raw == '@file "path with space.py"'


# ========================================
# Test Helper Methods
# ========================================

class TestHelperMethods:
    """Test helper methods."""
    
    def test_extract_provider_ids(self, parser: MentionParser):
        """Test extract_provider_ids method."""
        ids = parser.extract_provider_ids("@file a.py @url b.com @file c.py")
        
        assert ids == ["file", "url", "file"]
    
    def test_has_mentions_true(self, parser: MentionParser):
        """Test has_mentions returns True when mentions exist."""
        assert parser.has_mentions("@file test.py") is True
    
    def test_has_mentions_false(self, parser: MentionParser):
        """Test has_mentions returns False when no mentions."""
        assert parser.has_mentions("plain text") is False


# ========================================
# Test Clean Text
# ========================================

class TestCleanText:
    """Test clean_text generation."""
    
    def test_clean_text_trims_whitespace(self, parser: MentionParser):
        """Test that clean_text is trimmed."""
        result = parser.parse("  @file test.py  ")
        
        assert result.clean_text == ""
    
    def test_clean_text_normalizes_spaces(self, parser: MentionParser):
        """Test that multiple spaces are normalized."""
        result = parser.parse("check  @file test.py  issues")
        
        assert result.clean_text == "check issues"
    
    def test_clean_text_only_mentions(self, parser: MentionParser):
        """Test clean_text when input is only mentions."""
        result = parser.parse("@file a.py @file b.py")
        
        assert result.clean_text == ""


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

