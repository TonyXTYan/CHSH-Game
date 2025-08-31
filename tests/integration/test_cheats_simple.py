"""Simple integration tests for cheat functionality to verify Step 1."""

import pytest
from src.models.quiz_models import Teams
from src.state import state
from src.sockets.team_management import parse_cheat_type


class TestCheatsStep1:
    """Test Step 1 implementation - parser, state, and ban enforcement."""
    
    def test_parser_integration(self):
        """Test that the parser is accessible and works correctly."""
        # Test normal teams
        assert parse_cheat_type("Normal Team") == "none"
        assert parse_cheat_type("test-team") == "none"
        
        # Test cheat teams
        assert parse_cheat_type("cheat-com") == "com"
        assert parse_cheat_type("cheat-hint-team") == "hint"
        assert parse_cheat_type("CHEAT-TONY_123") == "tony"
        assert parse_cheat_type("cheat-kevin test") == "kevin"
    
    def test_state_cheats_banned_flag(self):
        """Test that state has cheats_banned flag."""
        # Should have the flag
        assert hasattr(state, 'cheats_banned')
        
        # Can be set
        original = state.cheats_banned
        state.cheats_banned = True
        assert state.cheats_banned == True
        state.cheats_banned = False
        assert state.cheats_banned == False
        state.cheats_banned = original
    
    def test_env_variable_loading(self):
        """Test that CHEATS_DISABLED env var is respected."""
        import os
        
        # Save original
        original_value = os.environ.get('CHEATS_DISABLED')
        original_state = state.cheats_banned
        
        try:
            # Test with env var set
            os.environ['CHEATS_DISABLED'] = 'true'
            state.reset()
            assert state.cheats_banned == True
            
            # Test with env var as false
            os.environ['CHEATS_DISABLED'] = 'false'
            state.reset()
            assert state.cheats_banned == False
            
            # Test without env var
            if 'CHEATS_DISABLED' in os.environ:
                del os.environ['CHEATS_DISABLED']
            state.reset()
            assert state.cheats_banned == False
            
        finally:
            # Restore original
            if original_value is None:
                os.environ.pop('CHEATS_DISABLED', None)
            else:
                os.environ['CHEATS_DISABLED'] = original_value
            state.cheats_banned = original_state
    
    def test_team_state_structure(self):
        """Test that team state can store cheat_type."""
        # Create a mock team in state
        team_name = "test-team"
        state.active_teams[team_name] = {
            'players': [],
            'team_id': 1,
            'current_round_number': 0,
            'combo_tracker': {},
            'answered_current_round': {},
            'status': 'waiting_pair',
            'player_slots': {},
            'cheat_type': 'none'
        }
        
        # Verify structure
        assert 'cheat_type' in state.active_teams[team_name]
        assert state.active_teams[team_name]['cheat_type'] == 'none'
        
        # Test with cheat type
        state.active_teams[team_name]['cheat_type'] = 'com'
        assert state.active_teams[team_name]['cheat_type'] == 'com'
        
        # Cleanup
        del state.active_teams[team_name]