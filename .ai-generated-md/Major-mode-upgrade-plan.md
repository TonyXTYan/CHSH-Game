# CHSH Game: Major Mode Upgrade Plan

## Overview

Implement a new game mode introducing player-based question restrictions and success-based metrics, with dashboard mode toggle functionality. Designed for minimal code changes while ensuring backwards compatibility.

### Current Architecture Summary

**Core Components:**
- `src/state.py`: Singleton AppState managing active_teams, player_to_team, connected_players
- `src/game_logic.py`: start_new_round_for_pair() randomly assigns questions from all ItemEnum values
- `src/sockets/team_management.py`: Player connections, team creation/joining, disconnect/reconnect logic
- `src/sockets/dashboard.py`: Metrics calculation with caching, correlation matrix, team statistics
- `src/models/quiz_models.py`: Database models Teams, Answers, PairQuestionRounds, ItemEnum(A,B,X,Y)

**Current Flow:** Players join teams → Dashboard starts game → Random question assignment → Answer submission → Physics metrics (CHSH, trace, balance)

### New Mode Requirements

1. **Question Restriction**: Player 1 gets only A,B questions; Player 2 gets only X,Y questions
2. **Success Metrics**: 
   - Success Rate: Percentage of rounds following optimal strategy
   - Success Rule: {B,Y} combinations require different answers; all others require same answers
   - Score: +1 successful round, -1 failed round, normalized by total rounds played
3. **Mode Toggle**: Dashboard switches between 'classic' and 'new' modes (affects only score calculation and question assignment)
4. **Dashboard Updates**: Correlation matrix shows success patterns instead of correlations in new mode
5. **Player UI Updates**: Display player position (Player 1/Player 2) in game interface, especially relevant in new mode
6. **Backwards Compatibility**: All existing functionality unchanged in classic mode

---

## Implementation Strategy

### Player Position Consistency
Leverage existing player position logic - no additional role mapping needed:
- Player 1 = team_info['players'][0] (maps to db_team.player1_session_id)
- Player 2 = team_info['players'][1] (maps to db_team.player2_session_id)
- Existing disconnect/reconnect mechanisms handle consistency perfectly

### Mode Switching
Mode changes only affect future question assignment and current metric calculations. All previous responses remain valid and useful. No game pause required - metrics simply recalculate using the new mode's logic.

---

## Implementation Steps

### Step 1: Core State Management
**Files:** src/state.py

**Tasks:**
1. Add game_mode = 'classic' to AppState.__init__()
2. Add game_mode reset to 'classic' in reset() method
3. No team management changes needed

**Tests:** State initialization, reset functionality, backwards compatibility

### Step 2: Question Assignment Logic
**Files:** src/game_logic.py

**Tasks:**
1. Add mode check in start_new_round_for_pair() before question assignment
2. Implement player-based filtering: Player 1 gets A,B only; Player 2 gets X,Y only
3. Maintain random selection within filtered sets
4. Keep classic mode unchanged (random from all items)

**Tests:** Player-based filtering, mode isolation, edge cases

### Step 3: Dashboard Metrics & Mode Toggle
**Files:** src/sockets/dashboard.py

**Tasks:**
1. Add toggle_game_mode socket event (no pause validation needed)
2. Create compute_success_metrics() function implementing success rules
3. Modify correlation matrix calculations for new mode display
4. Update _process_single_team() for conditional metrics based on mode
5. Add normalized score calculation (score/total_rounds)
6. Ensure metrics recalculate immediately when mode changes
7. Optimize performance: only calculate metrics for active mode (skip physics calculations in new mode, skip success calculations in classic mode)

**Tests:** Mode toggle functionality, success rule calculations, correlation matrix updates, metric display

### Step 4: Player UI & Integration Testing
**Files:** src/static/app.js, src/static/index.html, all modified files

**Tasks:**
1. Add player position display to game interface (Player 1/Player 2)
2. Conditionally show position info based on game mode (more relevant in new mode)
3. Update game interface to show current mode to players
4. Complete test suite validation
5. End-to-end workflow testing including UI updates
6. Edge case handling for reactivated teams
7. Integration test updates

---

## Dashboard Updates

### Correlation Matrix Changes
- **Classic Mode**: Current correlation calculations for CHSH physics
- **New Mode**: Success rate calculations per question combination
- **Structure**: Same data format, different values and labels
- **Display**: Frontend conditionally shows "Correlation" vs "Success Rate" labels

### Metric Replacements
- Replace trace_average_statistic with overall_success_rate
- Replace chsh_value_statistic with normalized_cumulative_score
- Maintain correlation_stats dict structure for frontend compatibility

---

## Key Implementation Details

### Critical File Locations
1. **State Management (src/state.py):** AppState.__init__() and reset() method
2. **Question Logic (src/game_logic.py):** start_new_round_for_pair() line ~13
3. **Dashboard Metrics (src/sockets/dashboard.py):** _process_single_team() line ~419, compute_correlation_matrix() line ~100
4. **Player UI (src/static/):** Add player position display to game interface
5. **Team Management:** No changes needed - existing logic handles player positions

### Success Rule Logic
- {B,Y} or {Y,B} combination: Players must answer differently
- All other combinations: Players must answer the same
- Score calculation: (+1 success, -1 failure) / total_rounds

### Testing Strategy
- Parameterized tests for mode-specific behavior
- Mock state.game_mode in existing fixtures
- Leverage existing test patterns from test_physics_calculations.py
- Test edge cases: mode switching mid-game, empty teams, single-player teams
- Test performance: verify conditional calculation actually skips unused metrics
- Ensure all existing tests pass unchanged in classic mode

---

## Expected Outcomes

**Success Criteria:**
- All existing functionality works unchanged in classic mode
- New mode implements player-based question restrictions correctly
- Success metrics calculate according to specified rules with normalization
- Mode toggle works seamlessly without data loss
- Dashboard displays appropriate metrics based on mode  
- All previous responses remain useful across mode changes
- Complete test suite passes with new functionality

**Performance:** Leverages existing caching mechanisms, conditional metric calculation saves significant CPU (skips complex physics calculations in new mode, skips success calculations in classic mode)
**Compatibility:** Zero breaking changes for classic mode operation
**Maintainability:** Follows existing code patterns and architectural decisions 