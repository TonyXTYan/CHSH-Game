#!/usr/bin/env python3
"""
Simple test script to verify Socket.IO connection stability improvements.
This script connects to the server and monitors for disconnections.
"""

import socketio
import time
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create Socket.IO client with optimized settings for interactive gameplay
# Note: ping_timeout and ping_interval are configured on the server side and in JavaScript clients
# The Python client uses default Engine.IO settings which are appropriate for testing
sio = socketio.Client(
    logger=True,
    engineio_logger=True,
    reconnection=True,
    reconnection_attempts=5,
    reconnection_delay=1000,
    reconnection_delay_max=5000
)

connection_count = 0
disconnection_count = 0

@sio.event
def connect():
    global connection_count
    connection_count += 1
    logger.info(f"Connected to server (connection #{connection_count})")

@sio.event
def disconnect():
    global disconnection_count
    disconnection_count += 1
    logger.info(f"Disconnected from server (disconnection #{disconnection_count})")

@sio.event
def connect_error(data):
    logger.error(f"Connection error: {data}")

@sio.event
def server_shutdown():
    logger.info("Server is shutting down")

def main():
    server_url = "http://localhost:8080"
    
    try:
        logger.info(f"Attempting to connect to {server_url}")
        sio.connect(server_url)
        
        # Keep the connection alive for 60 seconds
        logger.info("Connection established. Monitoring for 60 seconds...")
        start_time = time.time()
        
        while time.time() - start_time < 60:
            if not sio.connected:
                logger.warning("Connection lost, attempting to reconnect...")
                try:
                    sio.connect(server_url)
                except Exception as e:
                    logger.error(f"Reconnection failed: {e}")
                    break
            time.sleep(1)
        
        logger.info(f"Test completed. Connections: {connection_count}, Disconnections: {disconnection_count}")
        
    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        if sio.connected:
            sio.disconnect()

if __name__ == "__main__":
    main() 