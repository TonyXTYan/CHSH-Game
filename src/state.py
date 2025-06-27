import time
import os
from typing import Dict, Set, Any, Optional
from collections import defaultdict, deque

class GameState:
    def __init__(self):
        self.active_teams = {}  # {team_name: {'players': [], 'team_id': db_team_id, 'current_round_number': 0, 'combo_tracker': {}, 'current_db_round_id': None, 'answered_current_round': {}, 'player_slots': {sid: slot_number}}}
        self.player_to_team = {}  # {sid: team_name}
        self.connected_players = set()  # All connected player SIDs
        self.dashboard_clients = set() # Stores SIDs of connected dashboard clients
        self.game_started = False # Track if game has started
        self.game_paused = False # Track if game is paused
        self.answer_stream_enabled = False # Track if answer streaming is enabled
        self.game_mode = 'classic'  # Track current game mode: 'classic' or 'new'
        # Store team ID to team name mapping for faster lookups
        self.team_id_to_name = {} # {team_id: team_name}
        # Track disconnected players for reconnection - maps team_name to disconnected player info
        self.disconnected_players = {}  # {team_name: {'player_session_id': old_sid, 'player_slot': 1|2, 'disconnect_time': timestamp}}
        
        # Enhanced connection management
        self.connection_times: Dict[str, float] = {}
        self.connection_rate_tracker: deque = deque(maxlen=100)  # Track last 100 connections
        self.heartbeat_tracker: Dict[str, float] = {}
        self.reconnection_attempts: Dict[str, int] = defaultdict(int)
        
        # Load protection settings (more lenient during testing)
        self.max_connections_per_minute = int(os.environ.get('MAX_CONNECTIONS_PER_MINUTE', '60'))
        self.max_reconnection_attempts = 5
        self.heartbeat_timeout = 40  # Slightly longer than ping_timeout

    def reset(self):
        self.active_teams.clear()
        self.player_to_team.clear()
        self.connected_players.clear()
        self.dashboard_clients.clear()
        self.team_id_to_name.clear()
        self.disconnected_players.clear()
        self.game_started = False
        self.game_paused = False
        self.answer_stream_enabled = False
        self.game_mode = 'classic'  # Reset game mode to classic
        
        # Keep connection management state for stability
        # Only clear old heartbeat entries (older than 60 seconds)
        current_time = time.time()
        old_heartbeats = [sid for sid, last_beat in self.heartbeat_tracker.items() 
                         if current_time - last_beat > 60]
        for sid in old_heartbeats:
            self.heartbeat_tracker.pop(sid, None)
            
        # Reset reconnection attempts for fresh start
        self.reconnection_attempts.clear()

    def get_player_slot(self, team_name, sid):
        """Get the database player slot (1 or 2) for a session ID in a team"""
        team_info = self.active_teams.get(team_name)
        if not team_info:
            return None
        return team_info.get('player_slots', {}).get(sid)
    
    def set_player_slot(self, team_name, sid, slot):
        """Set the database player slot for a session ID in a team"""
        team_info = self.active_teams.get(team_name)
        if team_info:
            if 'player_slots' not in team_info:
                team_info['player_slots'] = {}
            team_info['player_slots'][sid] = slot

    def can_accept_connection(self) -> bool:
        """Check if server can accept new connection based on rate limiting"""
        current_time = time.time()
        
        # Remove old connection timestamps (older than 1 minute)
        while self.connection_rate_tracker and current_time - self.connection_rate_tracker[0] > 60:
            self.connection_rate_tracker.popleft()
        
        # Check if under rate limit
        return len(self.connection_rate_tracker) < self.max_connections_per_minute
    
    def record_connection(self, sid: str) -> None:
        """Record a new connection with timestamp"""
        current_time = time.time()
        self.connection_times[sid] = current_time
        self.connection_rate_tracker.append(current_time)
        self.update_heartbeat(sid)
    
    def record_disconnection(self, sid: str) -> None:
        """Clean up connection tracking for disconnected client"""
        self.connection_times.pop(sid, None)
        self.heartbeat_tracker.pop(sid, None)
        self.connected_players.discard(sid)
        self.dashboard_clients.discard(sid)
    
    def update_heartbeat(self, sid: str) -> None:
        """Update last heartbeat timestamp for a client"""
        self.heartbeat_tracker[sid] = time.time()
    
    def get_stale_connections(self) -> Set[str]:
        """Get connections that haven't sent heartbeat within timeout period"""
        current_time = time.time()
        stale = set()
        for sid, last_heartbeat in self.heartbeat_tracker.items():
            if current_time - last_heartbeat > self.heartbeat_timeout:
                stale.add(sid)
        return stale
    
    def can_reconnect(self, sid: str) -> bool:
        """Check if client can attempt reconnection"""
        return self.reconnection_attempts[sid] < self.max_reconnection_attempts
    
    def record_reconnection_attempt(self, sid: str) -> None:
        """Record a reconnection attempt"""
        self.reconnection_attempts[sid] += 1
    
    def clear_reconnection_attempts(self, sid: str) -> None:
        """Clear reconnection attempts after successful connection"""
        self.reconnection_attempts.pop(sid, None)

# Global state instance
state = GameState()
