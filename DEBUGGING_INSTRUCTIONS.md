# Debugging Player Disconnection and Rejoin Issues

## Issues Reported
1. "Invalid team information" error when trying to rejoin
2. Other player and dashboard don't see when a player disconnects

## Fixes Applied

### 1. Fixed Missing `team_id` in `team_joined` Event
**Problem**: When a player joined a team, the `team_id` wasn't included in the response, so it couldn't be saved for reconnection.

**Fix**: Added `team_id` to the `team_joined` event in `src/sockets/team_management.py` line ~270.

### 2. Added Better Error Messages and Logging
**Problem**: Generic "Invalid team information" error made debugging difficult.

**Fix**: Added detailed logging and specific error messages in the rejoin handler.

### 3. Enhanced Browser Disconnect Detection
**Problem**: Browser refresh doesn't always immediately trigger disconnect events.

**Fix**: Added `beforeunload` event handler to force immediate disconnect.

### 4. Added Comprehensive Debugging
Added console logging throughout the rejoin process to help identify issues.

## How to Test the Fixes

### Option 1: Use Browser Developer Tools
1. Open browser developer tools (F12)
2. Go to Console tab
3. Create a team with Player 1
4. Join the team with Player 2 
5. **Check console logs** - you should see:
   ```
   Team created event data: {team_name: "...", team_id: ..., ...}
   Saving team session data: {teamName: "...", teamId: ..., ...}
   ```
6. Refresh Player 2's browser
7. **Check console logs** - you should see:
   ```
   showRejoinOption called
   Raw localStorage data: {...}
   Parsed session data: {...}
   Showing rejoin option for saved data: {...}
   ```

### Option 2: Check Server Logs
1. Start the server with logging enabled
2. Check server logs for rejoin attempts:
   ```
   [INFO] Rejoin attempt: team_name='...', team_id='...', sid='...'
   ```

## Common Issues and Solutions

### Issue: "Invalid team information" Error

**Cause**: `team_id` is missing or null in localStorage

**Debug Steps**:
1. Open browser console after creating/joining a team
2. Check: `localStorage.getItem('quizSessionData')`
3. Look for `teamId` field - it should be a number, not null

**Solution**: If `teamId` is null, the team creation/join events aren't sending `team_id`. Check server logs for the team creation response.

### Issue: Disconnect Not Detected

**Cause**: Browser refresh doesn't always trigger immediate disconnect

**Debug Steps**:
1. In browser console, monitor for:
   - `player_left` events on remaining player
   - `team_status_update` events with `status: 'waiting_pair'`
2. Check server logs for disconnect messages

**Solution**: The `beforeunload` handler should help, but socket.io disconnect detection can be delayed.

### Issue: Rejoin UI Not Showing

**Cause**: Timing issues or missing localStorage data

**Debug Steps**:
1. Check browser console for `showRejoinOption called` message
2. Verify localStorage data exists: `localStorage.getItem('quizSessionData')`
3. Check for DOM elements: `document.getElementById('rejoinSection')`

## Testing Workflow

1. **Player 1**: Create team "TestTeam"
   - Console should show: `Team created event data: {...}`
   - Console should show: `Saving team session data: {...}`

2. **Player 2**: Join team "TestTeam" 
   - Console should show: `Team joined event data: {...}`
   - Console should show: `Saving team session data: {...}`

3. **Verify team is active**: Both players should see "Team Paired Up!" status

4. **Player 2**: Refresh browser (F5)
   - Player 1 should see: "A team member has disconnected" 
   - Player 1 status should change to: "Waiting for Player..."
   - Player 1's response inputs should be disabled

5. **Player 2**: After page reloads
   - Console should show: `showRejoinOption called`
   - Should see rejoin UI with "Previous Team Found"
   - Click "Rejoin Team"

6. **Expected Result**:
   - Player 2 rejoins successfully
   - Both players see "Team Paired Up!" again
   - Response inputs are re-enabled

## If Issues Persist

If you're still seeing "Invalid team information":

1. **Check browser console** for the exact data being sent:
   ```javascript
   // After joining a team, run this in console:
   console.log('Stored data:', localStorage.getItem('quizSessionData'));
   ```

2. **Check server logs** for the rejoin attempt details

3. **Try manual rejoin** in browser console:
   ```javascript
   // After reconnecting, try manual rejoin:
   const data = JSON.parse(localStorage.getItem('quizSessionData'));
   console.log('Manual rejoin with:', data);
   socket.emit('rejoin_team', {team_name: data.teamName, team_id: data.teamId});
   ```

## Temporary Workaround

If rejoin still fails, use the existing **reactivate team** feature:
1. Go to "Inactive Teams" section
2. Click "Reactivate & Join" on your previous team
3. This will restore the team and preserve all previous responses

## Test Script

I've created `debug_disconnect.py` that can be run to test the functionality programmatically. Run it with a local server to verify the fixes work correctly.