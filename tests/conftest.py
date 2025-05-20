import eventlet
eventlet.monkey_patch()

# Monkey-patch standard library before any other imports

import pytest
import sys
import os
import logging
import socket
import time
import multiprocessing
import signal
from unittest.mock import MagicMock

def run_server(server_ready, startup_error, logger):
    """Run the Flask server in a subprocess."""
    try:
        from src.main import app, socketio

        logger.info("Initializing server in subprocess...")
        
        # Check port availability
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(('127.0.0.1', 8080))
            sock.close()
        except OSError as e:
            startup_error.put(str(e))
            server_ready.set()
            logger.error(f"Port check failed: {e}")
            return

        # Set up signal handler for graceful shutdown
        def handle_shutdown(signum, frame):
            logger.info(f"Server process received signal {signum}")
            socketio.stop()
        
        signal.signal(signal.SIGTERM, handle_shutdown)
        signal.signal(signal.SIGINT, handle_shutdown)
        
        logger.info("Starting server with eventlet...")
        
        def start_server():
            try:
                socketio.run(app, host='127.0.0.1', port=8080, log_output=True, debug=True)
            except Exception as e:
                startup_error.put(str(e))
                logger.error(f"Eventlet server failed: {e}")
                
        # Start server in a thread so we can set ready event after bind
        import threading
        server_thread = threading.Thread(target=start_server)
        server_thread.daemon = True
        server_thread.start()
        
        # Wait briefly for server to bind port
        time.sleep(0.5)
        server_ready.set()
        
    except Exception as e:
        startup_error.put(str(e))
        server_ready.set()
        logger.error(f"Server startup failed: {e}")
        raise
    finally:
        logger.info("Server process shutting down...")

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

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

@pytest.fixture(scope="function")
def server_thread():
    """Fixture to run the Flask server in a separate process for testing"""
    # Inter-process communication primitives
    server_ready = multiprocessing.Event()
    stop_server = multiprocessing.Event()
    startup_error = multiprocessing.Queue()

    # Start server in a separate process
    process = multiprocessing.Process(target=run_server, args=(server_ready, startup_error, logger))
    logger.info("Starting server process...")
    process.start()

    try:
        # Wait for server initialization
        if not server_ready.wait(timeout=10):
            pytest.fail("Server initialization timed out")

        # Check for startup errors
        try:
            error = startup_error.get_nowait()
            pytest.fail(f"Server failed to start: {error}")
        except multiprocessing.queues.Empty:
            pass

        # Additional connection check
        def wait_for_server(timeout=5):
            logger.info("Waiting for server to accept connections...")
            start_time = time.time()
            connection_errors = []
            
            while time.time() - start_time < timeout:
                # Check if process is still alive
                if not process.is_alive():
                    exit_code = process.exitcode
                    logger.error(f"Server process died with exit code: {exit_code}")
                    # Check for any startup errors
                    try:
                        error = startup_error.get_nowait()
                        logger.error(f"Server startup error: {error}")
                        raise RuntimeError(f"Server failed to start: {error}")
                    except multiprocessing.queues.Empty:
                        raise RuntimeError(f"Server process died unexpectedly with exit code {exit_code}")
                
                try:
                    with socket.create_connection(('127.0.0.1', 8080), timeout=1) as sock:
                        logger.info("Successfully connected to server")
                        if connection_errors:
                            logger.info(f"Previous connection attempts failed with: {', '.join(connection_errors)}")
                        return True
                except (socket.error, socket.timeout) as e:
                    error_msg = str(e)
                    if error_msg not in connection_errors:
                        connection_errors.append(error_msg)
                    logger.debug(f"Connection attempt failed: {e}")
                    time.sleep(0.1)
            
            if connection_errors:
                logger.error(f"All connection attempts failed with: {', '.join(connection_errors)}")
            return False

        if not wait_for_server():
            logger.error("Server is not accepting connections")
            pytest.fail("Server failed to accept connections within timeout")

        logger.info("Server is ready to accept connections")
        yield process

    finally:
        # Robust teardown process
        logger.info("Starting server teardown...")
        
        if process.is_alive():
            logger.info("Sending termination signal...")
            process.terminate()
            
            logger.info("Waiting for server process to exit...")
            process.join(timeout=5)
            
            if process.is_alive():
                logger.warning("Server process did not exit gracefully, forcing termination...")
                os.kill(process.pid, signal.SIGKILL)
                process.join(1)
        
        # Double-check process termination
        if process.is_alive():
            logger.error("Failed to terminate server process!")
        else:
            logger.info("Server process terminated successfully")

