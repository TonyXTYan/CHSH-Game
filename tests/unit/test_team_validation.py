import pytest
from unittest.mock import patch, MagicMock, call
from src.models.quiz_models import Teams
from src.sockets.game import validate_team_sessions
from src.sockets.team_validation import check_for_duplicate_player_assignments, validate_all_teams

class TestTeamValidation:
    
    @pytest.fixture
    def mock_state(self):
        with patch('src.sockets.team_validation.state') as mock_state:
            mock_state.active_teams = {
                'team1': {
                    'team_id': 1,
                    'players': ['sid1', 'sid2'],
                    'current_round_number': 0,
                    'combo_tracker': {},
                    'answered_current_round': {}
                },
                'team2': {
                    'team_id': 2,
                    'players': ['sid3', 'sid4'],
                    'current_round_number': 0,
                    'combo_tracker': {},
                    'answered_current_round': {}
                }
            }
            mock_state.player_to_team = {
                'sid1': 'team1',
                'sid2': 'team1',
                'sid3': 'team2',
                'sid4': 'team2'
            }
            mock_state.connected_players = {'sid1', 'sid2', 'sid3', 'sid4'}
            yield mock_state
    
    @pytest.fixture
    def mock_db(self):
        with patch('src.sockets.team_validation.db') as mock_db:
            mock_db.session = MagicMock()
            yield mock_db
    
    @pytest.fixture
    def mock_teams(self):
        with patch('src.sockets.team_validation.Teams') as mock_teams:
            team1 = MagicMock()
            team1.team_id = 1
            team1.team_name = 'team1'
            team1.player1_session_id = 'sid1'
            team1.player2_session_id = 'sid2'
            team1.is_active = True
            
            team2 = MagicMock()
            team2.team_id = 2
            team2.team_name = 'team2'
            team2.player1_session_id = 'sid3'
            team2.player2_session_id = 'sid4'
            team2.is_active = True
            
            # Mock the query.get method to return appropriate team
            mock_teams.query.get.side_effect = lambda id: team1 if id == 1 else team2
            
            # Mock the query.filter_by().all() to return both teams
            mock_query = MagicMock()
            mock_query.all.return_value = [team1, team2]
            mock_teams.query.filter_by.return_value = mock_query
            
            yield mock_teams, [team1, team2]
    
    @patch('src.sockets.team_validation.validate_team_sessions')
    @patch('src.sockets.team_validation.sync_team_state')
    def test_validate_all_teams_normal(self, mock_sync, mock_validate, mock_state, mock_db, mock_teams):
        # Set up mocks
        mock_validate.return_value = True
        mock_sync.return_value = True
        
        # Run the function
        result = validate_all_teams()
        
        # Check the results
        assert result is True
        assert mock_validate.call_count == 2
        mock_validate.assert_has_calls([call('team1'), call('team2')], any_order=True)
        assert mock_sync.call_count == 2
        mock_sync.assert_has_calls([call('team1'), call('team2')], any_order=True)
    
    def test_check_for_duplicate_player_assignments(self, mock_state, mock_db, mock_teams):
        # Create a duplicate assignment - sid1 is in both team1 and team2
        mock_state.active_teams['team2']['players'] = ['sid1', 'sid4']  
        mock_state.player_to_team['sid1'] = 'team1'  # This is the "correct" team for sid1
        
        # Run the function
        fixed_count = check_for_duplicate_player_assignments()
        
        # Check the results
        assert fixed_count == 1  # One duplicate was fixed
        assert mock_state.active_teams['team2']['players'] == ['sid4']  # sid1 was removed from team2
        mock_db.session.commit.assert_called_once()
    
    def test_duplicate_sids_in_same_team(self, mock_state, mock_db, mock_teams):
        # Create a duplicate SID within the same team
        mock_state.active_teams['team1']['players'] = ['sid1', 'sid1']
        mock_teams_obj, mock_team_list = mock_teams
        team1 = mock_team_list[0]
        team1.player1_session_id = 'sid1'
        team1.player2_session_id = 'sid1'
        
        # Need to patch validate_team_sessions
        with patch('src.sockets.team_validation.validate_team_sessions') as mock_validate:
            mock_validate.return_value = False  # Validation detected issues
            
            # Run the function
            result = validate_all_teams()
            
            # Validate the function was called
            mock_validate.assert_called_with('team1')
