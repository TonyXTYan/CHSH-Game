import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import threading
import time
from src.main import app, socketio # Assuming your app and socketio instances are here

# Helper to run the Flask-SocketIO app in a separate thread
def run_server():
    # Use a specific port known for testing to avoid conflicts
    socketio.run(app, host='0.0.0.0', port=5001, use_reloader=False, debug=False)

@pytest.fixture(scope="module")
def live_server_url():
    # Start the server in a thread
    server_thread = threading.Thread(target=run_server, daemon=True)
    server_thread.start()
    # Give the server a moment to start
    time.sleep(3) # Increased sleep time for server startup
    yield "http://localhost:5001"
    # Teardown (server thread is daemon, will exit with main thread)

@pytest.fixture(scope="function")
def player_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080") # Optional: specify window size
    driver = webdriver.Chrome(options=chrome_options)
    yield driver
    driver.quit()

@pytest.fixture(scope="function")
def host_driver():
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080") # Optional: specify window size
    driver = webdriver.Chrome(options=chrome_options)
    yield driver
    driver.quit()

def test_player_and_host_connection_status(live_server_url, player_driver, host_driver):
    base_url = live_server_url

    # Player navigates to index.html
    player_driver.get(base_url + "/")
    # Host navigates to dashboard.html
    host_driver.get(base_url + "/dashboard")

    # Wait for and assert player connection status
    # The player's connection status ID is 'connectionStatus'
    player_connection_status_element = WebDriverWait(player_driver, 20).until(
        EC.presence_of_element_located((By.ID, "connectionStatus"))
    )
    # Wait for the text to be "Connected to server!"
    WebDriverWait(player_driver, 20).until(
        EC.text_to_be_present_in_element((By.ID, "connectionStatus"), "Connected to server!")
    )
    assert "Connected to server!" in player_connection_status_element.text, \
        f"Player connection status was: {player_connection_status_element.text}"

    # Wait for and assert host connection status
    # The host's dashboard connection status ID is 'connection-status-dash'
    host_connection_status_element = WebDriverWait(host_driver, 20).until(
        EC.presence_of_element_located((By.ID, "connection-status-dash"))
    )
    # Wait for the text to be "Connected to server"
    WebDriverWait(host_driver, 20).until(
        EC.text_to_be_present_in_element((By.ID, "connection-status-dash"), "Connected to server")
    )
    assert "Connected to server" in host_connection_status_element.text, \
        f"Host connection status was: {host_connection_status_element.text}"