@pytest.fixture
def dashboard_client(server_thread):
    """Fixture to create a Socket.IO client for dashboard testing"""
    import socketio
    from socketio.exceptions import ConnectionError
    
    logger.info("Initializing Socket.IO dashboard client...")
    client = socketio.Client(logger=logger, reconnection=False)
    
    # Events for tracking connection and registration
    connection_event = multiprocessing.Event()
    registered_event = multiprocessing.Event()
    connection_error = multiprocessing.Queue()
    
    @client.event
    def connect():
        logger.info("Dashboard client connected successfully")
        connection_event.set()
    
    @client.event
    def connect_error(data):
        error_msg = f"Dashboard connection error: {data}"
        logger.error(error_msg)
        connection_error.put(error_msg)
        connection_event.set()
    
    @client.event
    def disconnect():
        logger.info("Dashboard client disconnected")
    
    @client.on('dashboard_registered')
    def on_registered(data):
        logger.info("Dashboard registration confirmed")
        registered_event.set()
    
    connection_timeout = 10
    registration_timeout = 5
    
    try:
        logger.info(f"Attempting to connect dashboard client (timeout: {connection_timeout}s)...")
        client.connect('http://127.0.0.1:8080', wait_timeout=connection_timeout)
        
        if not connection_event.wait(timeout=connection_timeout):
            raise TimeoutError("Dashboard connection timed out")
        try:
            error = connection_error.get_nowait()
            raise ConnectionError(error)
        except multiprocessing.queues.Empty:
            pass
        
        logger.info("Registering as dashboard...")
        client.emit('register_dashboard')
        
        if not registered_event.wait(timeout=registration_timeout):
            raise TimeoutError("Dashboard registration timed out")
        
        logger.info("Dashboard client setup completed successfully")
        yield client
        
    except Exception as e:
        logger.error(f"Error in dashboard client setup: {e}")
        raise
        
    finally:
        logger.info("Cleaning up dashboard client connection...")
        if hasattr(client, 'connected') and client.connected:
            try:
                client.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting dashboard client: {e}")

@pytest.fixture
def player_client(server_thread):
    """Fixture to create a Socket.IO client for player testing"""
    import socketio
    from socketio.exceptions import ConnectionError
    
    logger.info("Initializing Socket.IO client...")
    client = socketio.Client(logger=logger, reconnection=False)
    
    # Set up event handlers for connection status
    @client.event
    def connect():
        logger.info("Client connected successfully")
    
    @client.event
    def connect_error(data):
        logger.error(f"Connection error: {data}")
    
    @client.event
    def disconnect():
        logger.info("Client disconnected")
    
    connection_timeout = 10
    try:
        logger.info(f"Attempting to connect to server (timeout: {connection_timeout}s)...")
        client.connect('http://127.0.0.1:8080', wait_timeout=connection_timeout)
        logger.info("Connection established")
        yield client
    except ConnectionError as e:
        logger.error(f"Failed to connect to server: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during client connection: {e}")
        raise
    finally:
        logger.info("Cleaning up client connection...")
        if hasattr(client, 'connected') and client.connected:
            try:
                client.disconnect()
            except Exception as e:
                logger.error(f"Error during disconnect: {e}")

@pytest.fixture
def reset_state(mock_state):
    """Fixture to reset game state between tests"""
    mock_state.reset()
    yield mock_state

