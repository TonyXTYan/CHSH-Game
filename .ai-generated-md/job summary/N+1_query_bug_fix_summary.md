# N+1 Query Bug Fix - Dashboard Optimized Functions

## Background

The optimized dashboard functions `_compute_correlation_matrix_optimized()` and `_compute_success_metrics_optimized()` were designed to use pre-fetched data to avoid database queries. However, when the session ID-based player answer matching was implemented to fix the duplicate item bug, these functions introduced individual `Teams.query.get(team_id)` calls, which undermined their optimization strategy and reintroduced N+1 query issues.

## Problem Identified

**Issue Location**: `src/sockets/dashboard.py` lines ~1054 and ~1159

**Root Cause**: The optimized functions were making individual database queries to get team session IDs:

```python
# PROBLEMATIC CODE
def _compute_correlation_matrix_optimized(team_id: int, team_rounds: List[Any], team_answers: List[Any]):
    # Get team data for session ID mapping
    db_team = Teams.query.get(team_id)  # ❌ N+1 query issue!
```

**Impact**: When `get_all_teams()` processes multiple teams, each call to the optimized functions would trigger an individual database query, defeating the bulk optimization strategy.

## Solution Implemented

### 1. Function Signature Changes

Added optional `team_obj` parameter to both optimized functions:

```python
# BEFORE
def _compute_correlation_matrix_optimized(team_id: int, team_rounds: List[Any], team_answers: List[Any])

# AFTER
def _compute_correlation_matrix_optimized(team_id: int, team_rounds: List[Any], team_answers: List[Any], team_obj: Any = None)
```

### 2. Conditional Team Data Usage

Modified functions to use pre-fetched team data when available:

```python
# Use pre-fetched team data to avoid N+1 queries
if team_obj is None:
    # Fallback to database query if team_obj not provided (backward compatibility)
    team_obj = Teams.query.get(team_id)
    if not team_obj:
        logger.warning(f"Could not find team data for team_id: {team_id}")
        return default_result
        
db_team = team_obj
```

### 3. Updated Function Calls

Modified calling code to pass team objects:

```python
# In _process_single_team_optimized():
correlation_result = _compute_correlation_matrix_optimized(team_id, team_rounds, team_answers, team_obj)
success_result = _compute_success_metrics_optimized(team_id, team_rounds, team_answers, team_obj)

# In get_all_teams():
team_data = _process_single_team_optimized(
    team.team_id, team.team_name, team.is_active,
    team.created_at.isoformat() if team.created_at else None,
    current_round, players[0], players[1],
    team_rounds, team_answers,
    team  # Pass team object to avoid N+1 queries
)
```

### 4. Test Updates

Updated test functions to work with the new parameter:

```python
# Create mock team object with session IDs
mock_team = MagicMock()
mock_team.player1_session_id = 'player1_session'
mock_team.player2_session_id = 'player2_session'

result = _compute_correlation_matrix_optimized(1, mock_rounds, mock_answers, mock_team)
```

## Performance Benefits

- **Before**: N database queries for N teams (N+1 problem)
- **After**: 1 bulk query for all teams (optimal)
- **Backward Compatibility**: Functions still work without team_obj parameter
- **Zero Regression**: All existing functionality preserved

## Files Modified

1. **`src/sockets/dashboard.py`**:
   - Updated `_compute_correlation_matrix_optimized()` signature and implementation
   - Updated `_compute_success_metrics_optimized()` signature and implementation  
   - Updated `_process_single_team_optimized()` signature and calls
   - Updated `get_all_teams()` function call

2. **`tests/unit/test_dashboard_sockets.py`**:
   - Updated `test_compute_correlation_matrix_optimized()` to use team object
   - Updated `test_compute_success_metrics_optimized()` to use team object

## Test Results

- **Dashboard Tests**: 89 passed, 10 skipped ✅
- **Last Round Results Tests**: 9 passed ✅
- **No Regressions**: All existing functionality working correctly ✅

## Key Benefits

1. **Performance**: Eliminated N+1 queries for bulk team processing
2. **Backward Compatibility**: Functions work with or without team_obj parameter
3. **Maintainability**: Clear separation between optimized and fallback paths
4. **Correctness**: Preserves session ID-based player matching for duplicate items

This fix ensures that the dashboard's bulk optimization strategy works as intended while maintaining the correct player answer matching logic for statistical integrity.