#!/usr/bin/env python3
"""
Test script to verify disconnect behavior during load test cancellation.

This script creates a few teams with players and then simulates mass disconnection
to verify that teams are properly cleaned up on the dashboard.
"""

import asyncio
import time
import signal
import logging
from typing import List
import socketio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

class TestPlayer:
    """Simple test player for disconnect testing."""
    
    def __init__(self, player_id: str, server_url: str):
        self.player_id = player_id
        self.server_url = server_url
        self.socket = None
        self.team_name = None
        self.connected = False
        
    async def connect(self):
        """Connect to the server."""
        try:
            self.socket = socketio.AsyncClient()
            
            @self.socket.event
            async def connect():
                logger.info(f"Player {self.player_id} connected")
                self.connected = True
            
            @self.socket.event
            async def disconnect():
                logger.info(f"Player {self.player_id} disconnected")
                self.connected = False
                
            @self.socket.event
            async def team_created(data):
                self.team_name = data.get('team_name')
                logger.info(f"Player {self.player_id} created team {self.team_name}")
                
            @self.socket.event
            async def team_joined(data):
                self.team_name = data.get('team_name')
                logger.info(f"Player {self.player_id} joined team {self.team_name}")
            
            await self.socket.connect(self.server_url)
            
            # Wait for connection to be established
            timeout = time.time() + 5
            while not self.connected and time.time() < timeout:
                await asyncio.sleep(0.1)
                
            return self.connected
            
        except Exception as e:
            logger.error(f"Player {self.player_id} connection failed: {e}")
            return False
    
    async def create_team(self, team_name: str):
        """Create a team."""
        if self.socket and self.connected:
            await self.socket.emit('create_team', {'team_name': team_name})
            await asyncio.sleep(0.5)  # Wait for team creation
    
    async def join_team(self, team_name: str):
        """Join a team."""
        if self.socket and self.connected:
            await self.socket.emit('join_team', {'team_name': team_name})
            await asyncio.sleep(0.5)  # Wait for team join
    
    async def disconnect(self):
        """Disconnect from the server."""
        if self.socket and self.connected:
            await self.socket.disconnect()
            self.connected = False

class DisconnectTest:
    """Test disconnect behavior."""
    
    def __init__(self, server_url: str = "http://localhost:8080", num_teams: int = 5):
        self.server_url = server_url
        self.num_teams = num_teams
        self.players: List[TestPlayer] = []
        self.should_stop = False
        
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown."""
        def signal_handler(signum, frame):
            logger.info(f"Received signal {signum}, initiating shutdown...")
            self.should_stop = True
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    async def run_test(self):
        """Run the disconnect test."""
        self.setup_signal_handlers()
        
        try:
            logger.info(f"Starting disconnect test with {self.num_teams} teams")
            
            # Create players
            await self.create_players()
            
            # Connect players
            await self.connect_players()
            
            # Create teams
            await self.create_teams()
            
            # Wait for user to check dashboard
            logger.info("Check the dashboard to see active teams. Press Ctrl+C to simulate mass disconnect...")
            
            # Wait for interrupt
            while not self.should_stop:
                await asyncio.sleep(1)
            
            # Simulate mass disconnection
            logger.info("Simulating mass disconnection...")
            await self.disconnect_all()
            
            # Wait a bit for cleanup
            await asyncio.sleep(2)
            logger.info("Test complete. Check dashboard to verify teams are cleaned up.")
            
        except Exception as e:
            logger.error(f"Test failed: {e}")
        finally:
            await self.cleanup()
    
    async def create_players(self):
        """Create player instances."""
        total_players = self.num_teams * 2
        for i in range(total_players):
            player_id = f"test_player_{i+1:03d}"
            player = TestPlayer(player_id, self.server_url)
            self.players.append(player)
        
        logger.info(f"Created {len(self.players)} test players")
    
    async def connect_players(self):
        """Connect all players."""
        logger.info("Connecting players...")
        
        connection_tasks = [player.connect() for player in self.players]
        results = await asyncio.gather(*connection_tasks, return_exceptions=True)
        
        successful = sum(1 for result in results if result is True)
        logger.info(f"Connected {successful}/{len(self.players)} players")
    
    async def create_teams(self):
        """Create teams."""
        logger.info(f"Creating {self.num_teams} teams...")
        
        for i in range(self.num_teams):
            team_name = f"TestTeam{i+1:03d}"
            creator = self.players[i * 2]
            joiner = self.players[i * 2 + 1]
            
            # Creator creates team
            await creator.create_team(team_name)
            
            # Joiner joins team
            await joiner.join_team(team_name)
            
            logger.info(f"Created team {team_name}")
        
        logger.info(f"Created {self.num_teams} teams")
    
    async def disconnect_all(self):
        """Disconnect all players simultaneously."""
        logger.info("Disconnecting all players...")
        
        disconnect_tasks = [player.disconnect() for player in self.players]
        await asyncio.gather(*disconnect_tasks, return_exceptions=True)
        
        logger.info("All players disconnected")
    
    async def cleanup(self):
        """Clean up resources."""
        try:
            for player in self.players:
                if player.connected:
                    await player.disconnect()
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

async def main():
    """Main function."""
    test = DisconnectTest()
    await test.run_test()

if __name__ == "__main__":
    asyncio.run(main())