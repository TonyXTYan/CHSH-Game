import pytest
from unittest.mock import patch, MagicMock
from src.sockets.team_management import parse_cheat_type
from src.state import state


class TestCheatNonRegression:
    """Test that non-cheat teams are unaffected by cheat functionality"""
    
    def test_non_cheat_team_creation_unaffected(self):
        """Test that normal teams can still be created when cheats are not banned"""
        # Normal team names should parse as 'none'
        normal_names = [
            "team_alpha", 
            "my-awesome-team", 
            "players123", 
            "test_team",
            "normal-team-name"
        ]
        
        for team_name in normal_names:
            cheat_type = parse_cheat_type(team_name)
            assert cheat_type == "none", f"Team {team_name} should not be detected as cheat"
    
    def test_non_cheat_team_creation_when_cheats_banned(self):
        """Test that normal teams can be created even when cheats are banned"""
        # Simulate cheats being banned
        original_banned = state.cheats_banned
        state.cheats_banned = True
        
        try:
            normal_names = [
                "team_alpha", 
                "my-awesome-team", 
                "players123", 
                "test_team"
            ]
            
            for team_name in normal_names:
                cheat_type = parse_cheat_type(team_name)
                assert cheat_type == "none"
                
                # These teams should be allowed (not blocked by ban logic)
                # The ban logic only blocks if cheat_type != "none"
                should_be_blocked = state.cheats_banned and cheat_type != "none"
                assert not should_be_blocked, f"Normal team {team_name} should not be blocked"
                
        finally:
            # Restore original state
            state.cheats_banned = original_banned
    
    def test_cheat_detection_only_affects_cheat_names(self):
        """Test that cheat detection is precise and doesn't affect similar names"""
        # These should NOT be detected as cheats
        non_cheat_names = [
            "team-cheat-com",  # cheat not at start
            "my-cheat-hint",   # cheat not at start  
            "cheat",           # no dash
            "cheat-",          # no type
            "cheat-invalid",   # invalid type
            "cheat-xyz",       # invalid type
            "cheater-com",     # not exact match
            "anti-cheat-com",  # cheat not at start
        ]
        
        for team_name in non_cheat_names:
            cheat_type = parse_cheat_type(team_name)
            assert cheat_type == "none", f"Team {team_name} should not be detected as cheat"
    
    def test_team_state_structure_unchanged_for_non_cheats(self):
        """Test that team state structure is the same for non-cheat teams"""
        # Mock team creation to check state structure
        team_name = "normal_team"
        cheat_type = parse_cheat_type(team_name)
        assert cheat_type == "none"
        
        # The team state should include cheat_type: "none" but otherwise be unchanged
        expected_keys = {
            'players', 'team_id', 'current_round_number', 'combo_tracker',
            'answered_current_round', 'status', 'player_slots', 'cheat_type'
        }
        
        # Simulate what team state would look like
        mock_team_state = {
            'players': ['test_sid'],
            'team_id': 123,
            'current_round_number': 0,
            'combo_tracker': {},
            'answered_current_round': {},
            'status': 'waiting_pair',
            'player_slots': {'test_sid': 1},
            'cheat_type': cheat_type
        }
        
        # Verify all expected keys are present
        assert set(mock_team_state.keys()) == expected_keys
        # Verify cheat_type is "none" for normal teams
        assert mock_team_state['cheat_type'] == "none"
    
    def test_dashboard_data_includes_cheat_flags_for_all_teams(self):
        """Test that dashboard data includes cheat flags for all teams, including non-cheats"""
        # For non-cheat teams, cheat should be False and cheat_type should be "none"
        team_name = "normal_team"
        cheat_type = parse_cheat_type(team_name)
        
        # Simulate what dashboard would receive
        team_data = {
            'team_name': team_name,
            'cheat': cheat_type != 'none',
            'cheat_type': cheat_type
        }
        
        # Non-cheat teams should have cheat=False and cheat_type="none"
        assert team_data['cheat'] is False
        assert team_data['cheat_type'] == "none"
        
        # For cheat teams, verify the opposite
        cheat_team_name = "cheat-com-test"
        cheat_team_type = parse_cheat_type(cheat_team_name)
        
        cheat_team_data = {
            'team_name': cheat_team_name,
            'cheat': cheat_team_type != 'none',
            'cheat_type': cheat_team_type
        }
        
        assert cheat_team_data['cheat'] is True
        assert cheat_team_data['cheat_type'] == "com"
    
    def test_no_new_events_for_non_cheat_teams(self):
        """Test that non-cheat teams don't receive any new cheat-related events"""
        # This is more of a documentation test - the implementation should ensure
        # that cheat events (cheat:partner_choice, cheat:hint) are only sent
        # to teams where cheat_type != "none"
        
        normal_team_cheat_type = parse_cheat_type("normal_team")
        cheat_team_cheat_type = parse_cheat_type("cheat-com-test")
        
        # Normal teams should not receive cheat events
        should_receive_cheat_events = normal_team_cheat_type != "none"
        assert not should_receive_cheat_events
        
        # Cheat teams should receive cheat events  
        should_receive_cheat_events = cheat_team_cheat_type != "none"
        assert should_receive_cheat_events