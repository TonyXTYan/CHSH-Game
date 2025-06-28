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

