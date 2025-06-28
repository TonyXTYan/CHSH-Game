# Cache and Throttling Logic Improvements

## Overview

Fixed the cache invalidation and throttling system in `src/sockets/dashboard.py` to properly handle cache invalidation without deleting cached data. The improvements ensure that:

1. **Cache invalidation marks data as outdated** rather than deleting it
2. **Within refresh delay periods**, cached data is returned regardless of validity (prevents expensive recomputation during rapid invalidations)
3. **After refresh delay periods**, the system still performs periodic refreshes to maintain data freshness
4. **Maintains compatibility** with existing code that calls `invalidate_team_caches()` and `emit_dashboard_*()` functions

## Key Changes Made

### 1. Enhanced SelectiveCache Class

**Before**: Cache invalidation deleted cached data
```python
def invalidate_by_team(self, team_name: str) -> int:
    # ... code that deleted cache entries ...
    for key in keys_to_remove:
        del self._cache[key]  # Actually deleted data
```

**After**: Cache invalidation marks data as invalid but preserves it
```python
def invalidate_by_team(self, team_name: str) -> int:
    # Mark as invalid, don't delete data
    for key in self._cache.keys():
        if self._is_team_key(key, team_name):
            self._validity[key] = False  # Mark invalid, keep data
```

**New Features**:
- Added `_validity` dictionary to track cache entry validity
- Added `is_valid(key)` method to check if cached data is valid
- Cache entries are marked as valid when set, invalid when invalidated
- LRU eviction and `clear_all()` still actually remove data

### 2. Global Cache Validity Flags

Added validity flags for throttled cache systems:
```python
_cached_teams_valid = True          # For get_all_teams()
_cached_team_metrics_valid = True   # For emit_dashboard_team_update()  
_cached_full_metrics_valid = True   # For emit_dashboard_full_update()
```

### 3. Improved Throttling Logic

**The Problem**: Original cache invalidation caused expensive recomputation during rapid team changes, but we still needed periodic refreshes.

**The Solution**: Two-tier throttling logic:

#### Within Refresh Delay Period
```python
# Always return cached data regardless of validity
if time_since_last_refresh < REFRESH_DELAY_X and cached_data is not None:
    return cached_data  # Fast path - prevents expensive recomputation from invalidations
```

#### Outside Refresh Delay Period  
```python
# Always recompute for periodic refresh (preserves original timing behavior)
# This ensures data freshness even when cache is still marked as valid
_computation_in_progress = True  # Trigger fresh computation
```

### 4. Updated Cache Invalidation Functions

#### `invalidate_team_caches(team_name)`
- **Before**: Deleted cached data and reset timestamps  
- **After**: Marks cache as invalid but preserves data and timestamps
- **Benefit**: Rapid invalidations during team changes don't cause expensive recomputation

#### `clear_team_caches()` and `force_clear_all_caches()`
- **Behavior**: Still actually clear cache data (for complete resets)
- **Use Case**: Game mode changes, complete restarts
- **Validity Reset**: Resets validity flags to `True` since cache is cleared

## Compatibility with Existing Code

### team_management.py
```python
# Still works as before - marks team cache as invalid without expensive recomputation
invalidate_team_caches(team_name)
emit_dashboard_team_update()  # Uses cached data if within refresh delay
```

### game.py  
```python
# Still works as before - marks team cache as invalid after answer submission
invalidate_team_caches(team_name)
emit_dashboard_team_update()  # Uses cached data if within refresh delay
```

### dashboard.py
```python
# Still works as before - forces complete cache reset for mode changes
force_clear_all_caches()
emit_dashboard_full_update()  # Always recomputes after force clear
```

## Benefits

### 1. Performance Improvements
- **Rapid invalidations** (e.g., multiple players leaving/joining) no longer cause expensive recomputation spikes
- **Throttling periods** protect against performance degradation during high activity
- **Periodic refreshes** ensure data stays fresh over time

### 2. Maintained Functionality  
- **Existing emit patterns** work unchanged
- **Test compatibility** preserved - throttling tests still pass
- **Cache invalidation** still works for its intended purpose

### 3. Better User Experience
- **Dashboard responsiveness** maintained during rapid team changes
- **Consistent update timing** regardless of invalidation frequency
- **No duplicate expensive operations** during brief periods

## Implementation Details

### Cache Key Format
Cache keys for decorated functions follow the pattern: `"('Team1')"` or `"('Team1', 'arg2')"`

### Thread Safety
- Single `RLock` protects all cache operations
- Computation flags prevent race conditions
- Expensive operations performed outside locks

### Error Handling
- Computation flags cleared on exceptions
- Graceful degradation when cache operations fail
- Comprehensive logging for debugging

## Testing

All existing tests pass with the new implementation:
- ✅ `test_selective_cache_invalidation.py` - Updated to reflect new behavior
- ✅ `test_dashboard_throttling.py` - Preserved original timing behavior
- ✅ Cache invalidation marks data as invalid rather than deleting it
- ✅ Throttling still provides periodic refreshes after delay periods

## Usage Guidelines

### When to Use `invalidate_team_caches(team_name)`
- Player joins/leaves team
- Team answers submitted  
- Any team-specific data change
- **Effect**: Marks cache invalid, next refresh will recompute

### When to Use `clear_team_caches()` or `force_clear_all_caches()`
- Game mode changes
- Complete game resets
- System-wide cache corruption
- **Effect**: Actually clears cache, forces immediate recomputation

### Refresh Delay Constants
- `REFRESH_DELAY_QUICK = 1.0` seconds - For frequent team updates
- `REFRESH_DELAY_FULL = 3.0` seconds - For expensive full dashboard updates

The improved system provides the best of both worlds: protection against expensive recomputation during rapid changes, while maintaining data freshness through periodic updates.