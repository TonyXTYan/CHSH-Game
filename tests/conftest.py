import pytest
import sys
import os
import warnings
from unittest.mock import MagicMock
import subprocess
import time
import requests
import atexit
import signal

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Global variable to track server process
_server_process = None

def _cleanup_server():
    """Clean up the server process on exit"""
    global _server_process
    if _server_process and _server_process.poll() is None:
        try:
            _server_process.terminate()
            _server_process.wait(timeout=5)
        except (subprocess.TimeoutExpired, ProcessLookupError):
            try:
                _server_process.kill()
                _server_process.wait(timeout=5)
            except:
                pass
        _server_process = None

# Register cleanup function
atexit.register(_cleanup_server)

@pytest.fixture(scope="session", autouse=True)
def flask_server(pytestconfig):
    """Start Flask server for integration tests and shut it down after tests complete"""
    global _server_process
    
    # Check if integration tests are being run
    integration_tests_present = False
    
    # Check if we're running tests from integration directory or with integration marker
    args = pytestconfig.args
    for arg in args:
        arg_str = str(arg)
        if ('integration' in arg_str or 
            'test_download_endpoint.py' in arg_str or 
            'test_player_interaction.py' in arg_str):
            integration_tests_present = True
            break
    
    # Also check if running all tests (no specific test files/directories specified)
    if not integration_tests_present:
        # Only start server if running all tests or tests directory without specifics
        if (not args or 
            (len(args) == 1 and args[0] in ['tests/', 'tests']) or
            any(arg == 'tests/' for arg in args)):
            integration_tests_present = True
    
    # If no integration tests, skip server startup
    if not integration_tests_present:
        print("No integration tests detected, skipping Flask server startup")
        yield None
        return
    
    # Start the server using gunicorn with eventlet worker
    server_cmd = [
        'gunicorn', 
        'wsgi:app',
        '--worker-class', 'eventlet',
        '--bind', '0.0.0.0:8080',
        '--timeout', '30',
        '--preload'
    ]
    
    try:
        print("Starting Flask server for integration tests...")
        _server_process = subprocess.Popen(
            server_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid  # Create new process group
        )
        
        # Wait for server to be ready
        max_retries = 30
        for i in range(max_retries):
            try:
                response = requests.get('http://localhost:8080', timeout=2)
                if response.status_code == 200:
                    print("Flask server is ready!")
                    break
            except requests.exceptions.RequestException:
                if i == max_retries - 1:
                    raise Exception("Flask server failed to start within timeout")
                time.sleep(1)
        
        yield _server_process
        
    finally:
        # Clean shutdown
        print("Shutting down Flask server...")
        if _server_process and _server_process.poll() is None:
            try:
                # Send SIGTERM to the process group
                os.killpg(os.getpgid(_server_process.pid), signal.SIGTERM)
                _server_process.wait(timeout=10)
                print("Flask server shut down gracefully")
            except (subprocess.TimeoutExpired, ProcessLookupError, OSError):
                try:
                    # Force kill if graceful shutdown fails
                    os.killpg(os.getpgid(_server_process.pid), signal.SIGKILL)
                    _server_process.wait(timeout=5)
                    print("Flask server forcefully terminated")
                except:
                    pass
            _server_process = None

# Filter specific warnings
# @pytest.fixture(autouse=True)
# def filter_warnings():
#     # Filter warning about uncertainties with std_dev==0
#     warnings.filterwarnings("ignore", message="Using UFloat objects with std_dev==0 may give unexpected results.")
#     # Filter warning about deprecated umath.fabs()
#     warnings.filterwarnings("ignore", message="umath.fabs() is deprecated.")
#     # Filter warning about deprecated AffineScalarFunc.__abs__()
#     warnings.filterwarnings("ignore", message="AffineScalarFunc.__abs__() is deprecated.")
#     # Filter SQLAlchemy deprecation warnings
#     warnings.filterwarnings("ignore", message="The Query.get() method is considered legacy")
#     yield

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
