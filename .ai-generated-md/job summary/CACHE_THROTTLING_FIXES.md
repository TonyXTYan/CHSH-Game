# Cache and Throttling Logic Fixes

## Issue Summary

The original cache invalidation logic was **immediately deleting** cached data when invalidating caches, which defeated the purpose of throttling. This caused:

1. **Broken throttling behavior** - cache invalidation would delete cached data, forcing expensive recomputation even within throttling windows
2. **Performance degradation** - expensive database queries and calculations would run on every team event during rapid updates
3. **Inconsistent behavior** - throttling delays were ignored whenever cache invalidation occurred

## Root Cause

The user correctly identified that cache invalidation should **mark data as stale** instead of deleting it, so that:
- Within `REFRESH_DELAY_*` periods, return the cached (stale) data
- Only after the throttling window expires, actually recompute fresh data

## Solution: "Stale but Usable" Cache System

### 1. Enhanced SelectiveCache Class

**Added staleness tracking:**
```python
class SelectiveCache:
    def __init__(self, maxsize: int = CACHE_SIZE):
        self.maxsize = maxsize
        self._cache: Dict[str, Any] = {}
        self._access_order: List[str] = []  # LRU tracking
        self._stale_keys: Set[str] = set()  # NEW: Track which keys are stale
        self._lock = threading.RLock()
```

**Modified invalidation to mark as stale:**
```python
def invalidate_by_team(self, team_name: str) -> int:
    """
    Mark cache entries for a specific team as stale instead of deleting them.
    This allows throttling logic to still return stale data within REFRESH_DELAY.
    Returns number of entries marked as stale.
    """
    with self._lock:
        stale_count = 0
        for key in self._cache.keys():
            if self._is_team_key(key, team_name):
                self._stale_keys.add(key)  # Mark as stale, don't delete
                stale_count += 1
        return stale_count
```

**Enhanced get method with stale support:**
```python
def get(self, key: str, allow_stale: bool = True) -> Optional[Any]:
    """
    Get cached value for key, updating LRU order.
    
    Args:
        key: Cache key to retrieve
        allow_stale: If True, return stale data. If False, return None for stale data.
    """
    with self._lock:
        if key in self._cache:
            # Check if key is stale and if stale data is allowed
            if key in self._stale_keys and not allow_stale:
                return None
            
            # Move to end (most recently used)
            self._access_order.remove(key)
            self._access_order.append(key)
            return self._cache[key]
        return None
```

### 2. Global Cache Staleness Tracking

**Added staleness flags for global throttling caches:**
```python
# Global throttling state for get_all_teams function
_last_refresh_time = 0
_cached_teams_result: Optional[List[Dict[str, Any]]] = None
_cached_teams_is_stale = False  # NEW: Track if cached data is stale but still usable

# Global throttling state for dashboard update functions
_last_team_update_time = 0
_last_full_update_time = 0
_cached_team_metrics: Optional[Dict[str, int]] = None
_cached_full_metrics: Optional[Dict[str, int]] = None
_cached_team_metrics_is_stale = False  # NEW: Track staleness for team metrics
_cached_full_metrics_is_stale = False  # NEW: Track staleness for full metrics
```

### 3. Modified Cache Invalidation Logic

**Updated `invalidate_team_caches()` to mark as stale:**
```python
def invalidate_team_caches(team_name: str) -> None:
    """
    Selectively mark caches as stale for a specific team only.
    Preserves cached results for all other teams and allows throttling to return stale data.
    Uses "stale but usable" invalidation - marks data as outdated without deleting it.
    """
    global _cached_teams_result, _cached_team_metrics, _cached_full_metrics
    global _cached_teams_is_stale, _cached_team_metrics_is_stale, _cached_full_metrics_is_stale
    
    try:
        with _safe_dashboard_operation():
            # Mark team-specific caches as stale (not delete them)
            total_invalidated = 0
            total_invalidated += compute_team_hashes.cache_invalidate_team(team_name)
            # ... mark other caches as stale
            
            # Mark global throttling caches as stale if they contain this team's data
            if _cached_teams_result is not None:
                team_in_cache = any(team.get('team_name') == team_name for team in _cached_teams_result)
                if team_in_cache:
                    _cached_teams_is_stale = True  # Mark as stale instead of clearing
            
            # Similar logic for team metrics and full metrics caches
            # ...
```

### 4. Updated Throttling Logic

**Modified throttling functions to respect staleness:**

```python
def get_all_teams() -> List[Dict[str, Any]]:
    """
    Uses "stale but usable" cache logic - returns stale data within throttling window.
    """
    global _last_refresh_time, _cached_teams_result, _cached_teams_is_stale, _teams_computation_in_progress
    
    try:
        current_time = time()
        with _safe_dashboard_operation():
            time_since_last_refresh = current_time - _last_refresh_time
            
            # Return cached result (even if stale) if throttling applies
            if time_since_last_refresh < REFRESH_DELAY_QUICK and _cached_teams_result is not None:
                return _cached_teams_result  # Return stale data within throttling window
            
            # Mark computation starting
            _teams_computation_in_progress = True
        
        # ... expensive computation outside lock ...
        
        # Update cache with fresh data
        with _safe_dashboard_operation():
            _cached_teams_result = teams_list
            _cached_teams_is_stale = False  # Fresh data is not stale
            _last_refresh_time = time()
            _teams_computation_in_progress = False
```

**Similar updates for dashboard emit functions:**
```python
def emit_dashboard_team_update() -> None:
    """
    Uses "stale but usable" cache logic - returns stale data within throttling window.
    """
    # ...
    with _safe_dashboard_operation():
        time_since_last_update = current_time - _last_team_update_time
        
        # Check if we can use cached data (even if stale, as long as within throttling window)
        use_cached_data = (time_since_last_update < REFRESH_DELAY_QUICK and 
                         _cached_team_metrics is not None)
    # ...
    
    # When updating cache with fresh data:
    with _safe_dashboard_operation():
        _cached_team_metrics = { /* fresh data */ }
        _cached_team_metrics_is_stale = False  # Fresh data is not stale
        _last_team_update_time = time()
```

## Key Benefits

### 1. **Proper Throttling Behavior**
- Cache invalidation no longer breaks throttling
- Stale data is returned within throttling windows
- Fresh computation only happens after throttling delay expires

### 2. **Performance Improvement**
- Expensive database queries and calculations are properly throttled
- Rapid team events don't cause excessive computation
- Better server scalability under high update frequency

### 3. **Consistent User Experience**
- Dashboard updates respect intended throttling delays (1.0s for quick updates, 3.0s for full updates)
- No more real-time updates that can overwhelm the system
- Smooth performance during rapid player actions

### 4. **Backwards Compatibility**
- All existing cache clearing functions still work
- `force_clear_all_caches()` still provides complete cache reset when needed
- Selective invalidation preserves performance for unrelated teams

## Implementation Summary

The fix implements a **two-tier cache system**:

1. **Tier 1: Staleness Marking** - Cache invalidation marks data as stale but preserves it
2. **Tier 2: Throttling Window** - Within `REFRESH_DELAY_*`, return stale cached data
3. **Tier 3: Fresh Computation** - After throttling window expires, compute fresh data and reset staleness

This ensures that:
- **Within throttling windows**: Return cached data (even if stale) for performance
- **After throttling windows**: Recompute fresh data and mark as non-stale
- **Cache invalidation**: Marks data as outdated without breaking throttling

The system now works exactly as originally designed - cache invalidation doesn't defeat throttling, and expensive operations are properly rate-limited while still providing responsive user experience through stale-but-recent data.