#!/usr/bin/env python3
"""
Debug script to test disconnect detection and rejoin functionality.
"""

import socketio
import time
import json
from threading import Event

class TestClient:
    def __init__(self, name):
        self.name = name
        self.sio = socketio.Client()
        self.connected = False
        self.team_data = None
        
        # Event handlers
        @self.sio.on('connect')
        def on_connect():
            self.connected = True
            print(f"[{self.name}] Connected to server")
        
        @self.sio.on('disconnect')
        def on_disconnect():
            self.connected = False
            print(f"[{self.name}] Disconnected from server")
        
        @self.sio.on('team_created')
        def on_team_created(data):
            self.team_data = data
            print(f"[{self.name}] Team created: {data}")
        
        @self.sio.on('team_joined')
        def on_team_joined(data):
            self.team_data = data
            print(f"[{self.name}] Team joined: {data}")
        
        @self.sio.on('team_status_update')
        def on_team_status_update(data):
            print(f"[{self.name}] Team status update: {data}")
        
        @self.sio.on('player_left')
        def on_player_left(data):
            print(f"[{self.name}] Player left: {data}")
        
        @self.sio.on('rejoin_team_response')
        def on_rejoin_response(data):
            print(f"[{self.name}] Rejoin response: {data}")
        
        @self.sio.on('error')
        def on_error(data):
            print(f"[{self.name}] Error: {data}")
    
    def connect(self, url="http://localhost:8080"):
        try:
            self.sio.connect(url)
            time.sleep(0.5)  # Wait for connection
        except Exception as e:
            print(f"[{self.name}] Failed to connect: {e}")
    
    def disconnect(self):
        if self.connected:
            self.sio.disconnect()
            time.sleep(0.5)  # Wait for disconnect
    
    def create_team(self, team_name):
        if self.connected:
            self.sio.emit('create_team', {'team_name': team_name})
            time.sleep(1)  # Wait for response
    
    def join_team(self, team_name):
        if self.connected:
            self.sio.emit('join_team', {'team_name': team_name})
            time.sleep(1)  # Wait for response
    
    def rejoin_team(self, team_name, team_id):
        if self.connected:
            print(f"[{self.name}] Attempting rejoin with team_name='{team_name}', team_id='{team_id}'")
            self.sio.emit('rejoin_team', {'team_name': team_name, 'team_id': team_id})
            time.sleep(1)  # Wait for response


def test_disconnect_rejoin():
    print("=== Testing Disconnect and Rejoin Functionality ===")
    
    # Create two clients
    player1 = TestClient("Player1")
    player2 = TestClient("Player2")
    
    try:
        # Connect both players
        print("\n1. Connecting players...")
        player1.connect()
        player2.connect()
        
        if not (player1.connected and player2.connected):
            print("ERROR: Failed to connect players")
            return
        
        # Player 1 creates team
        print("\n2. Player 1 creating team...")
        player1.create_team("TestTeam")
        
        if not player1.team_data:
            print("ERROR: Player 1 didn't receive team_created event")
            return
        
        team_name = player1.team_data.get('team_name')
        team_id = player1.team_data.get('team_id')
        print(f"   Team created: name='{team_name}', id='{team_id}'")
        
        # Player 2 joins team
        print("\n3. Player 2 joining team...")
        player2.join_team(team_name)
        
        if not player2.team_data:
            print("ERROR: Player 2 didn't receive team_joined event")
            return
        
        p2_team_id = player2.team_data.get('team_id')
        print(f"   Player 2 joined: team_id='{p2_team_id}'")
        
        # Simulate player 2 disconnect (browser refresh)
        print("\n4. Player 2 disconnects (simulating browser refresh)...")
        player2.disconnect()
        
        # Wait a bit for disconnect to be processed
        time.sleep(2)
        
        # Player 2 reconnects and tries to rejoin
        print("\n5. Player 2 reconnects and attempts rejoin...")
        player2.connect()
        
        if player2.connected:
            player2.rejoin_team(team_name, p2_team_id)
        else:
            print("ERROR: Player 2 failed to reconnect")
            return
        
        print("\n6. Test completed - check output above for issues")
        
    except Exception as e:
        print(f"Test failed with error: {e}")
    
    finally:
        # Cleanup
        print("\n7. Cleaning up...")
        player1.disconnect()
        player2.disconnect()


if __name__ == "__main__":
    test_disconnect_rejoin()