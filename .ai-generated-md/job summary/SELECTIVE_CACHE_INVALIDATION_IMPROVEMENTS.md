# Selective Cache Invalidation Strategy Implementation

## Overview

Implemented a selective cache invalidation system to replace the previous aggressive cache clearing strategy. This ensures that teams that haven't been updated can continue using their cached results, while only invalidating caches for teams that have actually changed.

## Problem Addressed

**Previous Issue**: The existing cache invalidation strategy was too aggressive:
- When ANY team had a change (player join/leave, answer submission, etc.), ALL team caches were cleared globally
- Teams that hadn't been updated lost their expensive cached calculation results unnecessarily
- This resulted in poor performance as expensive statistics calculations had to be recomputed for unchanged teams

## Solution: Selective Cache Invalidation System

### 1. Custom SelectiveCache Class

Created a thread-safe custom cache implementation with the following features:

```python
class SelectiveCache:
    def __init__(self, maxsize: int = CACHE_SIZE):
        self.maxsize = maxsize
        self._cache: Dict[str, Any] = {}
        self._access_order: List[str] = []  # LRU tracking
        self._lock = threading.RLock()
```

**Key Features**:
- **LRU Eviction**: Maintains least-recently-used eviction policy for memory management
- **Thread Safety**: Uses RLock for safe concurrent access
- **Selective Invalidation**: `invalidate_by_team(team_name)` method to clear only specific team's cache entries
- **Pattern Matching**: Intelligent key matching to identify team-specific cache entries

### 2. Selective Cache Decorator

Replaced Python's built-in `@lru_cache` decorators with custom `@selective_cache`:

```python
@selective_cache(cache_instance)
def cached_function(team_name: str, ...):
    # Expensive computation
    return result
```

**Benefits**:
- Drop-in replacement for `@lru_cache`
- Supports team-specific invalidation via `cache_invalidate_team(team_name)`
- Maintains same performance characteristics as LRU cache
- Adds cache management methods to decorated functions

### 3. Updated Cache Architecture

**Before**:
```python
@lru_cache(maxsize=CACHE_SIZE)
def compute_team_statistics(team_name: str):
    # ... expensive computation
```

**After**:
```python
@selective_cache(_classic_stats_cache)
def compute_team_statistics(team_name: str):
    # ... expensive computation
```

**Functions Updated**:
- `compute_team_hashes(team_name)` → `@selective_cache(_hash_cache)`
- `compute_correlation_matrix(team_name)` → `@selective_cache(_correlation_cache)`
- `compute_success_metrics(team_name)` → `@selective_cache(_success_cache)`
- `_calculate_team_statistics(team_name)` → `@selective_cache(_classic_stats_cache)`
- `_calculate_success_statistics(team_name)` → `@selective_cache(_new_stats_cache)`
- `_process_single_team(...)` → `@selective_cache(_team_process_cache)`

### 4. New Invalidation Functions

#### `invalidate_team_caches(team_name: str)`
- **Purpose**: Selectively invalidate caches for a specific team only
- **Preserves**: Cached results for all other teams
- **Thread-safe**: Uses proper locking mechanism
- **Intelligent**: Only clears global throttling caches if they contain the affected team's data

#### Updated `clear_team_caches()`
- **Purpose**: Clear ALL team caches (kept for backward compatibility)
- **Usage**: Only when global clearing is necessary
- **Note**: Now documents that `invalidate_team_caches(team_name)` should be preferred for specific teams

#### `force_clear_all_caches()`
- **Purpose**: Force clear ALL caches including throttling state
- **Usage**: Only for critical situations requiring complete cache reset (e.g., game mode changes)

### 5. Strategic Cache Invalidation Usage

Updated cache invalidation calls throughout the codebase to use selective invalidation where appropriate:

**Team Management Operations**:
```python
# OLD: Cleared ALL team caches
clear_team_caches()

# NEW: Only clear caches for the affected team
invalidate_team_caches(team_name)
```

**Usage Locations**:
- **Player disconnect**: `invalidate_team_caches(team_name)` instead of global clear
- **Team join/leave**: `invalidate_team_caches(team_name)` for specific team
- **Answer submission**: `invalidate_team_caches(team_name)` for submitting team
- **Team creation**: `invalidate_team_caches(team_name)` for new team

**Global Clearing Preserved For**:
- Game mode changes (affects all teams' calculations)
- Game resets (complete state change)
- Test environments (ensuring clean state)

### 6. Intelligent Global Cache Management

The system now intelligently manages global throttling caches:

```python
# Only clear global caches if they contain the affected team's data
if _cached_teams_result is not None:
    team_in_cache = any(team.get('team_name') == team_name for team in _cached_teams_result)
    if team_in_cache:
        _cached_teams_result = None
        _last_refresh_time = 0
```

**Benefits**:
- Preserves global caches that don't contain affected team's data
- Maintains throttling efficiency for unrelated operations
- Reduces unnecessary recomputation of expensive database queries

## Performance Improvements

### 1. Cache Retention
- **Teams not updated**: Continue using cached results indefinitely
- **Only affected teams**: Have their caches invalidated
- **Memory efficiency**: LRU eviction prevents unbounded growth

### 2. Reduced Computation
- **Before**: Any team change triggered recomputation for ALL teams
- **After**: Only affected team requires recomputation
- **Scalability**: Performance improvement increases with number of teams

### 3. Throttling Preservation
- **Global throttling caches**: Only cleared when they actually contain affected team's data
- **Database queries**: Avoided when possible through intelligent cache management
- **Dashboard updates**: More efficient with preserved throttling state

## Implementation Details

### Thread Safety
- All cache operations use `threading.RLock()` for safe concurrent access
- Atomic operations prevent race conditions during cache updates
- Lock management with proper exception handling

### Memory Management
- LRU eviction policy maintains bounded memory usage
- Cache size configurable via `CACHE_SIZE` constant
- Old cache entries automatically evicted when memory limit reached

### Error Handling
- Comprehensive error handling with proper logging
- Graceful degradation when cache operations fail
- Exception safety ensures locks are always released

## Backward Compatibility

- **API Compatibility**: All existing function signatures preserved
- **Import Structure**: Maintained existing import helper pattern
- **Test Compatibility**: All existing tests continue to work
- **Global Clearing**: `clear_team_caches()` still available for cases requiring complete cache reset

## Testing Considerations

The selective cache system is fully compatible with existing test infrastructure:

- **Test Isolation**: Tests continue to use `clear_team_caches()` for complete state reset
- **Performance Tests**: Can measure cache efficiency improvements
- **Functional Tests**: Ensure selective invalidation works correctly

## Future Enhancements

This foundation enables future optimizations:

1. **Cache Statistics**: Track hit/miss ratios per team
2. **Adaptive Eviction**: Team-specific eviction policies based on update frequency
3. **Distributed Caching**: Extension to multi-server deployments
4. **Cache Warming**: Proactive computation of likely-needed team statistics

## Summary

The selective cache invalidation system provides significant performance improvements while maintaining full backward compatibility. Teams that haven't been updated can continue using their expensive cached calculation results, while only teams with actual changes have their caches invalidated. This results in much more efficient resource usage and better scalability as the number of teams grows.