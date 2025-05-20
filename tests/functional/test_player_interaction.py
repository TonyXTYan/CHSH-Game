import pytest
from src.config import app
from bs4 import BeautifulSoup

@pytest.fixture
def test_client():
    """Test client fixture for making HTTP requests"""
    return app.test_client()

def test_landing_page_initial_load(test_client):
    """
    Test that verifies the initial landing page load for a player.

    This test checks:
    1. The root URL returns a successful response
    2. The page contains the connection status element
    3. The initial connection message is present
    """
    print("[TEST] Starting landing page test")
    print(f"[TEST] App static folder: {app.static_folder}")
    print(f"[TEST] App URL map: {app.url_map}")
    
    This test checks:
    1. The root URL returns a successful response
    2. The page contains the connection status element
    3. The initial connection message is present
    
    Note: This test verifies the initial page state before WebSocket connection.
    The "Connected to server!" message appears after successful Socket.IO
    connection, which would require additional WebSocket testing setup.
    """
    # Make GET request to root URL
    response = test_client.get('/')
    
    # Check response is successful
    assert response.status_code == 200
    
    # Parse HTML content
    soup = BeautifulSoup(response.data, 'html.parser')
    
    # Verify connection status element exists
    connection_status = soup.find(id='connectionStatus')
    assert connection_status is not None
    
    # Verify status message element exists and contains initial connecting message
    status_message = soup.find(id='statusMessage')
    assert status_message is not None
    assert 'Connecting to server...' in status_message.text
    
    # Verify page title is correct
    assert soup.title.string == 'CHSH Game - Participant'