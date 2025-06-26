# Player Question Assignment Fix

## Problem Summary

Players 1 and 2 sometimes had mixed question sets (A/B and X/Y) in the "new" game mode, indicating a problem in the game logic where player assignments were not consistent.

### Root Cause

The issue was in the `start_new_round_for_pair` function in `src/game_logic.py`. The function was using the order of players in the `team_info['players']` list to determine question assignments, rather than using the actual database player slot assignments.

```python
# OLD (problematic) code:
player1, player2 = team_info['players']
socketio.emit('new_question', {..., 'item': p1_item.value}, room=player1)
socketio.emit('new_question', {..., 'item': p2_item.value}, room=player2)
```

This approach was problematic because:
1. The order in `team_info['players']` could change during reconnections
2. Players could join in a different order than their database slot assignment
3. In "new" mode, Player 1 should ALWAYS get A/B questions and Player 2 should ALWAYS get X/Y questions

## Solution Implemented

### 1. Enhanced Game Logic (`src/game_logic.py`)

**Key Changes:**
- Added database team lookup to get actual player slot assignments
- Modified question assignment to use database player slots instead of list order
- Added validation to ensure session IDs match between database and current state

```python
# NEW (fixed) code:
# Get the database team to determine actual player slots
db_team = db.session.get(Teams, team_info['team_id'])

# Map session IDs to their database player slots
player1_sid = db_team.player1_session_id
player2_sid = db_team.player2_session_id

# Send questions to players using actual database player slots
socketio.emit('new_question', {..., 'item': p1_item.value}, room=player1_sid)
socketio.emit('new_question', {..., 'item': p2_item.value}, room=player2_sid)
```

**Validation Added:**
- Verify database team exists
- Ensure both player session IDs are present in database
- Confirm connected players match database session IDs

### 2. Enhanced State Management (`src/state.py`)

**Added Player Slot Tracking:**
- Added `player_slots` dictionary to team state structure
- Added helper methods `get_player_slot()` and `set_player_slot()`
- Enhanced team state documentation

### 3. Updated Team Management (`src/sockets/team_management.py`)

**Enhanced Team Creation/Joining:**
- Track player slots during team creation (creator = Player 1)
- Track player slots during team joining (joiner gets next available slot)
- Maintain player slot mapping for reconnection scenarios

### 4. Fixed Circular Import Issue (`src/config.py`)

**Import Management:**
- Deferred socket handler initialization to avoid circular imports
- Created `initialize_socket_handlers()` function for manual initialization

## Comprehensive Test Suite

### Unit Tests (`tests/unit/test_player_question_assignment.py`)

**Test Coverage:**
1. **Correct Player Assignment**: Verify new mode assigns A/B to Player 1, X/Y to Player 2
2. **Player Order Independence**: Ensure assignment works regardless of connection order
3. **Reconnection Scenarios**: Validate consistent assignment after reconnections
4. **Classic Mode Preservation**: Ensure classic mode behavior unchanged
5. **Error Handling**: Test missing teams, invalid session IDs, etc.
6. **Mode Transitions**: Verify correct behavior when switching modes mid-game
7. **Comprehensive Coverage**: Ensure all valid combinations are eventually covered

### Integration Tests (`tests/integration/test_player_question_integration.py`)

**Real-World Scenarios:**
1. **Team Creation Flow**: Test realistic team creation and joining
2. **Database Integration**: Verify proper database slot assignment
3. **Player Order Scenarios**: Test various connection orders
4. **Mode Switching**: Test mode changes during active gameplay

## Key Benefits

### 1. **Consistent Player Assignments**
- Player 1 (database slot 1) always gets A/B questions in new mode
- Player 2 (database slot 2) always gets X/Y questions in new mode
- Assignment independent of connection order or reconnection events

### 2. **Robust Error Handling**
- Graceful handling of missing database teams
- Validation of session ID consistency
- Proper fallback behavior for invalid states

### 3. **Backward Compatibility**
- Classic mode behavior completely preserved
- Existing teams continue to work correctly
- No breaking changes to existing functionality

### 4. **Enhanced Reliability**
- Reduced race conditions during reconnections
- Consistent behavior across different connection scenarios
- Better state management and tracking

## Testing Results

All tests pass successfully:
- ✅ 9/9 new unit tests for player question assignment
- ✅ Updated existing game logic tests
- ✅ Comprehensive scenario coverage
- ✅ Error handling validation
- ✅ Mode transition verification

## Files Modified

1. `src/game_logic.py` - Core fix for player question assignment
2. `src/state.py` - Enhanced state management with player slot tracking
3. `src/sockets/team_management.py` - Updated team creation/joining logic
4. `src/config.py` - Fixed circular import issues
5. `tests/unit/test_game_logic.py` - Updated existing tests for new validation
6. `tests/unit/test_player_question_assignment.py` - New comprehensive test suite
7. `tests/integration/test_player_question_integration.py` - New integration tests

## Implementation Notes

### Database Schema
No database schema changes were required. The fix utilizes existing fields:
- `Teams.player1_session_id` - Session ID for Player 1 (database slot 1)
- `Teams.player2_session_id` - Session ID for Player 2 (database slot 2)

### Game Mode Behavior
- **New Mode**: Player 1 → A/B questions, Player 2 → X/Y questions (FIXED)
- **Classic Mode**: Any player can get any question type (UNCHANGED)

### Performance Impact
Minimal performance impact:
- Single additional database query per round (cached by SQLAlchemy)
- Small amount of additional validation logic
- No impact on existing functionality

This fix ensures that the CHSH game's "new" mode works as intended, with consistent and predictable player question assignments regardless of connection order or reconnection events.