import time
import threading
from typing import Dict, Set, Optional, Any
from collections import deque

class ConnectionManager:
    """Manages connection queuing and stability during load spikes"""
    def __init__(self):
        self.connection_queue = deque()
        self.processing_connections = False
        self.last_sync_time = time.time()
        self.reconnection_tokens: Dict[str, Dict[str, Any]] = {}  # {token: {team_name, player_slot, timestamp}}
        # Store tokens by team and slot for easier retrieval
        self.team_slot_tokens: Dict[str, Dict[int, str]] = {}  # {team_name: {player_slot: token}}
        self._lock = threading.Lock()
    
    def queue_connection(self, sid: str, connect_time: float = None):
        """Queue a connection for processing to prevent overwhelming during spikes"""
        if connect_time is None:
            connect_time = time.time()
        
        with self._lock:
            self.connection_queue.append({
                'sid': sid,
                'timestamp': connect_time
            })
    
    def process_connection_queue(self):
        """Process queued connections in batches to prevent server overload"""
        if self.processing_connections:
            return
            
        self.processing_connections = True
        try:
            batch_size = 10  # Process connections in small batches
            processed = 0
            
            while self.connection_queue and processed < batch_size:
                with self._lock:
                    if not self.connection_queue:
                        break
                    connection = self.connection_queue.popleft()
                
                # For now, just log and count the connection
                # Actual processing happens in the main connection handler
                # This prevents queue from growing indefinitely during load spikes
                processed += 1
                
        finally:
            self.processing_connections = False
    
    def create_reconnection_token(self, team_name: str, player_slot: int) -> str:
        """Create a token for reconnection during the current server session"""
        import uuid
        token = str(uuid.uuid4())
        timestamp = time.time()
        
        # Clear any existing token for this team/slot
        self.clear_team_slot_token(team_name, player_slot)
        
        # Store the new token
        self.reconnection_tokens[token] = {
            'team_name': team_name,
            'player_slot': player_slot,
            'timestamp': timestamp
        }
        
        # Also store by team/slot for easier retrieval
        if team_name not in self.team_slot_tokens:
            self.team_slot_tokens[team_name] = {}
        self.team_slot_tokens[team_name][player_slot] = token
        
        return token
    
    def get_reconnection_token_for_team_slot(self, team_name: str, player_slot: int) -> Optional[str]:
        """Get the reconnection token for a specific team and player slot"""
        if team_name in self.team_slot_tokens:
            token = self.team_slot_tokens[team_name].get(player_slot)
            if token and token in self.reconnection_tokens:
                # Check if token is still valid
                token_data = self.reconnection_tokens[token]
                if time.time() - token_data['timestamp'] < 3600:
                    return token
                else:
                    # Token expired, clean it up
                    self.clear_team_slot_token(team_name, player_slot)
        return None
    
    def clear_team_slot_token(self, team_name: str, player_slot: int):
        """Clear the reconnection token for a specific team and player slot"""
        if team_name in self.team_slot_tokens and player_slot in self.team_slot_tokens[team_name]:
            old_token = self.team_slot_tokens[team_name][player_slot]
            if old_token in self.reconnection_tokens:
                del self.reconnection_tokens[old_token]
            del self.team_slot_tokens[team_name][player_slot]
            
            # Clean up empty team entries
            if not self.team_slot_tokens[team_name]:
                del self.team_slot_tokens[team_name]
    
    def validate_reconnection_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Validate and consume a reconnection token"""
        if token in self.reconnection_tokens:
            token_data = self.reconnection_tokens[token]
            # Tokens expire after 1 hour
            if time.time() - token_data['timestamp'] < 3600:
                return token_data
            else:
                # Clean up expired token
                team_name = token_data['team_name']
                player_slot = token_data['player_slot']
                self.clear_team_slot_token(team_name, player_slot)
        return None
    
    def cleanup_expired_tokens(self):
        """Clean up expired reconnection tokens"""
        current_time = time.time()
        expired_tokens = [
            token for token, data in self.reconnection_tokens.items()
            if current_time - data['timestamp'] > 3600
        ]
        for token in expired_tokens:
            token_data = self.reconnection_tokens[token]
            self.clear_team_slot_token(token_data['team_name'], token_data['player_slot'])


class AppState:
    def __init__(self):
        self.active_teams = {}  # {team_name: {'players': [], 'team_id': db_team_id, 'current_round_number': 0, 'combo_tracker': {}, 'current_db_round_id': None, 'answered_current_round': {}, 'player_slots': {sid: slot_number}}}
        self.player_to_team = {}  # {sid: team_name}
        self.connected_players = set()  # All connected player SIDs
        self.dashboard_clients = set() # Stores SIDs of connected dashboard clients
        self.game_started = False # Track if game has started
        self.game_paused = False # Track if game is paused
        self.answer_stream_enabled = False # Track if answer streaming is enabled
        self.game_mode = 'new'  # Track current game mode: 'classic' or 'new'
        # Store team ID to team name mapping for faster lookups
        self.team_id_to_name = {} # {team_id: team_name}
        # Track disconnected players for reconnection - maps team_name to disconnected player info
        self.disconnected_players = {}  # {team_name: {'player_session_id': old_sid, 'player_slot': 1|2, 'disconnect_time': timestamp}}
        
        # Connection management for load stability
        self.connection_manager = ConnectionManager()
        
        # Last state sync info for server restarts
        self.last_server_start = time.time()
        self.connection_count_peak = 0

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
        self.game_mode = 'new'  # Reset game mode to new
        self.connection_count_peak = 0
        # Keep connection manager and its tokens across resets
        self.connection_manager.cleanup_expired_tokens()

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
    
    def sync_with_database(self, preserve_sessions_during_startup=False):
        """Synchronize in-memory state with database state for reconnections
        
        Args:
            preserve_sessions_during_startup: If True, don't clear session IDs during server startup
                                            when connected_players is empty
        """
        try:
            from src.models.quiz_models import Teams
            from src.config import db
            import logging
            logger = logging.getLogger(__name__)
            
            # Get all active teams from database
            db_teams = Teams.query.filter_by(is_active=True).all()
            
            # Determine if we should clean up stale sessions
            # Don't clean up during server startup when no clients are connected yet
            should_cleanup_stale_sessions = not preserve_sessions_during_startup and len(self.connected_players) > 0
            
            # Update state to match database
            for db_team in db_teams:
                if db_team.team_name not in self.active_teams:
                    # Team exists in DB but not in memory - restore it
                    players = []
                    player_slots = {}
                    stale_sessions_found = False
                    
                    # Check session validity based on context
                    if should_cleanup_stale_sessions:
                        # Normal operation: only restore currently connected players
                        if db_team.player1_session_id and db_team.player1_session_id in self.connected_players:
                            players.append(db_team.player1_session_id)
                            player_slots[db_team.player1_session_id] = 1
                        elif db_team.player1_session_id:
                            stale_sessions_found = True
                            
                        if db_team.player2_session_id and db_team.player2_session_id in self.connected_players:
                            players.append(db_team.player2_session_id)
                            player_slots[db_team.player2_session_id] = 2
                        elif db_team.player2_session_id:
                            stale_sessions_found = True
                    else:
                        # Server startup: preserve all session IDs for potential reconnection
                        if db_team.player1_session_id:
                            # Don't add to players list since they're not connected yet
                            # but preserve the session ID in the database
                            pass
                        if db_team.player2_session_id:
                            # Same for player 2
                            pass
                        logger.info(f"Preserving team {db_team.team_name} session IDs during startup for reconnection")
                    
                    # Clean up stale session IDs from database if appropriate
                    if stale_sessions_found and should_cleanup_stale_sessions:
                        try:
                            db.session.begin_nested()
                            if db_team.player1_session_id and db_team.player1_session_id not in self.connected_players:
                                logger.info(f"Clearing stale player1 session ID {db_team.player1_session_id} from team {db_team.team_name}")
                                db_team.player1_session_id = None
                            if db_team.player2_session_id and db_team.player2_session_id not in self.connected_players:
                                logger.info(f"Clearing stale player2 session ID {db_team.player2_session_id} from team {db_team.team_name}")
                                db_team.player2_session_id = None
                            db.session.commit()
                        except Exception as cleanup_error:
                            logger.error(f"Error cleaning up stale session IDs: {str(cleanup_error)}")
                            try:
                                db.session.rollback()
                            except Exception as rollback_error:
                                logger.error(f"Failed to rollback after cleanup error: {str(rollback_error)}")
                    
                    # Only restore teams to active memory if they have connected players
                    if players:
                        # Determine current round number from database
                        from src.models.quiz_models import PairQuestionRounds
                        from sqlalchemy import func
                        max_round_obj = db.session.query(func.max(PairQuestionRounds.round_number_for_team)) \
                                            .filter_by(team_id=db_team.team_id).scalar()
                        last_played_round_number = max_round_obj if max_round_obj is not None else 0
                        
                        self.active_teams[db_team.team_name] = {
                            'players': players,
                            'team_id': db_team.team_id,
                            'current_round_number': last_played_round_number,
                            'combo_tracker': {},
                            'answered_current_round': {},
                            'status': 'active' if len(players) == 2 else 'waiting_pair',
                            'player_slots': player_slots
                        }
                        
                        self.team_id_to_name[db_team.team_id] = db_team.team_name
                        
                        for player_sid in players:
                            self.player_to_team[player_sid] = db_team.team_name
            
            # Track peak connections for monitoring
            current_count = len(self.connected_players)
            if current_count > self.connection_count_peak:
                self.connection_count_peak = current_count
                
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error syncing state with database: {str(e)}", exc_info=True)

# Create singleton instance for state
state = AppState()
