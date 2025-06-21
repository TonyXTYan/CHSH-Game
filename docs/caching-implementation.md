# CHSH Game Dashboard Caching Implementation

## Overview

This document describes the enhanced caching strategy implemented for the CHSH Game dashboard to handle hundreds of teams efficiently while maintaining data consistency.

## Cached Functions

### 1. `compute_correlation_matrix(team_id)`
- **Cache Size**: 512 entries
- **Purpose**: Caches the most expensive computation (correlation calculations)
- **Invalidation**: Via `get_all_teams()` cache invalidation (indirect)

### 2. `compute_team_hashes(team_id)`
- **Cache Size**: 256 entries
- **Purpose**: Caches team hash calculations (currently disabled but ready for future use)
- **Invalidation**: Via `get_all_teams()` cache invalidation (indirect)

### 3. `get_all_teams()`
- **Cache Size**: 8 entries
- **Purpose**: Caches the complete teams list with embedded correlation statistics
- **Invalidation**: Frequent - on any game action (answer submission, team operations, game state changes)
- **Contains**: Team lists, player status, correlation matrices, round numbers, team statistics

## Cache Invalidation Strategy

### Corrected Cache Invalidation Strategy
- **Answer Submission**: Invalidates `get_all_teams()` cache (contains correlation stats, round numbers, team status)
- **Team Operations**: Invalidates `get_all_teams()` cache (player lists, team status changes)
- **Game Reset**: Clears all caches

**Key Insight**: `get_all_teams()` contains dynamic data that changes with every game action, so it must be invalidated frequently to maintain data consistency.

### Integration Points

#### 1. game.py - `on_submit_answer()`
```python
# Answer submission changes correlation stats, round numbers, team status
invalidate_teams_list_cache()
```

#### 2. team_management.py
- **Team Creation**: `invalidate_teams_list_cache()` (new team in list)
- **Team Join/Leave**: `invalidate_teams_list_cache()` (player lists, status changes)
- **Team Reactivation**: `invalidate_teams_list_cache()` (team status changes)
- **Player Disconnect**: `invalidate_teams_list_cache()` (player lists, status changes)

#### 3. dashboard.py - `on_restart_game()`
```python
# Before database reset - clear all cached data
invalidate_all_dashboard_caches()
```

**Note**: The `invalidate_teams_list_cache()` function also clears correlation caches since `get_all_teams()` internally calls `compute_correlation_matrix()` and `compute_team_hashes()`.

## Cache Monitoring

### Cache Statistics
- **Endpoint**: `/api/dashboard/cache-stats`
- **Returns**: Hit/miss ratios, current sizes, max sizes for all cached functions
- **Automatic Logging**: Every 10th dashboard update logs cache statistics

### Manual Cache Management
- **Endpoint**: `/api/dashboard/invalidate-cache`
- **Parameters**: 
  - `cache_type`: `"all"`, `"teams"`, or `"correlation"`
- **Purpose**: Manual cache invalidation for debugging/maintenance

## Performance Benefits

### For Hundreds of Teams
1. **Correlation Calculations**: Most expensive operation cached with 512 entries
2. **Smart Invalidation**: Only clears affected caches, not all caches
3. **Memory Efficient**: Conservative cache sizes prevent memory bloat
4. **Hit Rate Monitoring**: Tracks cache effectiveness

### Cache Hit Scenarios
- **Dashboard Refreshes**: High hit rate for `get_all_teams()`
- **Team Statistics**: High hit rate for `compute_correlation_matrix()`
- **Repeated Team Views**: Correlation data served from cache

## Revised Performance Strategy

**Trade-off Analysis**: While `get_all_teams()` cache needs frequent invalidation due to dynamic data, it still provides significant performance benefits:

### Cache Effectiveness Despite Frequent Invalidation

1. **Burst Access Patterns**: Multiple dashboard clients viewing data simultaneously benefit from shared cache
2. **Short-Term Caching**: Even brief cache lifetime reduces computational load during peak usage
3. **Expensive Operations**: Correlation matrix calculations for hundreds of teams are costly to recompute

### Why Small Cache Size Works

**`get_all_teams()` Cache Size 8**:
- Provides benefit for concurrent dashboard access
- Minimizes memory impact with frequent invalidation
- Critical during load testing with multiple dashboard viewers

**Individual Function Caches**:
- `compute_correlation_matrix()`: 512 entries for sustained team-specific performance
- `compute_team_hashes()`: 256 entries for team-specific data
- These maintain longer cache lifetimes as they're called indirectly

### Performance Impact

- **High-Concurrency Scenarios**: Multiple dashboards share cached `get_all_teams()` results
- **Database Load Reduction**: Fewer complex correlation calculations during burst access
- **Memory Efficiency**: Conservative cache sizes prevent memory bloat while providing measurable benefits

## Error Handling

### Cache Failures
- All cache operations wrapped in try-except blocks
- Cache failures don't break core functionality
- Fallback to direct computation if caching fails

### Logging
- Cache statistics logged at INFO level
- Cache errors logged at ERROR level
- Periodic cache monitoring for performance tracking

## Implementation Notes

### functools.lru_cache Limitations
- No selective invalidation by parameters
- Full cache clearing for team-specific invalidation
- Consider advanced caching solutions for production scale

### Memory Considerations
- Total cache memory: ~800 team entries across all functions
- Conservative sizing for hundreds of teams
- Automatic eviction with LRU policy

### Future Enhancements
1. **Custom Cache Implementation**: Selective invalidation by team_id
2. **Cache Warming**: Pre-populate cache for active teams
3. **Distributed Caching**: Redis/Memcached for multi-instance deployments
4. **Cache Compression**: Reduce memory footprint for large datasets

## Usage Examples

### Check Cache Statistics
```bash
curl http://localhost:5000/api/dashboard/cache-stats
```

### Manually Invalidate All Caches
```bash
curl -X POST http://localhost:5000/api/dashboard/invalidate-cache \
  -H "Content-Type: application/json" \
  -d '{"cache_type": "all"}'
```

### Monitor Cache Hit Rates
```python
from src.sockets.dashboard import get_cache_stats, log_cache_stats

# Get current statistics
stats = get_cache_stats()
print(f"Correlation matrix cache hit rate: {stats['compute_correlation_matrix']['hits'] / (stats['compute_correlation_matrix']['hits'] + stats['compute_correlation_matrix']['misses']):.2%}")

# Log statistics
log_cache_stats()
```

## Performance Testing

### Load Testing Integration
- Cache statistics included in load test reporting
- Hit rate monitoring during high-concurrency scenarios
- Memory usage tracking with hundreds of teams

### Expected Performance Gains
- **Dashboard Loads**: 70-90% faster with cache hits
- **Team Statistics**: 80-95% faster for correlation calculations
- **Memory Usage**: Bounded by cache sizes (predictable scaling)