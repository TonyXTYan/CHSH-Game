import pytest
from unittest.mock import patch, MagicMock
from src.sockets.dashboard import on_pause_game
from src.config import app
from src.state import state

@pytest.fixture
def test_client():
    return app.test_client()

@pytest.fixture
def mock_request():
    with app.test_request_context() as ctx:
        ctx.request.sid = 'test_dashboard_sid'
        yield ctx.request

@pytest.fixture
def mock_state():
    with patch('src.sockets.dashboard.state') as mock_state:
        mock_state.dashboard_clients = {'test_dashboard_sid'}
        mock_state.active_teams = {'team1': {'players': ['p1', 'p2']}}
        mock_state.game_paused = False
        yield mock_state

@pytest.fixture
def mock_socketio():
    with patch('src.sockets.dashboard.socketio') as mock_io:
        yield mock_io

@pytest.fixture
def mock_emit():
    with patch('src.sockets.dashboard.emit') as mock_emit:
        yield mock_emit

def test_pause_game_toggles_state(mock_request, mock_state, mock_socketio, mock_emit):
    """Test that pause_game properly toggles game state and notifies clients"""
    # Initial state is unpaused
    assert not mock_state.game_paused

    # Call pause_game
    on_pause_game()

    # Verify state was toggled
    assert mock_state.game_paused

    # Verify teams were notified
    mock_socketio.emit.assert_any_call('game_state_update', 
                                      {'paused': True}, 
                                      room='team1')

    # Call pause_game again
    on_pause_game()

    # Verify state was toggled back
    assert not mock_state.game_paused

    # Verify teams were notified of unpause
    mock_socketio.emit.assert_any_call('game_state_update', 
                                      {'paused': False}, 
                                      room='team1')

def test_pause_game_unauthorized(mock_request, mock_state, mock_socketio, mock_emit):
    """Test that unauthorized clients cannot pause the game"""
    # Remove dashboard client status
    mock_state.dashboard_clients = set()
    
    # Try to pause game
    on_pause_game()

    # Verify state remained unchanged
    assert not mock_state.game_paused

    # Verify error was emitted
    mock_emit.assert_called_once_with('error', 
                                     {'message': 'Unauthorized: Not a dashboard client'})

    # Verify no team notifications were sent
    mock_socketio.emit.assert_not_called()