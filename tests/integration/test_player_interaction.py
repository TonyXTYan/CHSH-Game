import pytest
import time
from flask_socketio import SocketIOTestClient
from wsgi import app
from src.config import socketio as server_socketio

@pytest.fixture
def socket_client():
    """Create a test client for SocketIO"""
    client = SocketIOTestClient(app, server_socketio)
    print("\nTest client created")  # Debug output
    yield client
    print("\nDisconnecting test client")  # Debug output
    client.disconnect()

@pytest.fixture
def app_context():
    with app.app_context():
        app.extensions['socketio'] = server_socketio
        yield app

@pytest.mark.integration
def test_player_connection(app_context, socket_client):
    """Test that a player can successfully connect to the game server"""
    # print("\nStarting connection test")  # Debug output
    
    # Verify the client has a connection
    assert socket_client.connected, "Client failed to connect to server"
    # print("Client connection verified")  # Debug output
    
    # Wait a short time for server processing
    time.sleep(0.1)
    
    # Get all received messages after connection
    messages = socket_client.get_received()
    # print(f"Received {len(messages)} messages: {messages}")  # Debug output
    
    # Verify we received connection_established
    connection_messages = [msg for msg in messages if msg.get('name') == 'connection_established']
    
    # More detailed assertion message
    if not connection_messages:
        # print("Available message names:", [msg.get('name') for msg in messages])
        assert False, "Did not receive connection_established event"
    
    assert len(connection_messages) == 1, f"Expected 1 connection_established message, got {len(connection_messages)}"
    
    # Verify the data structure
    data = connection_messages[0].get('args', [{}])[0]
    # print(f"Connection data received: {data}")  # Debug output
    
    assert 'game_started' in data, "connection_established missing game_started status"
    assert 'available_teams' in data, "connection_established missing available_teams list"
    assert isinstance(data['game_started'], bool), "game_started should be a boolean"
    assert isinstance(data['available_teams'], list), "available_teams should be a list"