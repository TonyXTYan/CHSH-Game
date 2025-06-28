from flask import jsonify, Response
import math
from uncertainties import ufloat, UFloat
import uncertainties.umath as um  # for ufloat‑compatible fabs
from functools import lru_cache
from sqlalchemy.orm import joinedload
from src.config import app, socketio, db
from src.state import state
from src.models.quiz_models import Teams, Answers, PairQuestionRounds, ItemEnum
from src.game_logic import QUESTION_ITEMS, TARGET_COMBO_REPEATS
from flask_socketio import emit
from src.game_logic import start_new_round_for_pair
from time import time
import hashlib
import csv
import io
import logging
import threading
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional, Union, Set
from flask import request
from contextlib import contextmanager
import weakref

# Configure logging
logger = logging.getLogger(__name__)

# Dashboard client activity tracking for keep-alive functionality
dashboard_last_activity: Dict[str, float] = {}

# Per-client preference for teams data streaming (enabled/disabled)
dashboard_teams_streaming: Dict[str, bool] = {}

# Cache configuration and throttling constants
CACHE_SIZE = 1024  # LRU cache size for team calculations
REFRESH_DELAY_QUICK = 1.0  # seconds - maximum refresh rate for team updates and data fetching
REFRESH_DELAY_FULL = 3.0  # seconds - maximum refresh rate for expensive full dashboard updates
MIN_STD_DEV = 1e-10  # Minimum standard deviation to avoid zero uncertainty warnings

# Single lock for all dashboard operations to prevent deadlocks
# This lock protects:
# - Cache operations (LRU cache clearing, throttling state)
# - Dashboard client tracking (activity and streaming preferences)
# - All shared state modifications
_dashboard_lock = threading.RLock()

# Global throttling state for get_all_teams function
_last_refresh_time = 0
_cached_teams_result: Optional[List[Dict[str, Any]]] = None

# Global throttling state for dashboard update functions with differentiated timing
_last_team_update_time = 0
_last_full_update_time = 0
_cached_team_metrics: Optional[Dict[str, int]] = None
_cached_full_metrics: Optional[Dict[str, int]] = None

# --- SELECTIVE CACHE INVALIDATION SYSTEM ---

class SelectiveCache:
    """
    Custom cache that supports selective invalidation by team name.
    Preserves cached results for unchanged teams while allowing targeted invalidation.
    """
    def __init__(self, maxsize: int = CACHE_SIZE):
        self.maxsize = maxsize
        self._cache: Dict[str, Any] = {}
        self._access_order: List[str] = []  # LRU tracking
        self._lock = threading.RLock()
    
    def get(self, key: str) -> Optional[Any]:
        """Get cached value for key, updating LRU order."""
        with self._lock:
            if key in self._cache:
                # Move to end (most recently used)
                self._access_order.remove(key)
                self._access_order.append(key)
                return self._cache[key]
            return None
    
    def set(self, key: str, value: Any) -> None:
        """Set cached value for key, evicting LRU items if needed."""
        with self._lock:
            if key in self._cache:
                # Update existing, move to end
                self._access_order.remove(key)
            elif len(self._cache) >= self.maxsize:
                # Evict least recently used
                lru_key = self._access_order.pop(0)
                del self._cache[lru_key]
            
            self._cache[key] = value
            self._access_order.append(key)
    
    def invalidate_by_team(self, team_name: str) -> int:
        """
        Invalidate all cache entries for a specific team.
        Returns number of entries invalidated.
        """
        with self._lock:
            invalidated_count = 0
            keys_to_remove = []
            
            for key in self._cache.keys():
                # Check if this cache key is for the specified team
                if self._is_team_key(key, team_name):
                    keys_to_remove.append(key)
            
            for key in keys_to_remove:
                del self._cache[key]
                self._access_order.remove(key)
                invalidated_count += 1
            
            return invalidated_count
    
    def clear_all(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._access_order.clear()
    
    def _is_team_key(self, cache_key: str, team_name: str) -> bool:
        """
        Check if a cache key belongs to a specific team.
        Uses precise matching to avoid false positives from substring matches.
        """
        # For simple team_name keys (exact match)
        if cache_key == team_name:
            return True
        
        # For function cache keys in format: (arg1, arg2, ...)
        # team_name appears as repr(team_name) which is 'team_name'
        team_name_repr = repr(team_name)
        
        # Check if this is a function cache key starting with (team_name, ...)
        if cache_key.startswith(f"({team_name_repr},") or cache_key == f"({team_name_repr})":
            return True
        
        # Check for team_name as any parameter in the function call
        # Use regex to match team_name_repr as a complete parameter
        import re
        # Pattern matches 'team_name' that is:
        # - after opening paren: ('team_name'
        # - after comma and optional space: , 'team_name' or ,  'team_name'
        # - and followed by comma, closing paren, or end: 'team_name', or 'team_name')
        pattern = rf"(\(|,\s*){re.escape(team_name_repr)}(\s*,|\s*\)|$)"
        return bool(re.search(pattern, cache_key))

# Global selective caches
_hash_cache = SelectiveCache()
_correlation_cache = SelectiveCache()
_success_cache = SelectiveCache()
_classic_stats_cache = SelectiveCache()
_new_stats_cache = SelectiveCache()
_team_process_cache = SelectiveCache()


def _make_cache_key(*args, **kwargs) -> str:
    """Create a consistent cache key from function arguments."""
    key_parts = []
    for arg in args:
        key_parts.append(repr(arg))
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}={repr(v)}")
    return f"({', '.join(key_parts)})"

