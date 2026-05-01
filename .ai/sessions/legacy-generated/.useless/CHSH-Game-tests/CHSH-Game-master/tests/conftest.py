import os
import sys
import pytest
import threading
import time
import socketio
from flask import Flask
from flask_socketio import SocketIO

# Add the project root to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.config import app as flask_app, socketio as server_socketio
from src.state import state

@pytest.fixture(scope="session")
def app():
    """Flask application fixture."""
    return flask_app

@pytest.fixture(scope="session")
def socketio_server():
    """SocketIO server fixture."""
    return server_socketio

@pytest.fixture(scope="function")
def reset_state():
    """Reset the application state before each test."""
    state.reset()
    yield
    state.reset()

@pytest.fixture(scope="session")
def server_thread():
    """Start the server in a separate thread for integration tests."""
    def run_server():
        server_socketio.run(flask_app, host='127.0.0.1', port=5000, debug=False, use_reloader=False)
    
    thread = threading.Thread(target=run_server)
    thread.daemon = True
    thread.start()
    
    # Give the server time to start
    time.sleep(1)
    
    yield thread

@pytest.fixture(scope="function")
def client_sio():
    """Create a Socket.IO client for testing."""
    sio = socketio.Client()
    yield sio
    if sio.connected:
        sio.disconnect()

@pytest.fixture(scope="function")
def dashboard_client(client_sio, server_thread):
    """Create a Socket.IO client connected as a dashboard."""
    client_sio.connect('http://127.0.0.1:5000')
    client_sio.emit('register_dashboard')
    time.sleep(0.1)  # Give time for registration to complete
    yield client_sio
    if client_sio.connected:
        client_sio.disconnect()

@pytest.fixture(scope="function")
def player_client(client_sio, server_thread):
    """Create a Socket.IO client connected as a player."""
    client_sio.connect('http://127.0.0.1:5000')
    yield client_sio
    if client_sio.connected:
        client_sio.disconnect()

@pytest.fixture(scope="function")
def two_player_clients(server_thread):
    """Create two Socket.IO clients connected as players."""
    player1 = socketio.Client()
    player2 = socketio.Client()
    
    player1.connect('http://127.0.0.1:5000')
    player2.connect('http://127.0.0.1:5000')
    
    yield player1, player2
    
    if player1.connected:
        player1.disconnect()
    if player2.connected:
        player2.disconnect()

@pytest.fixture(scope="function")
def complete_team(two_player_clients):
    """Create a team with two players."""
    player1, player2 = two_player_clients
    
    # Create team events
    team_created = threading.Event()
    team_joined = threading.Event()
    team_name = "TestTeam"
    team_data = {}
    
    @player1.on('team_created')
    def on_team_created(data):
        team_data.update(data)
        team_created.set()
    
    @player2.on('joined_team')
    def on_joined_team(data):
        team_joined.set()
    
    # Create and join team
    player1.emit('create_team', {'team_name': team_name})
    assert team_created.wait(timeout=2), "Team creation timed out"
    
    player2.emit('join_team', {'team_name': team_name})
    assert team_joined.wait(timeout=2), "Team joining timed out"
    
    yield player1, player2, team_name, team_data
