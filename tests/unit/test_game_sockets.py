import pytest
from flask import Flask
from flask_socketio import SocketIO, join_room
from unittest.mock import patch, MagicMock
from src.config import socketio
from src.state import state
from src.sockets.game import on_submit_answer

@pytest.fixture
def test_client():
    app = Flask(__name__)
    app.config['TESTING'] = True
    print("Debug: Initializing Flask-SocketIO app in test")
    socketio.init_app(app)
    print("Debug: Flask-SocketIO app initialized in test")
    print("Debug: Initializing test client")
    client = socketio.test_client(app)
    print("Debug: Test client initialized")
    print(f"Debug: Test client connected: {client.is_connected()}")
    yield client
    client.disconnect()

def test_on_submit_answer_valid_submission(test_client):
    # Mock state and database
    state.player_to_team = {'test_sid': 'team1'}
    state.active_teams = {
        'team1': {
            'players': ['test_sid', 'other_sid'],
            'current_db_round_id': 1,
            'answered_current_round': {},
            'team_id': 123,
            'current_round_number': 1
        }
    }
    state.dashboard_clients = ['dashboard_sid']
    state.game_paused = False

    mock_db_session = MagicMock()
    mock_round_query = MagicMock()
    mock_round_query.get.return_value = MagicMock()

    with patch('src.sockets.game.db.session', mock_db_session), \
         patch('src.sockets.game.PairQuestionRounds.query', mock_round_query), \
         patch('src.sockets.game.Answers') as MockAnswers, \
         patch('src.sockets.game.start_new_round_for_pair') as mock_start_new_round:
        
        # Simulate valid data
        data = {
            'round_id': 1,
            'item': 'A',
            'answer': True
        }
        print(f"Debug: Mocked state.player_to_team: {state.player_to_team}")
        print(f"Debug: Mocked state.active_teams: {state.active_teams}")
        print(f"Debug: Mocked data: {data}")
        print("Debug: Emitting 'submit_answer' event")
        test_client.emit('submit_answer', data, namespace='/')
        print("Debug: Event emitted, verifying namespace '/' and event routing (final check)")
        print("Received events:", test_client.get_received())

        # Assertions
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        mock_start_new_round.assert_called_once_with('team1')
        assert test_client.get_received()[-1]['name'] == 'answer_confirmed'

def test_on_submit_answer_invalid_team(test_client):
    # Mock state
    state.player_to_team = {}
    state.active_teams = {}
    state.game_paused = False

    # Simulate invalid data
    data = {
        'round_id': 1,
            'item': 'Z',
        'answer': True
    }
    print(f"Debug: Mocked state.player_to_team: {state.player_to_team}")
    print(f"Debug: Mocked state.active_teams: {state.active_teams}")
    print(f"Debug: Mocked data: {data}")
    print("Debug: Emitting 'submit_answer' event")
    test_client.emit('submit_answer', data, namespace='/')
    print("Debug: Event emitted")
    print("Received events:", test_client.get_received())

    # Assertions
    received = test_client.get_received()
    assert received[-1]['name'] == 'error'
    assert 'You are not in a team or session expired.' in received[-1]['args'][0]['message']