@pytest.fixture
def two_player_clients(server_thread):
    """Fixture to create two Socket.IO clients for testing"""
    import socketio
    from socketio.exceptions import ConnectionError
    
    logger.info("Initializing two Socket.IO clients...")
    client1 = socketio.Client(logger=logger, reconnection=False)
    client2 = socketio.Client(logger=logger, reconnection=False)
    
    # Track connection status using multiprocessing primitives
    clients_connected = multiprocessing.Event()
    connection_errors = multiprocessing.Queue()
    
    def setup_client_handlers(client, client_id):
        @client.event
        def connect():
            logger.info(f"Client {client_id} connected successfully")
            if client1.connected and client2.connected:
                clients_connected.set()
        
        @client.event
        def connect_error(data):
            error_msg = f"Client {client_id} connection error: {data}"
            logger.error(error_msg)
            connection_errors.put(error_msg)
            clients_connected.set()  # Set event to unblock waiting
        
        @client.event
        def disconnect():
            logger.info(f"Client {client_id} disconnected")
    
    # Set up handlers for both clients
    setup_client_handlers(client1, "1")
    setup_client_handlers(client2, "2")
    
    connection_timeout = 10
    try:
        logger.info(f"Attempting to connect client1 (timeout: {connection_timeout}s)...")
        client1.connect('http://127.0.0.1:8080', wait_timeout=connection_timeout)
        logger.info(f"Attempting to connect client2 (timeout: {connection_timeout}s)...")
        client2.connect('http://127.0.0.1:8080', wait_timeout=connection_timeout)
        
        logger.info("Waiting for both clients to establish connection...")
        if not clients_connected.wait(timeout=connection_timeout):
            raise TimeoutError("Timeout waiting for both clients to connect")
        # Check for any connection errors
        errors = []
        while True:
            try:
                errors.append(connection_errors.get_nowait())
            except multiprocessing.queues.Empty:
                break
        if errors:
            raise ConnectionError("\n".join(errors))
            
        logger.info("Both clients connected successfully")
        yield client1, client2
        
    except Exception as e:
        logger.error(f"Error setting up client connections: {e}")
        raise
        
    finally:
        logger.info("Cleaning up client connections...")
        for idx, client in enumerate([client1, client2], 1):
            if hasattr(client, 'connected') and client.connected:
                try:
                    logger.info(f"Disconnecting client {idx}...")
                    client.disconnect()
                except Exception as e:
                    logger.error(f"Error disconnecting client {idx}: {e}")

@pytest.fixture
def complete_team(two_player_clients, reset_state, request):
    """Fixture to set up a complete team with two players"""
    import threading
    player1, player2 = two_player_clients
    team_name = "TestTeam"
    team_data = {}
    
    # Events for synchronization
    team_created = multiprocessing.Event()
    team_joined = multiprocessing.Event()
    
    def cleanup_connections():
        try:
            if player1.connected:
                player1.disconnect()
            if player2.connected:
                player2.disconnect()
        except Exception:
            pass

    try:
        @player1.on('team_created')
        def on_team_created(data):
            logger.info("Team created event received")
            team_data.update(data)
            team_created.set()
        
        @player2.on('joined_team')
        def on_team_joined(data):
            logger.info("Team joined event received")
            team_joined.set()
        
        # Create and join team
        logger.info("Emitting create_team event...")
        player1.emit('create_team', {'team_name': team_name})
        if not team_created.wait(timeout=5):
            logger.error("Team creation timed out")
            raise TimeoutError("Team creation timed out")
        
        logger.info("Emitting join_team event...")
        player2.emit('join_team', {'team_name': team_name})
        if not team_joined.wait(timeout=5):
            logger.error("Team joining timed out")
            raise TimeoutError("Team joining timed out")
        
        yield player1, player2, team_name, team_data
    
    except Exception as e:
        logger.error(f"Error in complete_team fixture: {str(e)}")
        cleanup_connections()
        raise
    
    finally:
        cleanup_connections()
