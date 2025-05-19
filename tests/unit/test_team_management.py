import pytest
from unittest.mock import patch, ANY
from flask import request
from wsgi import app
from src.config import socketio, db
from src.models.quiz_models import Teams
from src.state import state

@pytest.fixture
def app_context():
    with app.app_context():
        app.extensions['socketio'] = socketio
        yield app

@pytest.fixture
def mock_request_context(app_context):
    with app_context.test_request_context('/') as context:
        context.request.sid = 'test_sid'
        context.request.namespace = '/'
        yield context.request

@pytest.fixture
def inactive_team():
    with app.app_context():
        # Create an inactive team in the database
        team = Teams(team_name="test_team", is_active=False)
        db.session.add(team)
        db.session.commit()
        yield team
        # Cleanup
        db.session.delete(team)
        db.session.commit()

def test_reactivate_team_success(mock_request_context, inactive_team):
    """Test successful team reactivation"""
    with patch('src.sockets.team_management.emit') as mock_emit, \
         patch('src.sockets.team_management.socketio.emit') as mock_socketio_emit, \
         patch('src.sockets.team_management.emit_dashboard_team_update') as mock_dashboard_update, \
         patch('src.sockets.team_management.join_room') as mock_join_room:
        
        # Initial state check
        assert "test_team" not in state.active_teams
        
        # Attempt to reactivate team
        from src.sockets.team_management import on_reactivate_team
        on_reactivate_team({'team_name': 'test_team'})
        
        # Verify team was updated in database
        team = Teams.query.filter_by(team_id=inactive_team.team_id).first()
        assert team.is_active == True
        assert team.player1_session_id == 'test_sid'
        
        # Verify state updates
        assert "test_team" in state.active_teams
        assert state.active_teams["test_team"]["team_id"] == inactive_team.team_id
        assert 'test_sid' in state.active_teams["test_team"]["players"]
        assert state.active_teams["test_team"]["status"] == "waiting_pair"
        assert state.player_to_team['test_sid'] == "test_team"
        
        # Verify event emissions
        mock_emit.assert_any_call(
            'team_created',
            {
                'team_name': 'test_team',
                'team_id': inactive_team.team_id,
                'message': 'Team reactivated successfully. Waiting for another player.',
                'game_started': state.game_started
            }
        )
        
        mock_socketio_emit.assert_any_call(
            'teams_updated',
            {
                'teams': ANY,
                'game_started': state.game_started
            }
        )
        
        # Verify dashboard update was called
        mock_dashboard_update.assert_called_once()

def test_reactivate_nonexistent_team(mock_request_context):
    """Test attempt to reactivate a team that doesn't exist"""
    with patch('src.sockets.team_management.emit') as mock_emit:
        from src.sockets.team_management import on_reactivate_team
        on_reactivate_team({'team_name': 'nonexistent_team'})
        
        mock_emit.assert_called_once_with(
            'error',
            {'message': 'Team not found or is already active'}
        )

def test_reactivate_team_name_conflict(mock_request_context, inactive_team):
    """Test attempt to reactivate a team when active team with same name exists"""
    # Set up an active team with the same name
    state.active_teams['test_team'] = {
        'players': ['other_sid'],
        'team_id': 999,
        'status': 'waiting_pair'
    }
    
    with patch('src.sockets.team_management.emit') as mock_emit:
        from src.sockets.team_management import on_reactivate_team
        on_reactivate_team({'team_name': 'test_team'})
        
        mock_emit.assert_called_once_with(
            'error',
            {'message': 'An active team with this name already exists'}
        )
    
    # Cleanup
    state.active_teams.clear()
    state.player_to_team.clear()
    state.team_id_to_name.clear()
