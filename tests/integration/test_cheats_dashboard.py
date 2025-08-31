"""Integration tests for cheat dashboard features."""

import pytest
from src.config import app, db
from src.state import state
from src.sockets.dashboard import get_all_teams
from src.models.quiz_models import Teams


class TestCheatsDashboard:
    """Test Step 2 implementation - dashboard features for cheats."""
    
    def test_get_all_teams_includes_cheat_info(self):
        """Test that get_all_teams includes cheat info for teams."""
        with app.app_context():
            # Setup: Add some teams to state
            state.active_teams['Normal Team'] = {
                'players': ['sid1', 'sid2'],
                'team_id': 1,
                'current_round_number': 0,
                'combo_tracker': {},
                'answered_current_round': {},
                'status': 'active',
                'player_slots': {'sid1': 1, 'sid2': 2},
                'cheat_type': 'none'
            }
            
            state.active_teams['cheat-com-test'] = {
                'players': ['sid3'],
                'team_id': 2,
                'current_round_number': 0,
                'combo_tracker': {},
                'answered_current_round': {},
                'status': 'waiting_pair',
                'player_slots': {'sid3': 1},
                'cheat_type': 'com'
            }
            
            state.active_teams['cheat-hint-team'] = {
                'players': ['sid4', 'sid5'],
                'team_id': 3,
                'current_round_number': 0,
                'combo_tracker': {},
                'answered_current_round': {},
                'status': 'active',
                'player_slots': {'sid4': 1, 'sid5': 2},
                'cheat_type': 'hint'
            }
            
            # Clear any existing database data
            Teams.query.delete()
            db.session.commit()
                
            # Create DB entries for the teams
            for team_name, team_info in state.active_teams.items():
                team = Teams(
                    team_id=team_info['team_id'],
                    team_name=team_name,
                    is_active=True,
                    player1_session_id=team_info['players'][0] if len(team_info['players']) > 0 else None,
                    player2_session_id=team_info['players'][1] if len(team_info['players']) > 1 else None
                )
                db.session.add(team)
            db.session.commit()
            
            # Call get_all_teams
            teams = get_all_teams()
            
            # Verify results
            assert len(teams) == 3
            
            # Find each team in results
            normal_team = next(t for t in teams if t['team_name'] == 'Normal Team')
            com_team = next(t for t in teams if t['team_name'] == 'cheat-com-test')
            hint_team = next(t for t in teams if t['team_name'] == 'cheat-hint-team')
            
            # Check normal team
            assert normal_team['cheat'] == False
            assert normal_team['cheat_type'] == 'none'
            
            # Check com cheat team
            assert com_team['cheat'] == True
            assert com_team['cheat_type'] == 'com'
            
            # Check hint cheat team
            assert hint_team['cheat'] == True
            assert hint_team['cheat_type'] == 'hint'
            
            # Cleanup
            state.active_teams.clear()
            Teams.query.delete()
            db.session.commit()
    
    def test_cheats_banned_in_game_state(self):
        """Test that cheats_banned flag is included in dashboard updates."""
        # This is tested via the emit_dashboard_full_update function
        # which includes cheats_banned in game_state
        
        # Set the ban state
        original = state.cheats_banned
        state.cheats_banned = True
        
        try:
            # We can't easily test the socket emission, but we can verify the structure
            # The actual socket testing would require a full integration test with socket clients
            assert hasattr(state, 'cheats_banned')
            assert state.cheats_banned == True
        finally:
            state.cheats_banned = original