def selective_cache(cache_instance: SelectiveCache):
    """
    Decorator for selective caching that supports team-specific invalidation.
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            cache_key = _make_cache_key(*args, **kwargs)
            
            # Try to get from cache
            cached_result = cache_instance.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Compute and cache result
            result = func(*args, **kwargs)
            cache_instance.set(cache_key, result)
            return result
        
        # Add cache management methods to function
        wrapper.cache_clear = cache_instance.clear_all
        wrapper.cache_invalidate_team = cache_instance.invalidate_by_team
        wrapper.cache_info = lambda: f"Cache entries: {len(cache_instance._cache)}"
        
        return wrapper
    return decorator

# --- END SELECTIVE CACHE SYSTEM ---

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

def _get_team_id_from_name(team_name: str) -> Optional[int]:
    """Helper function to resolve team_name to team_id from state or database."""
    try:
        # First check active teams
        team_info = state.active_teams.get(team_name)
        if team_info and 'team_id' in team_info:
            return team_info['team_id']
        
        # Fall back to database lookup
        team = Teams.query.filter_by(team_name=team_name).first()
        return team.team_id if team else None
    except Exception as e:
        logger.error(f"Error getting team_id for team_name {team_name}: {str(e)}", exc_info=True)
        return None

def _periodic_cleanup_dashboard_clients() -> None:
    """
    Periodic cleanup of stale dashboard client data.
    Removes tracking for clients not in active dashboard_clients set.
    Thread-safe with atomic operations to prevent inconsistencies.
    """
    try:
        with _safe_dashboard_operation():
            # Get current active dashboard clients
            active_clients = set(state.dashboard_clients)
            
            # Clean up tracking dictionaries atomically
            stale_activity_clients = set(dashboard_last_activity.keys()) - active_clients
            stale_streaming_clients = set(dashboard_teams_streaming.keys()) - active_clients
            
            # Remove stale clients atomically
            for sid in stale_activity_clients:
                del dashboard_last_activity[sid]
                
            for sid in stale_streaming_clients:
                del dashboard_teams_streaming[sid]
                
            if stale_activity_clients or stale_streaming_clients:
                logger.info(f"Cleaned up {len(stale_activity_clients)} stale activity clients "
                           f"and {len(stale_streaming_clients)} stale streaming clients")
    except Exception as e:
        logger.error(f"Error in periodic cleanup: {str(e)}", exc_info=True)

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
        emit_dashboard_full_update()
        
    except Exception as e:
        logger.error(f"Error in on_toggle_game_mode: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while toggling game mode'})  # type: ignore

# Import heavy calculation functions from helper module and re-export them
from .calculations import (
    compute_team_hashes,
    compute_success_metrics,
    compute_correlation_matrix,
    compute_correlation_stats,
    _calculate_team_statistics,
    _calculate_success_statistics,
    _compute_team_hashes_optimized,
    _compute_correlation_matrix_optimized,
    _compute_success_metrics_optimized,
    _calculate_team_statistics_from_data,
    _calculate_success_statistics_from_data,
    _process_single_team_optimized,
    _process_single_team,
)


def get_all_teams() -> List[Dict[str, Any]]:
    """
    Retrieve and serialize all team data with throttling for performance.
    Returns cached result if called within REFRESH_DELAY_QUICK seconds.
    Thread-safe with proper error handling and lock management.
    
    OPTIMIZATION: Uses bulk queries to prevent N+1 database query problem.
    """
    global _last_refresh_time, _cached_teams_result
    
    try:
        with _safe_dashboard_operation():
            # Check if we should throttle the request
            current_time = time()
            time_since_last_refresh = current_time - _last_refresh_time
            
            # Throttle all calls with REFRESH_DELAY_QUICK
            if time_since_last_refresh < REFRESH_DELAY_QUICK and _cached_teams_result is not None:
                # logger.debug("Returning cached team data")
                return _cached_teams_result
            
            # logger.debug("Computing fresh team data")
            
            # OPTIMIZATION: Bulk fetch all data to prevent N+1 queries
            # Fetch all teams
            all_teams = Teams.query.all()
            
            if not all_teams:
                _cached_teams_result = []
                _last_refresh_time = current_time
                return []
            
            # Extract team IDs for bulk queries
            team_ids = [team.team_id for team in all_teams]
            
            # Bulk fetch all rounds and answers for all teams
            all_rounds = PairQuestionRounds.query.filter(
                PairQuestionRounds.team_id.in_(team_ids)
            ).order_by(PairQuestionRounds.team_id, PairQuestionRounds.timestamp_initiated).all()
            
            all_answers = Answers.query.filter(
                Answers.team_id.in_(team_ids)
            ).order_by(Answers.team_id, Answers.timestamp).all()
            
            # Group data by team_id for efficient lookup
            rounds_by_team = {}
            answers_by_team = {}
            
            for round_obj in all_rounds:
                if round_obj.team_id not in rounds_by_team:
                    rounds_by_team[round_obj.team_id] = []
                rounds_by_team[round_obj.team_id].append(round_obj)
            
            for answer in all_answers:
                if answer.team_id not in answers_by_team:
                    answers_by_team[answer.team_id] = []
                answers_by_team[answer.team_id].append(answer)
            
            # Process teams using pre-fetched data
            teams_list = []
            
            for team in all_teams:
                # Get active team info from state if available
                team_info = state.active_teams.get(team.team_name)
                
                # Get players from either active state or database
                players = team_info['players'] if team_info else []
                current_round = team_info.get('current_round_number', 0) if team_info else 0
                
                # Get pre-fetched data for this team
                team_rounds = rounds_by_team.get(team.team_id, [])
                team_answers = answers_by_team.get(team.team_id, [])
                
                # Use optimized helper function with pre-fetched data
                team_data = _process_single_team_optimized(
                    team.team_id,
                    team.team_name,
                    team.is_active,
                    team.created_at.isoformat() if team.created_at else None,
                    current_round,
                    players[0] if len(players) > 0 else None,
                    players[1] if len(players) > 1 else None,
                    team_rounds,
                    team_answers
                )
                
                if team_data:
                    teams_list.append(team_data)
            
            # Update cache and timestamp
            _cached_teams_result = teams_list
            _last_refresh_time = current_time
            
            return teams_list
    except Exception as e:
        logger.error(f"Error in get_all_teams: {str(e)}", exc_info=True)
        return []

def invalidate_team_caches(team_name: str) -> None:
    """
    Selectively invalidate caches for a specific team only.
    Preserves cached results for all other teams.
    Thread-safe operation with proper error handling.
    """
    global _cached_teams_result, _cached_team_metrics, _cached_full_metrics
    
    try:
        with _safe_dashboard_operation():
            # Selectively invalidate team-specific caches
            total_invalidated = 0
            total_invalidated += compute_team_hashes.cache_invalidate_team(team_name)
            total_invalidated += compute_correlation_matrix.cache_invalidate_team(team_name)
            total_invalidated += compute_success_metrics.cache_invalidate_team(team_name)
            total_invalidated += _calculate_team_statistics.cache_invalidate_team(team_name)
            total_invalidated += _calculate_success_statistics.cache_invalidate_team(team_name)
            total_invalidated += _process_single_team.cache_invalidate_team(team_name)
            
            # Invalidate global throttling caches that may contain this team's data
            # but preserve caches that don't contain this team
            if _cached_teams_result is not None:
                # Check if this team is in the cached result
                team_in_cache = any(team.get('team_name') == team_name for team in _cached_teams_result)
                if team_in_cache:
                    _cached_teams_result = None
                    _last_refresh_time = 0
                    logger.debug(f"Cleared get_all_teams cache containing team {team_name}")
            
            # Clear throttling caches if they contained this team's data
            if _cached_team_metrics is not None and 'cached_teams' in _cached_team_metrics:
                cached_teams = _cached_team_metrics.get('cached_teams', [])
                if any(team.get('team_name') == team_name for team in cached_teams):
                    _cached_team_metrics = None
                    _last_team_update_time = 0
                    logger.debug(f"Cleared team metrics cache containing team {team_name}")
            
            if _cached_full_metrics is not None and 'cached_teams' in _cached_full_metrics:
                cached_teams = _cached_full_metrics.get('cached_teams', [])
                if any(team.get('team_name') == team_name for team in cached_teams):
                    _cached_full_metrics = None
                    _last_full_update_time = 0
                    logger.debug(f"Cleared full metrics cache containing team {team_name}")
            
            logger.debug(f"Selectively invalidated {total_invalidated} cache entries for team {team_name}")
            
    except Exception as e:
        logger.error(f"Error invalidating team caches for {team_name}: {str(e)}", exc_info=True)

def clear_team_caches() -> None:
    """
    Clear all team-related caches and throttling state to prevent stale data.
    Thread-safe operation with proper error handling to prevent lock issues.
    
    Note: This function now clears ALL caches. For selective invalidation of
    specific teams, use invalidate_team_caches(team_name) instead.
    """
    global _last_refresh_time, _cached_teams_result
    global _last_team_update_time, _last_full_update_time, _cached_team_metrics, _cached_full_metrics
    
    try:
        with _safe_dashboard_operation():
            # Clear all selective caches
            compute_team_hashes.cache_clear()
            compute_correlation_matrix.cache_clear()
            compute_success_metrics.cache_clear()
            _calculate_team_statistics.cache_clear()
            _calculate_success_statistics.cache_clear()
            _process_single_team.cache_clear()
            
            # Clear get_all_teams cache since it depends on caches we just cleared
            _last_refresh_time = 0
            _cached_teams_result = None
            
            # FIXED: Reset throttling timers when cached teams data is removed to prevent inconsistent state
            # When we remove cached teams data, we must also reset throttling to avoid serving
            # empty teams list with stale metrics in subsequent throttled calls
            if _cached_team_metrics is not None and 'cached_teams' in _cached_team_metrics:
                # Reset team update throttling to ensure consistency
                _last_team_update_time = 0
                _cached_team_metrics = None
                
            if _cached_full_metrics is not None and 'cached_teams' in _cached_full_metrics:
                # Reset full update throttling to ensure consistency
                _last_full_update_time = 0
                _cached_full_metrics = None
            
            logger.debug("Cleared all team caches and reset throttling state to ensure data consistency")
            
        # Perform periodic cleanup of dashboard client data
        # Note: This is outside the main lock to prevent potential deadlocks
        _periodic_cleanup_dashboard_clients()
        
    except Exception as e:
        logger.error(f"Error clearing team caches: {str(e)}", exc_info=True)

def force_clear_all_caches() -> None:
    """
    Force clear ALL caches including throttling state. Use only when data integrity requires it.
    This is more aggressive than clear_team_caches() and should be used sparingly.
    """
    global _last_refresh_time, _cached_teams_result
    global _last_team_update_time, _last_full_update_time, _cached_team_metrics, _cached_full_metrics
    
    try:
        with _safe_dashboard_operation():
            # Clear all selective caches
            compute_team_hashes.cache_clear()
            compute_correlation_matrix.cache_clear()
            compute_success_metrics.cache_clear()
            _calculate_team_statistics.cache_clear()
            _calculate_success_statistics.cache_clear()
            _process_single_team.cache_clear()
            
            # Force clear ALL throttling state
            _last_refresh_time = 0
            _cached_teams_result = None
            _last_team_update_time = 0
            _last_full_update_time = 0
            _cached_team_metrics = None
            _cached_full_metrics = None
            
            logger.info("Force cleared all caches and throttling state")
            
        _periodic_cleanup_dashboard_clients()
        
    except Exception as e:
        logger.error(f"Error in force_clear_all_caches: {str(e)}", exc_info=True)

def emit_dashboard_team_update() -> None:
    """
    Send team status updates to dashboard clients with throttled metrics calculation.
    Always sends fresh connected_players_count but throttles expensive metrics.
    Uses REFRESH_DELAY_QUICK for frequent team status updates.
    Thread-safe with proper error handling.
    """
    global _last_team_update_time, _cached_team_metrics
    
    try:
        # Always compute teams data and metrics for all dashboard clients
        if not state.dashboard_clients:
            return  # No dashboard clients at all
        
        # Always calculate connected_players_count fresh since it changes frequently
        connected_players_count = len(state.connected_players)
        
        with _safe_dashboard_operation():
            # Check if any clients need teams streaming
            streaming_clients = [sid for sid in state.dashboard_clients if dashboard_teams_streaming.get(sid, False)]
            non_streaming_clients = [sid for sid in state.dashboard_clients if not dashboard_teams_streaming.get(sid, False)]
            
            # Throttle team updates to prevent spam during mass connect/disconnect
            current_time = time()
            time_since_last_update = current_time - _last_team_update_time
            
            # Only compute expensive teams data if there are streaming clients
            if streaming_clients:
                if time_since_last_update < REFRESH_DELAY_QUICK and _cached_team_metrics is not None:
                    # Use cached data for both teams and metrics to avoid expensive calculations
                    serialized_teams = _cached_team_metrics.get('cached_teams', [])
                    active_teams_count = _cached_team_metrics.get('active_teams_count', 0)
                    ready_players_count = _cached_team_metrics.get('ready_players_count', 0)
                    logger.debug("Using cached team data and metrics for team update")
                else:
                    # Calculate fresh data including expensive team computation
                    serialized_teams = get_all_teams()
                    active_teams = [team for team in serialized_teams if team.get('is_active', False) or team.get('status') == 'waiting_pair']
                    active_teams_count = len(active_teams)
                    ready_players_count = sum(
                        (1 if team.get('player1_sid') else 0) + (1 if team.get('player2_sid') else 0)
                        for team in active_teams
                    )
                    
                    # Cache both the expensive teams data AND the calculated metrics
                    _cached_team_metrics = {
                        'cached_teams': serialized_teams,
                        'active_teams_count': active_teams_count,
                        'ready_players_count': ready_players_count,
                    }
                    _last_team_update_time = current_time
                    logger.debug("Computed fresh team data and metrics for team update")
            else:
                # No streaming clients - compute lightweight metrics only
                serialized_teams = []
                if time_since_last_update < REFRESH_DELAY_QUICK and _cached_team_metrics is not None:
                    active_teams_count = _cached_team_metrics.get('active_teams_count', 0)
                    ready_players_count = _cached_team_metrics.get('ready_players_count', 0)
                    logger.debug("Using cached metrics for non-streaming team update")
                else:
                    # Calculate lightweight metrics from state without expensive team processing
                    active_teams = [team_info for team_info in state.active_teams.values() 
                                  if team_info.get('status') in ['active', 'waiting_pair']]
                    active_teams_count = len(active_teams)
                    ready_players_count = sum(len(team_info.get('players', [])) for team_info in active_teams)
                    
                    # Cache just the lightweight metrics
                    _cached_team_metrics = {
                        'cached_teams': [],  # No teams data cached for non-streaming updates
                        'active_teams_count': active_teams_count,
                        'ready_players_count': ready_players_count,
                    }
                    _last_team_update_time = current_time
                    logger.debug("Computed lightweight metrics for non-streaming team update")
        
        # Send updates outside the lock to prevent blocking
        # Send full teams data to streaming clients
        if streaming_clients:
            streaming_update_data = {
                'teams': serialized_teams,
                'connected_players_count': connected_players_count,
                'active_teams_count': active_teams_count,
                'ready_players_count': ready_players_count
            }
            
            for sid in streaming_clients:
                socketio.emit('team_status_changed_for_dashboard', streaming_update_data, to=sid)  # type: ignore
        
        # Send metrics-only updates to non-streaming clients
        if non_streaming_clients:
            metrics_update_data = {
                'teams': [],  # Empty teams array for non-streaming clients
                'connected_players_count': connected_players_count,
                'active_teams_count': active_teams_count,
                'ready_players_count': ready_players_count
            }
            
            for sid in non_streaming_clients:
                socketio.emit('team_status_changed_for_dashboard', metrics_update_data, to=sid)  # type: ignore
                
    except Exception as e:
        logger.error(f"Error in emit_dashboard_team_update: {str(e)}", exc_info=True)

def emit_dashboard_full_update(client_sid: Optional[str] = None, exclude_sid: Optional[str] = None) -> None:
    """
    Send complete dashboard data to clients with throttled expensive operations.
    Supports targeting specific clients or excluding clients to prevent duplicates.
    Uses REFRESH_DELAY_FULL for expensive operations like database queries.
    Thread-safe with proper error handling.
    """
    global _last_full_update_time, _cached_full_metrics
    
    try:
        # Check if there are any dashboard clients to send updates to
        if not state.dashboard_clients:
            return  # No dashboard clients at all
        
        # Always calculate connected_players_count fresh since it changes frequently
        connected_players_count = len(state.connected_players)
        
        with _safe_dashboard_operation():
            # Determine which clients need teams data
            if client_sid:
                clients_needing_teams = [client_sid] if dashboard_teams_streaming.get(client_sid, False) else []
            else:
                clients_needing_teams = [sid for sid in state.dashboard_clients 
                                       if dashboard_teams_streaming.get(sid, False) and sid != exclude_sid]
            
            # Throttle full updates with longer delay due to expensive operations
            current_time = time()
            time_since_last_update = current_time - _last_full_update_time
            
            # Only compute expensive teams data if clients need it
            if clients_needing_teams:
                if time_since_last_update < REFRESH_DELAY_FULL and _cached_full_metrics is not None:
                    # Use cached data to avoid expensive operations
                    all_teams_for_metrics = _cached_full_metrics.get('cached_teams', [])
                    total_answers = _cached_full_metrics.get('total_answers', 0)
                    active_teams_count = _cached_full_metrics.get('active_teams_count', 0)
                    ready_players_count = _cached_full_metrics.get('ready_players_count', 0)
                    logger.debug("Using cached team data and full metrics for dashboard update")
                else:
                    # Calculate fresh data with expensive database query AND team computation
                    all_teams_for_metrics = get_all_teams()
                    
                    with app.app_context():
                        total_answers = Answers.query.count()

                    # Calculate metrics from the teams data we just fetched
                    # Count teams that are active or waiting for a pair as "active" for metrics
                    active_teams = [team for team in all_teams_for_metrics if team.get('is_active', False) or team.get('status') == 'waiting_pair']
                    active_teams_count = len(active_teams)
                    ready_players_count = sum(
                        (1 if team.get('player1_sid') else 0) + (1 if team.get('player2_sid') else 0)
                        for team in active_teams
                    )
                    
                    # Cache the expensive-to-calculate data including teams
                    _cached_full_metrics = {
                        'cached_teams': all_teams_for_metrics,
                        'total_answers': total_answers,
                        'active_teams_count': active_teams_count,
                        'ready_players_count': ready_players_count,
                    }
                    _last_full_update_time = current_time
                    logger.debug("Computed fresh team data and full metrics for dashboard update")
            else:
                # No clients need teams data - compute lightweight metrics only
                all_teams_for_metrics = []
                if time_since_last_update < REFRESH_DELAY_FULL and _cached_full_metrics is not None:
                    total_answers = _cached_full_metrics.get('total_answers', 0)
                    active_teams_count = _cached_full_metrics.get('active_teams_count', 0)
                    ready_players_count = _cached_full_metrics.get('ready_players_count', 0)
                    logger.debug("Using cached metrics for non-streaming dashboard update")
                else:
                    # Calculate lightweight metrics and database query only
                    with app.app_context():
                        total_answers = Answers.query.count()
                    
                    # Calculate lightweight metrics from state without expensive team processing
                    active_teams = [team_info for team_info in state.active_teams.values() 
                                  if team_info.get('status') in ['active', 'waiting_pair']]
                    active_teams_count = len(active_teams)
                    ready_players_count = sum(len(team_info.get('players', [])) for team_info in active_teams)
                    
                    # Cache just the lightweight metrics
                    _cached_full_metrics = {
                        'cached_teams': [],  # No teams data cached for non-streaming updates
                        'total_answers': total_answers,
                        'active_teams_count': active_teams_count,
                        'ready_players_count': ready_players_count,
                    }
                    _last_full_update_time = current_time
                    logger.debug("Computed lightweight metrics for non-streaming dashboard update")

        base_update_data = {
            'total_answers_count': total_answers,
            'connected_players_count': connected_players_count,
            'active_teams_count': active_teams_count,  # Always send metrics
            'ready_players_count': ready_players_count,  # Always send metrics
            'game_state': {
                'started': state.game_started,
                'paused': state.game_paused,
                'streaming_enabled': state.answer_stream_enabled,
                'mode': state.game_mode  # Include current game mode
            }
        }

        # Send updates outside the lock to prevent blocking
        if client_sid:
            # For specific client, include teams only if they have streaming enabled
            update_data = base_update_data.copy()
            if dashboard_teams_streaming.get(client_sid, False):
                update_data['teams'] = all_teams_for_metrics
            else:
                update_data['teams'] = []  # Send empty array if streaming disabled
            socketio.emit('dashboard_update', update_data, to=client_sid)  # type: ignore
        else:
            # For all clients, send appropriate data based on their preferences
            for dash_sid in state.dashboard_clients:
                # Skip excluded client to prevent duplicate updates
                if exclude_sid and dash_sid == exclude_sid:
                    continue
                    
                update_data = base_update_data.copy()
                if dashboard_teams_streaming.get(dash_sid, False):
                    update_data['teams'] = all_teams_for_metrics
                else:
                    update_data['teams'] = []  # Send empty array if streaming disabled
                socketio.emit('dashboard_update', update_data, to=dash_sid)  # type: ignore
    except Exception as e:
        logger.error(f"Error in emit_dashboard_full_update: {str(e)}", exc_info=True)

@socketio.on('dashboard_join')
def on_dashboard_join(data: Optional[Dict[str, Any]] = None, callback: Optional[Any] = None) -> None:
    try:
        sid = request.sid  # type: ignore
        
        # Add to dashboard clients with teams streaming disabled by default (only for new clients)
        state.dashboard_clients.add(sid)
        dashboard_last_activity[sid] = time()
        if sid not in dashboard_teams_streaming:
            dashboard_teams_streaming[sid] = False  # Teams streaming off by default only for new clients
        logger.info(f"Dashboard client connected: {sid}")
        
        # Notify OTHER dashboard clients about the new connection (exclude the joining client to prevent duplicates)
        emit_dashboard_full_update(exclude_sid=sid)
        
        # Prepare update data for this specific client, respecting their streaming preference
        with app.app_context():
            total_answers = Answers.query.count()
            
        # Only get expensive teams data if this client has streaming enabled
        if dashboard_teams_streaming.get(sid, False):
            all_teams_for_metrics = get_all_teams()
            # Calculate metrics from the teams data we just fetched
            active_teams = [team for team in all_teams_for_metrics if team.get('is_active', False) or team.get('status') == 'waiting_pair']
            active_teams_count = len(active_teams)
            ready_players_count = sum(
                (1 if team.get('player1_sid') else 0) + (1 if team.get('player2_sid') else 0)
                for team in active_teams
            )
        else:
            # Calculate lightweight metrics from state without expensive team processing
            all_teams_for_metrics = []
            active_teams = [team_info for team_info in state.active_teams.values() 
                          if team_info.get('status') in ['active', 'waiting_pair']]
            active_teams_count = len(active_teams)
            ready_players_count = sum(len(team_info.get('players', [])) for team_info in active_teams)
        
        update_data = {
            'teams': all_teams_for_metrics if dashboard_teams_streaming.get(sid, False) else [],  # Respect client's streaming preference
            'total_answers_count': total_answers,
            'connected_players_count': len(state.connected_players),
            'active_teams_count': active_teams_count,  # Always send metrics
            'ready_players_count': ready_players_count,  # Always send metrics
            'game_state': {
                'started': state.game_started,
                'streaming_enabled': state.answer_stream_enabled,
                'mode': state.game_mode  # Include current game mode
            }
        }
        
        # If callback provided, use it to return data directly
        if callback:
            callback(update_data)
        else:
            # Send update to the joining client only once
            socketio.emit('dashboard_update', update_data, to=sid)  # type: ignore
    except Exception as e:
        logger.error(f"Error in on_dashboard_join: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while joining the dashboard'})  # type: ignore

@socketio.on('start_game')
def on_start_game(data: Optional[Dict[str, Any]] = None) -> None:
    try:
        if request.sid in state.dashboard_clients:  # type: ignore
            state.game_started = True
            # Notify teams and dashboard that game has started
            for team_name, team_info in state.active_teams.items():
                if len(team_info['players']) == 2:  # Only notify paired teams
                    socketio.emit('game_start', {'game_started': True}, to=team_name)  # type: ignore
            
            # Notify dashboard
            for dashboard_sid in state.dashboard_clients:
                socketio.emit('game_started', to=dashboard_sid)  # type: ignore
                
            # Notify all clients about game state change
            socketio.emit('game_state_changed', {'game_started': True})  # type: ignore
                
            # Start first round for all paired teams
            for team_name, team_info in state.active_teams.items():
                if len(team_info['players']) == 2: # If team is paired
                    start_new_round_for_pair(team_name)
    except Exception as e:
        logger.error(f"Error in on_start_game: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while starting the game'})  # type: ignore

@socketio.on('pause_game')
def on_pause_game() -> None:
    try:
        if request.sid not in state.dashboard_clients:  # type: ignore
            emit('error', {'message': 'Unauthorized: Not a dashboard client'})  # type: ignore
            return

        state.game_paused = not state.game_paused  # Toggle pause state
        pause_status = "paused" if state.game_paused else "resumed"
        logger.info(f"Game {pause_status} by {request.sid}")  # type: ignore

        # Notify all clients about pause state change
        for team_name in state.active_teams.keys():
            socketio.emit('game_state_update', {
                'paused': state.game_paused
            }, to=team_name)  # type: ignore

        # Update dashboard state
        emit_dashboard_full_update()

    except Exception as e:
        logger.error(f"Error in on_pause_game: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while toggling game pause'})  # type: ignore

def handle_dashboard_disconnect(sid: str) -> None:
    """Handle disconnect logic for dashboard clients with proper cleanup and error handling"""
    try:
        if sid in state.dashboard_clients:
            state.dashboard_clients.remove(sid)
            
        # Clean up all dashboard client tracking data atomically
        _atomic_client_update(sid, remove=True)
        
    except Exception as e:
        logger.error(f"Error in handle_dashboard_disconnect: {str(e)}", exc_info=True)

@socketio.on('restart_game')
def on_restart_game() -> None:
    try:
        logger.info(f"Received restart_game from {request.sid}")  # type: ignore
        if request.sid not in state.dashboard_clients:  # type: ignore
            emit('error', {'message': 'Unauthorized: Not a dashboard client'})  # type: ignore
            emit('game_reset_complete', to=request.sid)  # type: ignore
            return

        # First update game state to prevent new answers during reset
        state.game_started = False
        # logger.debug("Set game_started=False")
        
        # Even if there are no active teams, clear the database
        try:
            # Clear database entries within a transaction
            db.session.begin_nested()  # Create savepoint
            PairQuestionRounds.query.delete()
            Answers.query.delete()
            db.session.commit()
            # Force clear all caches after successful database commit since this is a complete reset
            force_clear_all_caches()
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database error during game reset: {str(db_error)}", exc_info=True)
            emit('error', {'message': 'Database error during reset'})  # type: ignore
            emit('game_reset_complete', to=request.sid)  # type: ignore
            return

        # If no active teams, still complete the reset successfully
        if not state.active_teams:
            socketio.emit('game_state_changed', {'game_started': False})  # type: ignore
            emit_dashboard_full_update()
            emit('game_reset_complete', to=request.sid)  # type: ignore
            return
        
        # Reset team state after successful database clear
        for team_name, team_info in state.active_teams.items():
            if team_info:  # Validate team info exists
                team_info['current_round_number'] = 0
                team_info['current_db_round_id'] = None
                team_info['answered_current_round'] = {}
                team_info['combo_tracker'] = {}
        
        # Notify all teams about the reset
        for team_name in state.active_teams.keys():
            socketio.emit('game_reset', to=team_name)  # type: ignore
        
        # Ensure all clients are notified of the state change
        socketio.emit('game_state_changed', {'game_started': False})  # type: ignore
        
        # Update dashboard with reset state
        emit_dashboard_full_update()

        # Notify dashboard clients that reset is complete
        logger.info("Emitting game_reset_complete to all dashboard clients")
        for dash_sid in state.dashboard_clients:
            socketio.emit('game_reset_complete', to=dash_sid)  # type: ignore
            
    except Exception as e:
        logger.error(f"Error in on_restart_game: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while restarting the game'})  # type: ignore

@app.route('/api/dashboard/data', methods=['GET'])
def get_dashboard_data():
    try:
        # Get all answers ordered by timestamp
        with app.app_context():
            all_answers = Answers.query.order_by(Answers.timestamp.asc()).all()
        
        answers_data = []
        for ans in all_answers:
            # Get team name for each answer
            team = Teams.query.get(ans.team_id)
            team_name = team.team_name if team else "Unknown Team"
            
            answers_data.append({
                'answer_id': ans.answer_id,
                'team_id': ans.team_id,
                'team_name': team_name,
                'player_session_id': ans.player_session_id,
                'question_round_id': ans.question_round_id,
                'assigned_item': ans.assigned_item.value,
                'response_value': ans.response_value,
                'timestamp': ans.timestamp.isoformat()
            })
        
        return jsonify({'answers': answers_data}), 200
    except Exception as e:
        logger.error(f"Error in get_dashboard_data: {str(e)}", exc_info=True)
        return jsonify({'error': 'An error occurred while retrieving dashboard data'}), 500

@app.route('/download', methods=['GET'])
def download_csv():
    try:
        # Get all answers ordered by timestamp
        with app.app_context():
            all_answers = Answers.query.order_by(Answers.timestamp.asc()).all()
        
        # Create CSV content in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write CSV header
        writer.writerow(['Timestamp', 'Team Name', 'Team ID', 'Player ID', 'Round ID', 'Question Item (A/B/X/Y)', 'Answer (True/False)'])
        
        # Write data rows
        for ans in all_answers:
            # Get team name for each answer
            team = Teams.query.get(ans.team_id)
            team_name = team.team_name if team else "Unknown Team"
            
            writer.writerow([
                ans.timestamp.strftime('%m/%d/%Y, %I:%M:%S %p'),  # Format timestamp like JavaScript toLocaleString()
                team_name,
                ans.team_id,
                ans.player_session_id,
                ans.question_round_id,
                ans.assigned_item.value,
                ans.response_value
            ])
        
        # Get the CSV content
        csv_content = output.getvalue()
        output.close()
        
        # Create response with appropriate headers for CSV download
        response = Response(
            csv_content,
            mimetype='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename=chsh-game-data.csv'
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error in download_csv: {str(e)}", exc_info=True)
        return Response(
            "An error occurred while generating the CSV file",
            status=500,
            mimetype='text/plain'
        )

# Disconnect handler is now consolidated in team_management.py
# The handle_dashboard_disconnect function is called from there
