# Dashboard Force Refresh Removal

## Summary

Successfully removed the `force_refresh` parameter from the dashboard codebase and simplified the throttling mechanism to use a single refresh rate of `REFRESH_DELAY_QUICK` (0.5 seconds).

## Changes Made

### 1. Modified `src/sockets/dashboard.py`

#### Constants Updated:
- Removed `REFRESH_DELAY = 1` (1 second)
- Kept `REFRESH_DELAY_QUICK = 0.5` as the single refresh rate
- Updated comment to "maximum refresh rate"

#### Global Variables Simplified:
- Removed `_last_force_refresh_time = 0`
- Kept `_last_refresh_time = 0` as the single throttling timer

#### Function Signatures Updated:
- `get_all_teams(force_refresh: bool = False)` → `get_all_teams()`
- `emit_dashboard_team_update(force_refresh: bool = False)` → `emit_dashboard_team_update()`

#### Throttling Logic Simplified:
- Removed complex dual throttling logic with separate force_refresh handling
- Now uses single throttling with `REFRESH_DELAY_QUICK` for all calls
- Removed all conditional logic based on `force_refresh` parameter

#### Cache Management:
- Updated `clear_team_caches()` to remove `_last_force_refresh_time` handling
- Simplified cache variable management

### 2. Modified `src/sockets/team_management.py`

#### Updated Function Calls:
- `emit_dashboard_team_update(force_refresh=True)` → `emit_dashboard_team_update()`
- `emit_dashboard_team_update(force_refresh=team_is_now_full)` → `emit_dashboard_team_update()`

#### Locations Updated:
- `handle_disconnect()` - Line 263: Removed force_refresh for disconnections
- `on_join_team()` - Line 454: Removed conditional force_refresh when team becomes full
- `on_leave_team()` - Line 634: Removed force_refresh for team leaving

## Impact

### Before:
- Two different throttling delays: 1 second (regular) and 0.5 seconds (force_refresh)
- Complex logic to determine when to use force_refresh vs regular refresh
- Separate tracking variables for each throttling type
- Comments about "critical team state changes" requiring immediate updates

### After:
- Single throttling delay: 0.5 seconds for all updates
- Simplified logic with consistent behavior
- Single tracking variable for throttling
- Maximum refresh rate is now consistently `REFRESH_DELAY_QUICK` (0.5 seconds)

### Benefits:
1. **Simplified Code**: Removed complexity of dual throttling system
2. **Consistent Performance**: All dashboard updates now use the faster 0.5-second refresh rate
3. **Easier Maintenance**: No need to decide when to use force_refresh vs regular refresh
4. **Better User Experience**: Faster updates for all scenarios (previously "non-critical" updates were slower)

## Testing Required

The following test files will need updates to remove `force_refresh` parameters:
- `tests/unit/test_dashboard_sockets.py`
- `tests/unit/test_dashboard_throttling.py`

Tests that specifically test `force_refresh` behavior should be updated or removed as appropriate.

## Verification

- [x] Code imports successfully
- [x] Function signatures updated correctly
- [x] All call sites updated to remove force_refresh parameter
- [x] Throttling logic simplified to single rate
- [x] Global variables cleaned up
- [ ] Tests updated (requires separate task)

The dashboard now operates with a consistent maximum refresh rate of 0.5 seconds for all updates, eliminating the complexity of the previous dual-throttling system.