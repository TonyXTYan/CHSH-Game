"""
Socket event handlers for dashboard functionality.

This module handles all dashboard-related socket events including
client connections, game controls, and real-time updates.
"""

import logging
import threading
from time import time
from typing import Dict, Any, Optional
from contextlib import contextmanager
from flask import request
from flask_socketio import emit

from src.config import socketio
from src.state import state
from .dashboard_cache import force_clear_all_caches

# Configure logging
logger = logging.getLogger(__name__)

# Dashboard client activity tracking for keep-alive functionality
dashboard_last_activity: Dict[str, float] = {}

# Per-client preference for teams data streaming (enabled/disabled)
dashboard_teams_streaming: Dict[str, bool] = {}

# Throttling constants
REFRESH_DELAY_QUICK = 1.0  # seconds - maximum refresh rate for team updates and data fetching
REFRESH_DELAY_FULL = 3.0  # seconds - maximum refresh rate for expensive full dashboard updates

# Single lock for all dashboard operations to prevent deadlocks
_dashboard_lock = threading.RLock()

@contextmanager
def _safe_dashboard_operation():
    """
    Context manager for safe dashboard operations with proper error handling.
    Ensures lock is always released even if exceptions occur.
    """
    _dashboard_lock.acquire()
    try:
        yield
    except Exception as e:
        logger.error(f"Error in dashboard operation: {str(e)}", exc_info=True)
        raise
    finally:
        _dashboard_lock.release()

def _atomic_client_update(sid: str, activity_time: Optional[float] = None, 
                         streaming_enabled: Optional[bool] = None, 
                         remove: bool = False) -> None:
    """
    Atomically update dashboard client tracking data.
    Ensures both dictionaries are updated together to prevent inconsistencies.
    
    Args:
        sid: Client session ID
        activity_time: Time to set for last activity (if not None)
        streaming_enabled: Streaming preference to set (if not None)
        remove: If True, remove client from tracking dictionaries
    """
    with _safe_dashboard_operation():
        if remove:
            dashboard_last_activity.pop(sid, None)
            dashboard_teams_streaming.pop(sid, None)
            logger.debug(f"Atomically removed dashboard client data for {sid}")
        else:
            if activity_time is not None:
                dashboard_last_activity[sid] = activity_time
            if streaming_enabled is not None:
                dashboard_teams_streaming[sid] = streaming_enabled
            logger.debug(f"Atomically updated dashboard client data for {sid}")

def reset_client_tracking() -> None:
    """Reset all client tracking data. Used by cache clearing operations."""
    global dashboard_last_activity, dashboard_teams_streaming
    with _safe_dashboard_operation():
        dashboard_last_activity.clear()
        dashboard_teams_streaming.clear()

@socketio.on('keep_alive')
def on_keep_alive() -> None:
    """Handle dashboard client keep-alive ping to maintain connection tracking."""
    try:
        sid = request.sid  # type: ignore
        if sid in state.dashboard_clients:
            _atomic_client_update(sid, activity_time=time())
            emit('keep_alive_ack', to=sid)  # type: ignore
    except Exception as e:
        logger.error(f"Error in on_keep_alive: {str(e)}", exc_info=True)

@socketio.on('set_teams_streaming')
def on_set_teams_streaming(data: Dict[str, Any]) -> None:
    """Handle dashboard client preference for teams data streaming on/off."""
    try:
        sid = request.sid  # type: ignore
        if sid in state.dashboard_clients:
            enabled = data.get('enabled', False)
            _atomic_client_update(sid, streaming_enabled=enabled)
            logger.info(f"Dashboard client {sid} set teams streaming to: {enabled}")
    except Exception as e:
        logger.error(f"Error in on_set_teams_streaming: {str(e)}", exc_info=True)

@socketio.on('request_teams_update')
def on_request_teams_update() -> None:
    """Handle explicit request for teams data from streaming-enabled clients."""
    try:
        sid = request.sid  # type: ignore
        if sid in state.dashboard_clients and dashboard_teams_streaming.get(sid, False):
            # Send current teams data to this specific client
            from .dashboard_utils import emit_dashboard_full_update
            emit_dashboard_full_update(client_sid=sid)
            logger.info(f"Sent teams update to dashboard client {sid}")
    except Exception as e:
        logger.error(f"Error in on_request_teams_update: {str(e)}", exc_info=True)

