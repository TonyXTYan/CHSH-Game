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
import threading
import queue
from typing import Optional, IO, Any

# Add the project root to the path so we can import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Global variable to track server process
_server_process = None

def _read_pipe(pipe: IO[Any], output_queue: queue.Queue, prefix: str) -> None:
    """Read from a pipe and put output into a queue for logging"""
    try:
        for line in iter(pipe.readline, b''):
            if line:
                decoded_line = line.decode('utf-8', errors='replace').strip()
                output_queue.put(f"[{prefix}] {decoded_line}")
        pipe.close()
    except Exception as e:
        output_queue.put(f"[{prefix}] Error reading pipe: {e}")

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
def flask_server(pytestconfig, request):
    """Start Flask server for integration tests and shut it down after tests complete"""
    global _server_process
    
    # Check if integration tests are being run
    integration_tests_present = False
    
    # Method 1: Check command line arguments
    args = pytestconfig.args
    for arg in args:
        arg_str = str(arg)
        if ('integration' in arg_str or 
            'test_download_endpoint.py' in arg_str or 
            'test_player_interaction.py' in arg_str or
            'test_server_functionality.py' in arg_str):
            integration_tests_present = True
            break
    
    # Method 2: Check collected items (more reliable)
    if not integration_tests_present:
        try:
            # This runs during test collection, so we can check the collected items
            session = request.session
            if hasattr(session, 'items'):
                for item in session.items:
                    # Check for no_server marker first - if found, skip server startup
                    if hasattr(item, 'iter_markers'):
                        for marker in item.iter_markers('no_server'):
                            print("Found tests with no_server marker, skipping Flask server startup")
                            yield None
                            return
                    
                    # Check the file path
                    file_path = str(item.fspath) if hasattr(item, 'fspath') else str(item.path)
                    if ('integration' in file_path or 
                        'test_download_endpoint.py' in file_path or 
                        'test_player_interaction.py' in file_path or
                        'test_server_functionality.py' in file_path):
                        # But also check if these files have no_server marker
                        has_no_server = False
                        if hasattr(item, 'iter_markers'):
                            for marker in item.iter_markers('no_server'):
                                has_no_server = True
                                break
                        if not has_no_server:
                            integration_tests_present = True
                            break
                    
                    # Also check for integration markers (but not if no_server is present)
                    if hasattr(item, 'iter_markers'):
                        for marker in item.iter_markers('integration'):
                            # Check if same item also has no_server marker
                            has_no_server = False
                            for no_server_marker in item.iter_markers('no_server'):
                                has_no_server = True
                                break
                            if not has_no_server:
                                integration_tests_present = True
                                break
                    if integration_tests_present:
                        break
        except Exception as e:
            # If we can't determine, be safe and start the server
            integration_tests_present = True
    
    # Method 3: If running all tests or tests directory, start server to be safe
    if not integration_tests_present:
        if (not args or 
            (len(args) == 1 and args[0] in ['tests/', 'tests']) or
            any(arg == 'tests/' for arg in args) or
            # When running pytest without specific paths, it often defaults to current directory
            (len(args) == 0)):
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
        '--preload',
        '--log-level', 'info'
    ]
    
    output_queue: queue.Queue = queue.Queue()
    stdout_thread: Optional[threading.Thread] = None
    stderr_thread: Optional[threading.Thread] = None
    
    try:
        print("Starting Flask server for integration tests...")
        _server_process = subprocess.Popen(
            server_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid  # Create new process group
        )
        
        # Start threads to read stdout and stderr
        stdout_thread = threading.Thread(
            target=_read_pipe, 
            args=(_server_process.stdout, output_queue, "STDOUT"),
            daemon=True
        )
        stderr_thread = threading.Thread(
            target=_read_pipe, 
            args=(_server_process.stderr, output_queue, "STDERR"), 
            daemon=True
        )
        
        stdout_thread.start()
        stderr_thread.start()
        
        # Wait for server to be ready with improved error handling
        max_retries = 30
        server_ready = False
        
        for i in range(max_retries):
            # Check if process is still alive
            if _server_process.poll() is not None:
                # Process has terminated, collect any remaining output
                time.sleep(0.5)  # Give threads time to read final output
                
                # Collect and log all server output
                server_output = []
                while not output_queue.empty():
                    try:
                        server_output.append(output_queue.get_nowait())
                    except queue.Empty:
                        break
                
                error_msg = f"Flask server process terminated early (exit code: {_server_process.returncode})"
                if server_output:
                    error_msg += "\n\nServer output:\n" + "\n".join(server_output)
                else:
                    error_msg += "\n\nNo server output captured."
                
                raise Exception(error_msg)
            
            # Try to connect to server
            try:
                response = requests.get('http://localhost:8080', timeout=2)
                if response.status_code == 200:
                    print("Flask server is ready!")
                    server_ready = True
                    break
            except requests.exceptions.RequestException:
                pass  # Expected during startup
            
            # Log any server output during startup (for debugging)
            while not output_queue.empty():
                try:
                    output_line = output_queue.get_nowait()
                    print(f"Server: {output_line}")
                except queue.Empty:
                    break
            
            if i == max_retries - 1:
                # Final attempt failed, collect server output for debugging
                server_output = []
                while not output_queue.empty():
                    try:
                        server_output.append(output_queue.get_nowait())
                    except queue.Empty:
                        break
                
                error_msg = "Flask server failed to start within timeout"
                if _server_process.poll() is not None:
                    error_msg += f" (process exited with code {_server_process.returncode})"
                
                if server_output:
                    error_msg += "\n\nServer output:\n" + "\n".join(server_output)
                else:
                    error_msg += "\n\nNo server output captured."
                
                raise Exception(error_msg)
            
            time.sleep(1)
        
        if not server_ready:
            raise Exception("Server health check failed after startup")
        
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
        
        # Clean up threads (they're daemon threads so they'll exit automatically)
        # But we can still collect any final output for debugging if needed
        if output_queue:
            final_output = []
            while not output_queue.empty():
                try:
                    final_output.append(output_queue.get_nowait())
                except queue.Empty:
                    break
            
            if final_output:
                print("Final server output during shutdown:")
                for line in final_output:
                    print(f"  {line}")

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
