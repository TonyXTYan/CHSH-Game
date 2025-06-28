# Last Round Results Feature Implementation

## Overview

This feature enhances the CHSH Game waiting message to show results from the last completed round, providing players with immediate feedback on their team's performance.

## Features Implemented

### 1. Enhanced `round_complete` Event

**Backend Changes (`src/sockets/game.py`):**
- Enhanced the `round_complete` event to include detailed last round information
- Fetches both players' questions and answers from the database
- Includes fallback handling when round data is not available

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

**Updated Tests:**
- ✅ Updated existing `test_game_sockets.py` to work with enhanced round_complete event

## Technical Details

### Database Queries
The implementation adds two database queries when a round completes:
1. Fetch round details (`PairQuestionRounds.query.get()`)
2. Fetch player answers (`Answers.query.filter_by()`)

### Error Handling
- Graceful fallback when round data is not found
- Handles incomplete or missing answer data
- Maintains backward compatibility

### Performance Considerations
- Queries only execute when both players have answered (round completion)
- No additional queries during normal gameplay
- Client-side caching of last round results

## Usage Examples

### Classic Theme Examples
```
Last round, your team (P1/P2) were asked A/X and answer was True/False
Last round, your team (P1/P2) were asked B/Y and answer was False/True
```

### Food Theme Examples
```
Last round, your team (P1/P2) were asked 🍞/🥬 and decisions was Choose/Skip, that was yum 😋
Last round, your team (P1/P2) were asked 🥟/🍫 and decisions was Choose/Choose, that was bad 😭
Last round, your team (P1/P2) were asked 🥟/🍫 and decisions was Choose/Skip, that was yum 😋
```

## Files Modified

### Backend
- `src/sockets/game.py` - Enhanced round_complete event
- `tests/unit/test_game_sockets.py` - Updated existing test

### Frontend  
- `src/static/app.js` - Added result tracking and message generation
- `src/static/socket-handlers.js` - Enhanced round_complete handler

### Tests
- `tests/unit/test_last_round_results.py` - Comprehensive new test suite

## Verification

All tests pass:
- ✅ 8/8 new tests in `test_last_round_results.py`
- ✅ 8/8 existing tests in `test_game_sockets.py`

The feature is fully functional and ready for use in both classic and food themes.