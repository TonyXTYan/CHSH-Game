"""
Player simulation for CHSH Game load testing.

Simulates individual players with Socket.io connections and game interactions.
"""

import asyncio
import random
import time
from typing import Optional, Dict, Any, Callable
from enum import Enum
import socketio
from loguru import logger

from .config import LoadTestConfig, ResponsePatternType
from .metrics import PlayerMetrics


class PlayerState(Enum):
    """Player state during load testing."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    CREATING_TEAM = "creating_team"
    JOINING_TEAM = "joining_team"
    IN_TEAM = "in_team"
    PLAYING = "playing"
    ERROR = "error"


class Player:
    """
    Simulates a single player in the CHSH Game.
    
    Handles Socket.io connection, team management, and game interactions.
    """
    
    def __init__(self, player_id: str, config: LoadTestConfig, metrics_callback: Optional[Callable] = None):
        self.player_id = player_id
        self.config = config
        self.metrics_callback = metrics_callback
        
        # Connection state
        self.socket: Optional[socketio.AsyncClient] = None
        self.state = PlayerState.DISCONNECTED
        self.connected_at: Optional[float] = None
        
        # Team information
        self.team_name: Optional[str] = None
        self.team_id: Optional[int] = None
        self.is_team_creator = False
        
        # Game state
        self.current_round: Optional[Dict[str, Any]] = None
        self.rounds_completed = 0
        self.game_started = False
        
        # Metrics
        self.metrics = PlayerMetrics(self.player_id)
        
        # Response timing
        self.last_question_time: Optional[float] = None
        
        # Shutdown flag
        self.should_shutdown = False
    
    async def connect(self) -> bool:
        """
        Establish Socket.io connection to the server.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            self.state = PlayerState.CONNECTING
            self.socket = socketio.AsyncClient(
                reconnection=True,
                reconnection_attempts=3,
                reconnection_delay=1,
                reconnection_delay_max=5,
                logger=False,  # Disable socketio debug logging
                engineio_logger=False
            )
            
            # Register event handlers
            self._register_event_handlers()
            
            # Connect with timeout
            start_time = time.time()
            await asyncio.wait_for(
                self.socket.connect(self.config.deployment_url),
                timeout=self.config.connection_timeout
            )
            
            connection_time = time.time() - start_time
            self.connected_at = time.time()
            self.state = PlayerState.CONNECTED
            
            # Record metrics
            self.metrics.record_connection_time(connection_time)
            if self.metrics_callback:
                self.metrics_callback('connection_success', self.player_id, connection_time)
            
            logger.debug(f"Player {self.player_id} connected in {connection_time:.2f}s")
            return True
            
        except asyncio.TimeoutError:
            logger.warning(f"Player {self.player_id} connection timeout")
            self.state = PlayerState.ERROR
            self.metrics.record_error('connection_timeout')
            if self.metrics_callback:
                self.metrics_callback('connection_timeout', self.player_id)
            return False
            
        except Exception as e:
            logger.error(f"Player {self.player_id} connection failed: {str(e)}")
            self.state = PlayerState.ERROR
            self.metrics.record_error(f'connection_error: {str(e)}')
            if self.metrics_callback:
                self.metrics_callback('connection_error', self.player_id, str(e))
            return False
    
    def _register_event_handlers(self):
        """Register Socket.io event handlers."""
        
        @self.socket.event
        async def connect():
            logger.debug(f"Player {self.player_id} Socket.io connected")
        
        @self.socket.event
        async def disconnect():
            logger.debug(f"Player {self.player_id} Socket.io disconnected")
            if not self.should_shutdown:
                self.state = PlayerState.DISCONNECTED
        
        @self.socket.event
        async def connection_established(data):
            """Handle connection_established event from server."""
            logger.debug(f"Player {self.player_id} connection established: {data}")
            self.game_started = data.get('game_started', False)
        
        @self.socket.event
        async def error(data):
            """Handle error events from server."""
            error_msg = data.get('message', 'Unknown error')
            logger.warning(f"Player {self.player_id} received error: {error_msg}")
            self.metrics.record_error(f'server_error: {error_msg}')
        
        @self.socket.event
        async def team_created(data):
            """Handle team_created event."""
            self.team_name = data.get('team_name')
            self.team_id = data.get('team_id')
            self.is_team_creator = True
            self.state = PlayerState.IN_TEAM
            logger.debug(f"Player {self.player_id} created team {self.team_name}")
        
        @self.socket.event
        async def team_joined(data):
            """Handle team_joined event."""
            self.team_name = data.get('team_name')
            self.team_id = data.get('team_id')
            self.is_team_creator = False
            self.state = PlayerState.IN_TEAM
            logger.debug(f"Player {self.player_id} joined team {self.team_name}")
        
        @self.socket.event
        async def game_start(data):
            """Handle game start event."""
            self.game_started = True
            logger.debug(f"Player {self.player_id} game started")
        
        @self.socket.event
        async def new_question(data):
            """Handle new question event and submit answer."""
            await self._handle_new_question(data)
        
        @self.socket.event
        async def answer_confirmed(data):
            """Handle answer confirmation."""
            self.metrics.record_answer_confirmed()
            logger.debug(f"Player {self.player_id} answer confirmed: {data.get('message')}")
        
        @self.socket.event
        async def round_complete(data):
            """Handle round completion."""
            self.rounds_completed += 1
            self.current_round = None
            logger.debug(f"Player {self.player_id} completed round {self.rounds_completed}")
    
    async def create_team(self, team_name: str) -> bool:
        """
        Create a new team.
        
        Args:
            team_name: Name for the new team
            
        Returns:
            True if team creation successful
        """
        if not self.socket or self.state != PlayerState.CONNECTED:
            return False
        
        try:
            self.state = PlayerState.CREATING_TEAM
            start_time = time.time()
            
            await self.socket.emit('create_team', {'team_name': team_name})
            
            # Wait for team_created event (with timeout)
            timeout_time = time.time() + 10.0
            while self.state == PlayerState.CREATING_TEAM and time.time() < timeout_time:
                await asyncio.sleep(0.1)
            
            if self.state == PlayerState.IN_TEAM:
                creation_time = time.time() - start_time
                self.metrics.record_team_operation('create', creation_time)
                if self.metrics_callback:
                    self.metrics_callback('team_created', self.player_id, creation_time)
                return True
            else:
                self.metrics.record_error('team_creation_timeout')
                return False
                
        except Exception as e:
            logger.error(f"Player {self.player_id} team creation failed: {str(e)}")
            self.state = PlayerState.ERROR
            self.metrics.record_error(f'team_creation_error: {str(e)}')
            return False
    
    async def join_team(self, team_name: str) -> bool:
        """
        Join an existing team.
        
        Args:
            team_name: Name of team to join
            
        Returns:
            True if join successful
        """
        if not self.socket or self.state != PlayerState.CONNECTED:
            return False
        
        try:
            self.state = PlayerState.JOINING_TEAM
            start_time = time.time()
            
            await self.socket.emit('join_team', {'team_name': team_name})
            
            # Wait for team_joined event (with timeout)
            timeout_time = time.time() + 10.0
            while self.state == PlayerState.JOINING_TEAM and time.time() < timeout_time:
                await asyncio.sleep(0.1)
            
            if self.state == PlayerState.IN_TEAM:
                join_time = time.time() - start_time
                self.metrics.record_team_operation('join', join_time)
                if self.metrics_callback:
                    self.metrics_callback('team_joined', self.player_id, join_time)
                return True
            else:
                self.metrics.record_error('team_join_timeout')
                return False
                
        except Exception as e:
            logger.error(f"Player {self.player_id} team join failed: {str(e)}")
            self.state = PlayerState.ERROR
            self.metrics.record_error(f'team_join_error: {str(e)}')
            return False
    
    async def _handle_new_question(self, question_data: Dict[str, Any]):
        """
        Handle incoming question and submit answer after delay.
        
        Args:
            question_data: Question data from server
        """
        try:
            self.current_round = question_data
            self.last_question_time = time.time()
            
            round_id = question_data.get('round_id')
            item = question_data.get('item')
            round_number = question_data.get('round_number')
            
            logger.debug(f"Player {self.player_id} received question: Round {round_number}, Item {item}")
            
            # Calculate response delay based on pattern
            delay = self._calculate_response_delay()
            
            # Wait for the calculated delay
            await asyncio.sleep(delay)
            
            # Submit answer (randomly True or False)
            answer = random.choice([True, False])
            
            start_time = time.time()
            await self.socket.emit('submit_answer', {
                'round_id': round_id,
                'item': item,
                'answer': answer
            })
            
            response_time = time.time() - start_time
            total_time = time.time() - self.last_question_time
            
            self.metrics.record_question_response(delay, response_time, total_time)
            
            if self.metrics_callback:
                self.metrics_callback('answer_submitted', self.player_id, {
                    'delay': delay,
                    'response_time': response_time,
                    'total_time': total_time
                })
            
            logger.debug(f"Player {self.player_id} submitted answer: {answer} (delay: {delay:.2f}s)")
            
        except Exception as e:
            logger.error(f"Player {self.player_id} question handling failed: {str(e)}")
            self.metrics.record_error(f'question_handling_error: {str(e)}')
    
    def _calculate_response_delay(self) -> float:
        """
        Calculate response delay based on configured pattern.
        
        Returns:
            Delay in seconds
        """
        pattern = self.config.response_pattern
        min_delay = self.config.min_response_delay
        max_delay = self.config.max_response_delay
        
        if pattern == ResponsePatternType.RANDOM:
            return random.uniform(min_delay, max_delay)
        
        elif pattern == ResponsePatternType.STEADY:
            # Consistent timing with small variance
            target = (min_delay + max_delay) / 2
            variance = (max_delay - min_delay) * 0.1
            return max(min_delay, min(max_delay, random.normalvariate(target, variance)))
        
        elif pattern == ResponsePatternType.BURST:
            # Quick responses in bursts, then longer pauses
            return random.choice([
                min_delay,  # Quick response
                min_delay + 0.1,
                min_delay + 0.2,
                max_delay,  # Long pause
                max_delay * 1.2
            ])
        
        elif pattern == ResponsePatternType.HUMAN_LIKE:
            # Log-normal distribution mimics human response times
            import numpy as np
            mean_log = (min_delay + max_delay) / 2
            sigma = 0.3
            delay = np.random.lognormal(mean=mean_log, sigma=sigma)
            return max(min_delay, min(max_delay * 1.5, delay))
        
        else:
            return random.uniform(min_delay, max_delay)
    
    async def disconnect(self):
        """Gracefully disconnect the player."""
        self.should_shutdown = True
        
        if self.socket and self.socket.connected:
            try:
                await self.socket.disconnect()
            except Exception as e:
                logger.warning(f"Player {self.player_id} disconnect error: {str(e)}")
        
        self.state = PlayerState.DISCONNECTED
        logger.debug(f"Player {self.player_id} disconnected")
    
    def get_status(self) -> Dict[str, Any]:
        """Get current player status for monitoring."""
        return {
            'player_id': self.player_id,
            'state': self.state.value,
            'team_name': self.team_name,
            'team_id': self.team_id,
            'is_team_creator': self.is_team_creator,
            'rounds_completed': self.rounds_completed,
            'game_started': self.game_started,
            'connected_duration': time.time() - self.connected_at if self.connected_at else 0,
            'metrics': self.metrics.get_summary()
        }