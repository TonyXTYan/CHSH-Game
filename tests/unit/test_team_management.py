import pytest
from unittest.mock import patch, MagicMock
from src.models.quiz_models import Teams
from src.sockets.game import validate_team_sessions

class TestTeamManagement:
    
    @pytest.fixture
    def mock_state(self):
        with patch('src.sockets.game.state') as mock_state:
            mock_state.active_teams = {
                'test_team': {
                    'team_id': 1,
                    'players': ['sid1', 'sid2'],
                    'current_round_number': 0,
                    'combo_tracker': {},
                    'answered_current_round': {}
                }
            }
            yield mock_state
    
    @pytest.fixture
    def mock_db(self):
        with patch('src.sockets.game.db') as mock_db:
            mock_db.session = MagicMock()
            yield mock_db
    
    @pytest.fixture
    def mock_teams(self):
        with patch('src.sockets.game.Teams') as mock_teams:
            mock_team = MagicMock()
            mock_team.player1_session_id = 'sid1'
            mock_team.player2_session_id = 'sid2'
            mock_teams.query.get.return_value = mock_team
            yield mock_teams, mock_team
    
    def test_validate_team_sessions_no_duplicates(self, mock_state, mock_db, mock_teams):
        mock_teams, mock_team = mock_teams
        
        result = validate_team_sessions('test_team')
        
        assert result is True
        # No changes should be made to the database
        mock_db.session.commit.assert_not_called()
    
    def test_validate_team_sessions_duplicate_in_db(self, mock_state, mock_db, mock_teams):
        mock_teams, mock_team = mock_teams
        
        # Set up duplicate in database
        mock_team.player1_session_id = 'sid1'
        mock_team.player2_session_id = 'sid1'
        
        result = validate_team_sessions('test_team')
        
        assert result is False
        # Should clear player2 and commit changes
        assert mock_team.player2_session_id is None
        mock_db.session.commit.assert_called_once()
    
    def test_validate_team_sessions_duplicate_in_memory(self, mock_state, mock_db, mock_teams):
        mock_teams, mock_team = mock_teams
        
        # Set up duplicate in memory
        mock_state.active_teams['test_team']['players'] = ['sid1', 'sid1']
        
        result = validate_team_sessions('test_team')
        
        assert result is False
        # Should fix the players array
        assert mock_state.active_teams['test_team']['players'] == ['sid1']
