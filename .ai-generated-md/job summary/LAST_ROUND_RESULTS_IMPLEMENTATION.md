# Last Round Results Feature Implementation

## Overview

This feature enhances the CHSH Game waiting message to show results from the last completed round, providing players with immediate feedback on their team's performance.

## ⚠️ **CRITICAL BUG FIX APPLIED**

**Issue Resolved**: Fixed a serious bug in player answer matching logic that occurred when both players received the same item (e.g., both get "A" or both get "X").

**Previous Broken Logic**:
```python
# BROKEN - matched by item only
for answer in round_answers:
    if answer.assigned_item.value == p1_item:
        p1_answer = answer.response_value  # Both answers could match here!
    elif answer.assigned_item.value == p2_item:
        p2_answer = answer.response_value
```

**Fixed Logic**:
```python
# FIXED - matches by player session ID
for answer in round_answers:
    if answer.player_session_id == db_team.player1_session_id:
        p1_answer = answer.response_value
    elif answer.player_session_id == db_team.player2_session_id:
        p2_answer = answer.response_value
```

**Why This Was Critical**: When both players receive the same item, the old logic would cause one answer to overwrite the other, resulting in data loss and incorrect results display.

## Features Implemented

### 1. Enhanced `round_complete` Event

**Backend Changes (`src/sockets/game.py`):**
- Enhanced the `round_complete` event to include detailed last round information
- **FIXED**: Uses `player_session_id` to correctly match answers to players
- Fetches team data to map session IDs to player positions
- Includes multiple fallback layers when data is unavailable

**Data Structure:**
```json
{
  "team_name": "Team Name",
  "round_number": 1,
  "last_round_details": {
    "p1_item": "A",
    "p2_item": "X", 
    "p1_answer": true,
    "p2_answer": false
  }
}
```

### 2. Client-Side Implementation

**JavaScript Changes (`src/static/app.js`):**
- Added `lastRoundResults` state variable to track last round data
- Added `setLastRoundResults` callback function
- Enhanced `updateGameState()` to display last round results in waiting message
- Updated socket handler to capture last round details

**Socket Handler (`src/static/socket-handlers.js`):**
- Enhanced `round_complete` handler to store last round details

### 3. Themed Message Generation

**Classic Theme:**
```
"Last round, your team (P1/P2) were asked A/X and answer was True/False"
```

**Food Theme:**
```
"Last round, your team (P1/P2) were asked 🍞/🥬 and decisions was Choose/Skip, that was yum 😋"
```

**Food Theme Evaluation Logic:**
- B+Y (🥟+🍫) combinations should have different answers → `yum 😋` (optimal) or `bad 😭` (suboptimal)
- All other combinations should have same answers → `yum 😋` (optimal) or `yuck 🤮` (suboptimal)

### 4. Message Display Logic

The waiting message shows last round results in these scenarios:
- When a player has answered and is waiting for the next round
- When the game is not paused and there are last round results available
- Falls back to default "Waiting for next round..." when no results are available

### 5. Comprehensive Test Coverage

**Test File: `tests/unit/test_last_round_results.py`**

**Test Coverage:**
- ✅ Enhanced `round_complete` event with last round details
- ✅ Fallback behavior when round data is unavailable  
- ✅ Classic theme message generation
- ✅ Food theme message generation (optimal results)
- ✅ Food theme message generation (suboptimal results)
- ✅ Food evaluation for all item combinations
- ✅ Incomplete round data handling
- ✅ **NEW**: Duplicate item scenario (both players get same item)

**Updated Tests:**
- ✅ Updated existing `test_game_sockets.py` to work with enhanced round_complete event

## Technical Details

### Database Queries
The implementation adds queries when a round completes:
1. Fetch round details (`PairQuestionRounds.query.get()`)
2. **NEW**: Fetch team data (`Teams.query.get()`) to map session IDs
3. Fetch player answers (`Answers.query.filter_by()`)

### Error Handling
- Graceful fallback when round data is not found
- Graceful fallback when team data is incomplete
- Handles incomplete or missing answer data
- Maintains backward compatibility

### Performance Considerations
- Queries only execute when both players have answered (round completion)
- No additional queries during normal gameplay
- Client-side caching of last round results

## Duplicate Item Scenarios (Now Fixed!)

**Example Scenario**: Both players receive item "A"
- Player 1 (session: 'player1_sid') answers True
- Player 2 (session: 'player2_sid') answers False

**Result**: 
```
Last round, your team (P1/P2) were asked A/A and answer was True/False
```

**Critical**: Answers are correctly matched to the right players regardless of having the same item.

## Usage Examples

### Classic Theme Examples
```
Last round, your team (P1/P2) were asked A/X and answer was True/False
Last round, your team (P1/P2) were asked A/A and answer was True/False  ← Duplicate items now work!
Last round, your team (P1/P2) were asked B/Y and answer was False/True
```

### Food Theme Examples
```
Last round, your team (P1/P2) were asked 🍞/🥬 and decisions was Choose/Skip, that was yum 😋
Last round, your team (P1/P2) were asked 🥟/🍫 and decisions was Choose/Choose, that was bad 😭
Last round, your team (P1/P2) were asked 🍞/� and decisions was Choose/Skip, that was yuck 🤮  ← Duplicate items work!
```

## Files Modified

### Backend
- `src/sockets/game.py` - **FIXED**: Enhanced round_complete event with correct player matching
- `tests/unit/test_game_sockets.py` - Updated existing test

### Frontend  
- `src/static/app.js` - Added result tracking and message generation
- `src/static/socket-handlers.js` - Enhanced round_complete handler

### Tests
- `tests/unit/test_last_round_results.py` - Comprehensive test suite with duplicate item test

## Verification

All tests pass:
- ✅ 9/9 tests in `test_last_round_results.py` (including new duplicate item test)
- ✅ 8/8 existing tests in `test_game_sockets.py`

**Critical bug fixed**: The feature now correctly handles all CHSH game scenarios, including when both players receive identical items.