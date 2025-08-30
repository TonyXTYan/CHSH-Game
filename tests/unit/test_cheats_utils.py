import pytest
from src.sockets.team_management import parse_cheat_type


class TestParseCheatType:
    """Test cheat type parsing functionality"""
    
    def test_parse_cheat_type_none(self):
        """Test that non-cheat team names return 'none'"""
        assert parse_cheat_type("normal_team") == "none"
        assert parse_cheat_type("team123") == "none"
        assert parse_cheat_type("my-awesome-team") == "none"
        assert parse_cheat_type("") == "none"
        assert parse_cheat_type("   ") == "none"
        assert parse_cheat_type(None) == "none"
        
    def test_parse_cheat_type_com(self):
        """Test that com cheat teams are detected"""
        assert parse_cheat_type("cheat-com") == "com"
        assert parse_cheat_type("cheat-com-team") == "com"
        assert parse_cheat_type("cheat-com_team") == "com"
        assert parse_cheat_type("cheat-com team") == "com"
        assert parse_cheat_type("CHEAT-COM") == "com"
        assert parse_cheat_type("Cheat-Com") == "com"
        
    def test_parse_cheat_type_hint(self):
        """Test that hint cheat teams are detected"""
        assert parse_cheat_type("cheat-hint") == "hint"
        assert parse_cheat_type("cheat-hint-team") == "hint"
        assert parse_cheat_type("cheat-hint_team") == "hint"
        assert parse_cheat_type("cheat-hint team") == "hint"
        assert parse_cheat_type("CHEAT-HINT") == "hint"
        assert parse_cheat_type("Cheat-Hint") == "hint"
        
    def test_parse_cheat_type_tony(self):
        """Test that tony cheat teams are detected"""
        assert parse_cheat_type("cheat-tony") == "tony"
        assert parse_cheat_type("cheat-tony-team") == "tony"
        assert parse_cheat_type("cheat-tony_team") == "tony"
        assert parse_cheat_type("cheat-tony team") == "tony"
        assert parse_cheat_type("CHEAT-TONY") == "tony"
        assert parse_cheat_type("Cheat-Tony") == "tony"
        
    def test_parse_cheat_type_kevin(self):
        """Test that kevin cheat teams are detected"""
        assert parse_cheat_type("cheat-kevin") == "kevin"
        assert parse_cheat_type("cheat-kevin-team") == "kevin"
        assert parse_cheat_type("cheat-kevin_team") == "kevin"
        assert parse_cheat_type("cheat-kevin team") == "kevin"
        assert parse_cheat_type("CHEAT-KEVIN") == "kevin"
        assert parse_cheat_type("Cheat-Kevin") == "kevin"
        
    def test_parse_cheat_type_edge_cases(self):
        """Test edge cases and invalid formats"""
        # Invalid cheat types should return 'none'
        assert parse_cheat_type("cheat-invalid") == "none"
        assert parse_cheat_type("cheat-xyz") == "none"
        assert parse_cheat_type("cheat-") == "none"
        assert parse_cheat_type("cheat") == "none"
        
        # Teams that contain but don't start with cheat should return 'none'
        assert parse_cheat_type("team-cheat-com") == "none"
        assert parse_cheat_type("my-cheat-hint") == "none"
        
    def test_parse_cheat_type_case_insensitive(self):
        """Test that parsing is case insensitive"""
        test_cases = [
            ("cheat-com", "com"),
            ("CHEAT-COM", "com"),
            ("Cheat-Com", "com"),
            ("chEaT-cOm", "com"),
            ("cheat-HINT", "hint"),
            ("CHEAT-hint", "hint"),
            ("cheat-Tony", "tony"),
            ("CHEAT-KEVIN", "kevin")
        ]
        
        for team_name, expected in test_cases:
            assert parse_cheat_type(team_name) == expected
            
    def test_parse_cheat_type_with_suffixes(self):
        """Test that cheat detection works with various suffixes"""
        suffixes = ["-team", "_group", " players", "-v2", "_final"]
        cheat_types = ["com", "hint", "tony", "kevin"]
        
        for cheat_type in cheat_types:
            for suffix in suffixes:
                team_name = f"cheat-{cheat_type}{suffix}"
                assert parse_cheat_type(team_name) == cheat_type
                
    def test_parse_cheat_type_error_handling(self):
        """Test that errors are handled gracefully"""
        # Should not throw exceptions for any input
        assert parse_cheat_type("cheat-com") == "com"  # Normal case
        
        # Test with unusual inputs that might cause regex issues
        unusual_inputs = [
            "cheat-com\n",
            "cheat-com\t",
            "cheat-com\r",
            "cheat-com with lots of spaces",
            "   cheat-com   ",
        ]
        
        for input_val in unusual_inputs:
            result = parse_cheat_type(input_val)
            assert isinstance(result, str)
            assert result in ["none", "com", "hint", "tony", "kevin"]