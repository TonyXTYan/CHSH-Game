"""
Dashboard Cache System

This module contains the sophisticated selective cache invalidation system
that allows efficient caching of team computations while supporting
targeted invalidation by team name.
"""

import threading
import re
from typing import Dict, List, Any, Optional
import logging

logger = logging.getLogger(__name__)

# Cache configuration constants
CACHE_SIZE = 1024  # LRU cache size for team calculations
MIN_STD_DEV = 1e-10  # Minimum standard deviation to avoid zero uncertainty warnings

# Single lock for all dashboard operations to prevent deadlocks
_dashboard_lock = threading.RLock()

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