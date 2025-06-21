"""
Dashboard simulation for CHSH Game load testing.

Simulates dashboard connections and game control operations.
"""

import asyncio
import time
from typing import Optional, Dict, Any
import socketio
from loguru import logger

from .config import LoadTestConfig


class DashboardSimulator:
    """
    Simulates dashboard client for game control.
    
    Handles connection to server as dashboard client and game control operations.
    """
    
    def __init__(self, config: LoadTestConfig):
        self.config = config
        self.socket: Optional[socketio.AsyncClient] = None
        self.connected = False
        self.game_started = False
        self.should_shutdown = False
        
        # Dashboard state
        self.dashboard_data: Dict[str, Any] = {}
        self.teams_data: list = []
        
    async def connect(self) -> bool:
        """
        Connect to server as dashboard client.
        
        Returns:
            True if connection successful
        """
        if not self.config.enable_dashboard_simulation:
            logger.info("Dashboard simulation disabled")
            return True
            
        try:
            logger.info("Connecting dashboard simulator...")
            
            self.socket = socketio.AsyncClient(
                reconnection=False,  # Dashboard should be stable
                logger=False,
                engineio_logger=False
            )
            
            # Register event handlers
            self._register_event_handlers()
            
            # Connect with timeout
            await asyncio.wait_for(
                self.socket.connect(self.config.deployment_url),
                timeout=self.config.connection_timeout
            )
            
            # Join as dashboard client
            await self.socket.emit('dashboard_join')
            
            # Wait for dashboard_update to confirm connection
            await asyncio.sleep(2.0)
            
            if self.connected:
                logger.info("Dashboard simulator connected successfully")
                return True
            else:
                logger.error("Dashboard simulator failed to receive initial data")
                return False
                
        except asyncio.TimeoutError:
            logger.error("Dashboard connection timeout")
            return False
        except Exception as e:
            logger.error(f"Dashboard connection failed: {str(e)}")
            return False
    
    def _register_event_handlers(self):
        """Register Socket.io event handlers for dashboard."""
        
        @self.socket.event
        async def connect():
            logger.debug("Dashboard Socket.io connected")
        
        @self.socket.event
        async def disconnect():
            logger.debug("Dashboard Socket.io disconnected")
            self.connected = False
        
        @self.socket.event
        async def dashboard_update(data):
            """Handle dashboard update with game state."""
            self.connected = True
            self.dashboard_data = data
            
            # Update game state
            game_state = data.get('game_state', {})
            self.game_started = game_state.get('started', False)
            
            # Update teams data
            self.teams_data = data.get('teams', [])
            
            logger.debug(f"Dashboard update: {len(self.teams_data)} teams, "
                        f"game_started={self.game_started}")
        
        @self.socket.event
        async def team_status_changed_for_dashboard(data):
            """Handle team status updates."""
            self.teams_data = data.get('teams', [])
            logger.debug(f"Team status update: {len(self.teams_data)} teams")
        
        @self.socket.event
        async def game_started():
            """Handle game start confirmation."""
            self.game_started = True
            logger.info("Dashboard received game start confirmation")
        
        @self.socket.event
        async def game_reset_complete():
            """Handle game reset completion."""
            self.game_started = False
            logger.info("Dashboard received game reset confirmation")
        
        @self.socket.event
        async def new_answer_for_dashboard(data):
            """Handle real-time answer updates."""
            # Just log for monitoring, don't need to store
            logger.debug(f"Dashboard received answer from team {data.get('team_name')}")
        
        @self.socket.event
        async def error(data):
            """Handle error events."""
            error_msg = data.get('message', 'Unknown error')
            logger.warning(f"Dashboard received error: {error_msg}")
    
    async def wait_for_teams(self, expected_teams: int, timeout: float = 60.0) -> bool:
        """
        Wait for teams to be created and ready.
        
        Args:
            expected_teams: Number of teams to wait for
            timeout: Maximum time to wait
            
        Returns:
            True if teams are ready
        """
        if not self.config.enable_dashboard_simulation:
            return True
            
        logger.info(f"Waiting for {expected_teams} teams to be ready...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            if self.should_shutdown:
                return False
                
            active_teams = [team for team in self.teams_data if team.get('is_active', False)]
            full_teams = [team for team in active_teams 
                         if team.get('status') in ['active', 'full']]
            
            logger.debug(f"Teams status: {len(active_teams)} active, {len(full_teams)} full")
            
            if len(full_teams) >= expected_teams:
                logger.info(f"All {expected_teams} teams are ready!")
                return True
            
            await asyncio.sleep(1.0)
        
        logger.warning(f"Timeout waiting for teams: {len(full_teams)}/{expected_teams} ready")
        return len(full_teams) > 0  # Accept partial success
    
    async def start_game(self) -> bool:
        """
        Start the game via dashboard.
        
        Returns:
            True if game start was successful
        """
        if not self.config.enable_dashboard_simulation:
            logger.info("Dashboard simulation disabled - game start skipped")
            return True
            
        if not self.socket or not self.connected:
            logger.error("Dashboard not connected, cannot start game")
            return False
        
        try:
            logger.info("Starting game via dashboard...")
            
            # Send start_game event
            await self.socket.emit('start_game')
            
            # Wait for confirmation
            start_time = time.time()
            timeout = 30.0
            
            while time.time() - start_time < timeout:
                if self.should_shutdown:
                    return False
                    
                if self.game_started:
                    logger.info("Game started successfully!")
                    return True
                
                await asyncio.sleep(0.5)
            
            logger.error("Game start timeout - no confirmation received")
            return False
            
        except Exception as e:
            logger.error(f"Failed to start game: {str(e)}")
            return False
    
    async def pause_game(self) -> bool:
        """
        Pause/unpause the game via dashboard.
        
        Returns:
            True if operation successful
        """
        if not self.config.enable_dashboard_simulation:
            return True
            
        if not self.socket or not self.connected:
            logger.error("Dashboard not connected, cannot pause game")
            return False
        
        try:
            logger.info("Toggling game pause state...")
            await self.socket.emit('pause_game')
            
            # Note: The server toggles pause state, so we don't track it here
            await asyncio.sleep(1.0)  # Give server time to process
            return True
            
        except Exception as e:
            logger.error(f"Failed to pause game: {str(e)}")
            return False
    
    async def restart_game(self) -> bool:
        """
        Restart the game via dashboard.
        
        Returns:
            True if restart successful
        """
        if not self.config.enable_dashboard_simulation:
            return True
            
        if not self.socket or not self.connected:
            logger.error("Dashboard not connected, cannot restart game")
            return False
        
        try:
            logger.info("Restarting game via dashboard...")
            
            # Send restart_game event
            await self.socket.emit('restart_game')
            
            # Wait for reset confirmation
            start_time = time.time()
            timeout = 30.0
            original_state = self.game_started
            
            while time.time() - start_time < timeout:
                if self.should_shutdown:
                    return False
                    
                # Game should be stopped after restart
                if original_state and not self.game_started:
                    logger.info("Game restarted successfully!")
                    return True
                
                await asyncio.sleep(0.5)
            
            logger.warning("Game restart timeout - no confirmation received")
            return False
            
        except Exception as e:
            logger.error(f"Failed to restart game: {str(e)}")
            return False
    
    async def monitor_dashboard(self, duration: float = 300.0):
        """
        Monitor dashboard data for the duration of the test.
        
        Args:
            duration: How long to monitor in seconds
        """
        if not self.config.enable_dashboard_simulation:
            return
            
        logger.info(f"Starting dashboard monitoring for {duration}s...")
        
        start_time = time.time()
        last_report_time = start_time
        report_interval = 30.0  # Report every 30 seconds
        
        while time.time() - start_time < duration and not self.should_shutdown:
            current_time = time.time()
            
            # Periodic status report
            if current_time - last_report_time >= report_interval:
                self._log_dashboard_status()
                last_report_time = current_time
            
            await asyncio.sleep(5.0)
        
        logger.info("Dashboard monitoring completed")
    
    def _log_dashboard_status(self):
        """Log current dashboard status."""
        if not self.connected:
            logger.warning("Dashboard disconnected")
            return
        
        active_teams = len([t for t in self.teams_data if t.get('is_active', False)])
        total_players = self.dashboard_data.get('connected_players_count', 0)
        total_answers = self.dashboard_data.get('total_answers_count', 0)
        
        logger.info(f"Dashboard status: {active_teams} active teams, "
                   f"{total_players} connected players, {total_answers} total answers")
    
    async def disconnect(self):
        """Gracefully disconnect dashboard."""
        self.should_shutdown = True
        
        if self.socket and self.socket.connected:
            try:
                await self.socket.disconnect()
                logger.debug("Dashboard disconnected")
            except Exception as e:
                logger.warning(f"Dashboard disconnect error: {str(e)}")
        
        self.connected = False
    
    def get_status(self) -> Dict[str, Any]:
        """Get current dashboard status."""
        return {
            'connected': self.connected,
            'game_started': self.game_started,
            'teams_count': len(self.teams_data),
            'active_teams': len([t for t in self.teams_data if t.get('is_active', False)]),
            'total_players': self.dashboard_data.get('connected_players_count', 0),
            'total_answers': self.dashboard_data.get('total_answers_count', 0),
            'dashboard_data_keys': list(self.dashboard_data.keys())
        }