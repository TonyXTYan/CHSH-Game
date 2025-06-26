# Team Disconnection and Reconnection Implementation

## Overview

This implementation addresses the team disconnection and reconnection issues in the CHSH game. The solution ensures that when one player disconnects, the team status properly changes to "waiting_pair" and the remaining player's response input is disabled. Most importantly, when the disconnected player reconnects, they can rejoin their previous team.

## 🐛 Critical Bug Fix Applied

**Issue Discovered**: The original implementation had **two separate `@socketio.on('disconnect')` handlers** - one in `team_management.py` and one in `dashboard.py`. Flask-SocketIO only executes the **last registered handler**, which meant the team disconnect logic was never being executed when players refreshed their browsers.

**Result**: When a player refreshed, the other player saw no change, and the dashboard also showed no change.

**Solution**: Consolidated both disconnect handlers into a single handler in `team_management.py` that handles both team and dashboard disconnections. Also fixed missing `leave_room()` calls and improved room management.

### Changes Made for Bug Fix:
- **Removed**: `@socketio.on('disconnect')` from `dashboard.py`  
- **Added**: `handle_dashboard_disconnect()` function to encapsulate dashboard logic
- **Updated**: Single disconnect handler in `team_management.py` calls both team and dashboard logic
- **Fixed**: Added proper `leave_room()` calls before emitting to team rooms
- **Updated**: All `_import_dashboard_functions()` calls to handle the new return signature

## Key Features Implemented

### 1. Disconnection Tracking
- **State Management**: Added `disconnected_players` to the application state to track players who disconnect from full teams.
- **Player Slot Tracking**: Records which player slot (1 or 2) the disconnected player occupied.
- **Timestamp Recording**: Tracks when the disconnection occurred for potential cleanup logic.

### 2. Team Status Management
- **Proper Status Updates**: When one player disconnects from a full team, the team status changes from "active" to "waiting_pair".
- **Input Disabling**: The remaining player's response input is disabled (`disable_input: true`) until the team is complete again.
- **Database Consistency**: Session IDs in the database are properly cleared when players disconnect.

### 3. Reconnection Logic
- **Seamless Rejoin**: Players can rejoin their previous team using the standard `join_team` mechanism.
- **Reconnection Detection**: The system detects when a join request is actually a reconnection and provides appropriate messaging.
- **State Restoration**: When a player reconnects, the team becomes active again and input is re-enabled.

### 4. Answer Submission Protection
- **Team Validation**: Answer submission now validates that the team is in "active" status before accepting responses.
- **Incomplete Team Blocking**: Teams with only one player cannot submit answers.

## Implementation Details

### State Management (`src/state.py`)
```python
class AppState:
    def __init__(self):
        # ... existing state ...
        # Track disconnected players for reconnection
        self.disconnected_players = {}  # {team_name: {'player_session_id': old_sid, 'player_slot': 1|2, 'disconnect_time': timestamp}}
```

### Core Functions (`src/sockets/team_management.py`)

#### Helper Functions
- `_get_player_slot_in_team()`: Determines which slot (1 or 2) a player occupies
- `_track_disconnected_player()`: Records disconnection info for potential reconnection
- `_clear_disconnected_player_tracking()`: Removes tracking when no longer needed
- `_can_rejoin_team()`: Checks if a player can rejoin a team

#### Enhanced Socket Handlers
- **`handle_disconnect()`** (FIXED): 
  - **Now properly called** when players disconnect
  - Handles both team and dashboard disconnections
  - Tracks disconnected players from full teams
  - Sets team status to "waiting_pair"
  - Emits status updates with `disable_input: true`
  - Properly calls `leave_room()` before emitting to team
  - Clears tracking when teams become completely inactive

- **`on_join_team()`**: 
  - Detects reconnection scenarios
  - Provides appropriate reconnection messaging
  - Re-enables input when teams become full
  - Clears disconnection tracking on successful reconnection

- **`on_leave_team()`**: 
  - Tracks deliberate departures from full teams
  - Maintains same behavior as disconnections for consistency

