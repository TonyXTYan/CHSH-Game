import pytest
import sys
import os
from unittest.mock import MagicMock

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Mock Flask app and SocketIO
@pytest.fixture
def mock_app():
    mock = MagicMock()
    mock.config = {}
    return mock

@pytest.fixture
def mock_socketio():
    return MagicMock()

@pytest.fixture
def mock_db():
    mock = MagicMock()
    mock.Column = MagicMock(return_value=MagicMock())
    mock.String = MagicMock(return_value=MagicMock())
    mock.Integer = MagicMock(return_value=MagicMock())
    mock.Boolean = MagicMock(return_value=MagicMock())
    mock.DateTime = MagicMock(return_value=MagicMock())
    mock.Enum = MagicMock(return_value=MagicMock())
    mock.ForeignKey = MagicMock(return_value=MagicMock())
    mock.func = MagicMock()
    mock.func.now = MagicMock(return_value=MagicMock())
    mock.session = MagicMock()
    mock.session.commit = MagicMock()
    mock.session.add = MagicMock()
    mock.session.delete = MagicMock()
    mock.session.query = MagicMock(return_value=MagicMock())
    mock.session.rollback = MagicMock()
    mock.create_all = MagicMock()
    return mock

# Mock state fixture
@pytest.fixture
def mock_state():
    class MockAppState:
        def __init__(self):
            self.active_teams = {}
            self.player_to_team = {}
            self.dashboard_clients = set()
            self.game_started = False
            self.answer_stream_enabled = False
            self.previous_sessions = {}
            self.team_id_to_name = {}
        
        def reset(self):
            self.active_teams.clear()
            self.player_to_team.clear()
            self.dashboard_clients.clear()
            self.previous_sessions.clear()
            self.team_id_to_name.clear()
            self.game_started = False
            self.answer_stream_enabled = False
    
    return MockAppState()

# Mock request fixture
@pytest.fixture
def mock_request():
    mock = MagicMock()
    mock.sid = "test_sid"
    return mock