@socketio.on('toggle_game_mode')
def on_toggle_game_mode() -> None:
    """Toggle between 'classic' and 'new' game modes with cache invalidation."""
    try:
        sid = request.sid  # type: ignore
        if sid not in state.dashboard_clients:
            emit('error', {'message': 'Unauthorized: Not a dashboard client'})  # type: ignore
            return

        # Toggle the mode
        new_mode = 'new' if state.game_mode == 'classic' else 'classic'
        state.game_mode = new_mode
        logger.info(f"Game mode toggled to: {new_mode}")
        
        # Clear caches to recalculate with new mode - use force clear since mode affects all calculations
        force_clear_all_caches()
        
        # Notify all clients (players and dashboards) about the mode change
        socketio.emit('game_mode_changed', {'mode': new_mode})
        
        # Trigger dashboard update to recalculate metrics immediately
        from .dashboard_utils import emit_dashboard_full_update
        emit_dashboard_full_update()
        
    except Exception as e:
        logger.error(f"Error in on_toggle_game_mode: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while toggling game mode'})  # type: ignore

@socketio.on('dashboard_join')
def on_dashboard_join(data: Optional[Dict[str, Any]] = None, callback: Optional[Any] = None) -> None:
    """Handle dashboard client joining and provide initial data."""
    try:
        from .dashboard_utils import get_all_teams
        from src.models.quiz_models import Answers
        
        sid = request.sid  # type: ignore
        
        # Add this client to dashboard_clients set
        state.dashboard_clients.add(sid)
        
        # Initialize client preferences (streaming disabled by default)
        _atomic_client_update(sid, streaming_enabled=False)
        
        logger.info(f"Dashboard client joined: {sid}")
        
        # Get initial dashboard data
        teams_data = get_all_teams()
        total_answers = Answers.query.count()
        
        dashboard_data = {
            'teams': teams_data,
            'connected_players_count': len(state.connected_players),
            'active_teams_count': len([t for t in teams_data if t.get('is_active', False) and len(t.get('members', [])) == 2]),
            'ready_players_count': sum(2 for t in teams_data if t.get('is_active', False) and len(t.get('members', [])) == 2),
            'total_answers': total_answers,
            'game_started': state.game_started,
            'game_paused': state.game_paused,
            'game_mode': state.game_mode,
            'answer_stream_enabled': state.answer_stream_enabled
        }
        
        # If callback is provided, send data via callback (for initial join)
        if callback:
            callback(dashboard_data)
        else:
            # Otherwise emit to the specific client
            emit('dashboard_data', dashboard_data, to=sid)  # type: ignore
        
        # Send dashboard update to OTHER dashboard clients (excluding the one that just joined)
        from .dashboard_utils import emit_dashboard_full_update
        emit_dashboard_full_update(exclude_sid=sid)
        
    except Exception as e:
        logger.error(f"Error in on_dashboard_join: {str(e)}", exc_info=True)
        if callback:
            callback({'error': 'An error occurred while joining dashboard'})
        else:
            emit('error', {'message': 'An error occurred while joining dashboard'})  # type: ignore

@socketio.on('start_game')
def on_start_game(data: Optional[Dict[str, Any]] = None) -> None:
    """Handle game start request from dashboard."""
    try:
        sid = request.sid  # type: ignore
        if sid not in state.dashboard_clients:
            emit('error', {'message': 'Unauthorized: Not a dashboard client'})  # type: ignore
            return

        from src.game_logic import start_new_round_for_pair
        
        state.game_started = True
        logger.info("Game started by dashboard")
        
        # Start rounds for all active teams with 2 players
        for team_name, team_info in state.active_teams.items():
            if len(team_info['players']) == 2:
                start_new_round_for_pair(team_name)
        
        # Notify all clients about game start
        socketio.emit('game_started', {'started': True})
        
    except Exception as e:
        logger.error(f"Error in on_start_game: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while starting the game'})  # type: ignore

@socketio.on('pause_game')
def on_pause_game() -> None:
    """Toggle game pause state."""
    try:
        sid = request.sid  # type: ignore
        if sid not in state.dashboard_clients:
            emit('error', {'message': 'Unauthorized: Not a dashboard client'})  # type: ignore
            return

        # Toggle pause state
        state.game_paused = not state.game_paused
        logger.info(f"Game {'paused' if state.game_paused else 'unpaused'} by dashboard")
        
        # Notify all active teams about the pause state change
        for team_name in state.active_teams.keys():
            socketio.emit('game_state_update', {'paused': state.game_paused}, to=team_name)
        
    except Exception as e:
        logger.error(f"Error in on_pause_game: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while pausing the game'})  # type: ignore

@socketio.on('restart_game')
def on_restart_game() -> None:
    """Handle game restart request from dashboard."""
    try:
        from src.config import db
        from src.models.quiz_models import Teams, PairQuestionRounds, Answers
        from .dashboard_cache import clear_team_caches
        
        sid = request.sid  # type: ignore
        if sid not in state.dashboard_clients:
            emit('error', {'message': 'Unauthorized: Not a dashboard client'})  # type: ignore
            return

        # Reset game state
        state.game_started = False
        state.game_paused = False
        
        # Deactivate all teams and clear their state
        for team_name, team_info in list(state.active_teams.items()):
            team_id = team_info['team_id']
            
            # Update database
            team = db.session.get(Teams, team_id)
            if team:
                team.is_active = False
                team.player1_session_id = None
                team.player2_session_id = None
        
        # Clear all answers and rounds from database
        db.session.query(Answers).delete()
        db.session.query(PairQuestionRounds).delete()
        db.session.commit()
        
        # Clear all state
        state.active_teams.clear()
        state.player_to_team.clear()
        state.team_id_to_name.clear()
        state.disconnected_players.clear()
        
        # Clear caches
        clear_team_caches()
        
        logger.info("Game restarted by dashboard")
        
        # Notify all clients about restart
        socketio.emit('game_restarted', {
            'restarted': True,
            'game_started': False,
            'game_paused': False
        })
        
    except Exception as e:
        logger.error(f"Error in on_restart_game: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while restarting the game'})  # type: ignore

def handle_dashboard_disconnect(sid: str) -> None:
    """Handle dashboard client disconnection and cleanup."""
    try:
        if sid in state.dashboard_clients:
            state.dashboard_clients.discard(sid)
            _atomic_client_update(sid, remove=True)
            logger.info(f"Dashboard client disconnected and cleaned up: {sid}")
    except Exception as e:
        logger.error(f"Error in handle_dashboard_disconnect: {str(e)}", exc_info=True)

# Export functions that are used by other modules
__all__ = [
    'on_keep_alive',
    'on_set_teams_streaming', 
    'on_request_teams_update',
    'on_toggle_game_mode',
    'on_dashboard_join',
    'on_start_game',
    'on_pause_game',
    'on_restart_game',
    'handle_dashboard_disconnect',
    'reset_client_tracking',
    'dashboard_teams_streaming'
]