#### New Socket Handler
- **`on_get_reconnectable_teams()`**: Returns list of teams that a player can potentially rejoin

### Dashboard Integration (`src/sockets/dashboard.py`)
- **`handle_dashboard_disconnect()`**: Extracted dashboard disconnect logic into reusable function
- **Removed**: Duplicate `@socketio.on('disconnect')` handler that was overriding team logic

### Game Logic Protection (`src/sockets/game.py`)
Enhanced `on_submit_answer()` to validate team status:
```python
# Check if team is in proper active state (both players connected)
if team_info.get('status') != 'active':
    emit('error', {'message': 'Team is not active. Waiting for all players to connect.'})
    return
```

## Event Flow Examples

### Scenario 1: Player Disconnection (NOW WORKING!)
1. Two players in active team
2. Player 1 disconnects (browser refresh) → **Disconnect handler is now called!**
3. System tracks Player 1's disconnection
4. Team status → "waiting_pair"
5. Player 2 receives `team_status_update` with `disable_input: true`
6. Dashboard sees the team status change
7. Player 2 cannot submit answers until team is complete

### Scenario 2: Player Reconnection
1. Player 1 reconnects and sees available teams
2. Player 1 joins their previous team
3. System detects this as reconnection
4. Team status → "active"
5. Both players receive `team_status_update` with `disable_input: false`
6. Game resumes normally

### Scenario 3: Both Players Disconnect
1. Both players disconnect
2. Team becomes inactive
3. Disconnection tracking is cleared
4. Team can be reactivated using existing reactivation logic

## Testing Coverage

### New Test Cases
- **Disconnection Tracking**: Validates proper tracking of disconnected players
- **Reconnection Logic**: Tests successful reconnection scenarios
- **Team Status Updates**: Ensures proper status transitions and input disabling
- **Answer Submission Blocking**: Verifies protection against incomplete team submissions
- **Edge Cases**: Both players disconnecting, multiple reconnection attempts

### Test Results
- **42 tests passing** across team management and game sockets
- All existing functionality preserved
- New disconnect logic fully tested

### Test Files
- **`tests/unit/test_team_management.py`**: Enhanced with 10 new test cases covering all aspects of the implementation

## Database Considerations

### Answer Persistence
- **Existing Answers Preserved**: All previously submitted answers remain in the database when players disconnect
- **Team Reactivation**: When teams are reactivated, they resume from their last round number
- **Data Integrity**: No data loss occurs during disconnection/reconnection cycles

### Session ID Management
- **Clean Disconnection**: Database session IDs are properly cleared when players disconnect
- **Reconnection Updates**: Database is updated with new session IDs when players reconnect

## Client-Side Integration

### Required Client Changes
Clients should handle the new event properties:

```javascript
// Team status updates now include disable_input
socket.on('team_status_update', (data) => {
    if (data.disable_input) {
        // Disable response input UI
    } else {
        // Enable response input UI
    }
});

// Team join events now include reconnection info
socket.on('team_joined', (data) => {
    if (data.is_reconnection) {
        // Show "reconnected" message instead of "joined"
    }
});

// New event for getting reconnectable teams
socket.emit('get_reconnectable_teams');
socket.on('reconnectable_teams', (data) => {
    // Display available teams for reconnection
});
```

## Benefits

1. **✅ FIXED**: Disconnect handler now properly executes when players refresh browsers
2. **Improved User Experience**: Players can seamlessly rejoin teams after disconnections
3. **Data Integrity**: No loss of game progress or answers
4. **Fair Gameplay**: Input is disabled when teams are incomplete, preventing unfair advantages
5. **Robust State Management**: Proper handling of various disconnection scenarios
6. **Backward Compatibility**: Existing functionality remains unchanged

## Future Enhancements

1. **Automatic Reconnection**: Could implement automatic team rejoining based on browser session storage
2. **Timeout Logic**: Could add timeouts for disconnection tracking to prevent indefinite waiting
3. **Notification System**: Could add push notifications for team member reconnections
4. **Spectator Mode**: Could allow disconnected players to spectate their team until they can rejoin