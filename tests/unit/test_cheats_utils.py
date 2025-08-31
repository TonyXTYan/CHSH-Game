"""Unit tests for cheats utility functions."""

import pytest
from src.sockets.team_management import parse_cheat_type


class TestParseCheatType:
    """Test the parse_cheat_type function."""
    
    def test_no_cheat_prefix(self):
        """Test team names without cheat prefix return 'none'."""
        assert parse_cheat_type("Normal Team") == "none"
        assert parse_cheat_type("TeamAlpha") == "none"
        assert parse_cheat_type("test-team") == "none"
        assert parse_cheat_type("cheatteam") == "none"  # No hyphen
        assert parse_cheat_type("cheater") == "none"  # No hyphen
    
    def test_exact_cheat_prefixes(self):
        """Test exact cheat prefixes are detected correctly."""
        assert parse_cheat_type("cheat-com") == "com"
        assert parse_cheat_type("cheat-hint") == "hint"
        assert parse_cheat_type("cheat-tony") == "tony"
        assert parse_cheat_type("cheat-kevin") == "kevin"
    
    def test_cheat_prefixes_with_suffixes(self):
        """Test cheat prefixes with suffixes are detected correctly."""
        assert parse_cheat_type("cheat-com-teamA") == "com"
        assert parse_cheat_type("cheat-hint_awesome") == "hint"
        assert parse_cheat_type("cheat-tony 123") == "tony"
        assert parse_cheat_type("cheat-kevin-the-great") == "kevin"
    
    def test_case_insensitive(self):
        """Test that cheat detection is case-insensitive."""
        assert parse_cheat_type("CHEAT-COM") == "com"
        assert parse_cheat_type("Cheat-Hint") == "hint"
        assert parse_cheat_type("ChEaT-tOnY") == "tony"
        assert parse_cheat_type("cheat-KEVIN") == "kevin"
        assert parse_cheat_type("CHEAT-COM-TEAM") == "com"
    
    def test_edge_cases(self):
        """Test edge cases for the parser."""
        assert parse_cheat_type("") == "none"
        assert parse_cheat_type("   ") == "none"
        assert parse_cheat_type(None) == "none"
        assert parse_cheat_type("cheat-") == "none"  # No type after hyphen
        assert parse_cheat_type("cheat-unknown") == "none"  # Unknown cheat type
        assert parse_cheat_type("cheat-com-") == "com"  # Trailing hyphen is OK
    
    def test_whitespace_handling(self):
        """Test that leading/trailing whitespace is handled correctly."""
        assert parse_cheat_type("  cheat-com  ") == "com"
        assert parse_cheat_type("\tcheat-hint\n") == "hint"
        assert parse_cheat_type(" cheat-tony team ") == "tony"
    
    def test_invalid_cheat_types(self):
        """Test that invalid cheat types return 'none'."""
        assert parse_cheat_type("cheat-invalid") == "none"
        assert parse_cheat_type("cheat-Com") == "com"  # Case handling
        assert parse_cheat_type("cheat-hints") == "none"  # Wrong type name
        assert parse_cheat_type("cheat-tonys") == "none"  # Wrong type name