# Correlation Calculation Improvements

## Overview

The CHSH game scoring logic has been encapsulated in the new `calculate_score` function in `src/game_logic.py`. We should utilize this function in the dashboard's correlation calculations to ensure consistent scoring across the application.

## Current Implementation

The dashboard's correlation calculation (in `src/sockets/dashboard.py`) currently uses a simple matching comparison:

```python
# Current correlation calculation (line 154 in dashboard.py)
correlation = 1 if p1_answer == p2_answer else -1
```

This doesn't properly account for the CHSH game rules where:
- For player1 with item A: answers should match for success
- For player1 with item B and player2 with X: answers should match
- For player1 with item B and player2 with Y: answers should differ

## Proposed Changes

1. Import `calculate_score` in `src/sockets/dashboard.py`:
```python
from src.game_logic import calculate_score, QUESTION_ITEMS, TARGET_COMBO_REPEATS
```

2. Replace the correlation calculation in `compute_correlation_matrix` function:

```python
# Replace the simple correlation calculation with calculate_score
correlation = 2 * calculate_score(
    player1_item=round_obj.player1_item,
    player2_item=round_obj.player2_item,
    player1_answer=p1_answer,
    player2_answer=p2_answer
) - 1
```

Note: We multiply by 2 and subtract 1 to convert from [0,1] to [-1,1] range for correlation values.

## Benefits

1. **Consistency**: Scoring logic will be consistent across the application
2. **Correctness**: Correlations will properly reflect the CHSH game rules
3. **Maintainability**: Single source of truth for scoring logic
4. **Accuracy**: Statistics shown in the dashboard will better reflect actual game performance

## Implementation Plan

1. Switch to Code mode to make the changes to `src/sockets/dashboard.py`
2. Update the correlation calculation in `compute_correlation_matrix`
3. Add tests to verify the correlation calculation matches game rules
4. Test the changes thoroughly with the dashboard UI
5. Monitor performance to ensure the changes don't impact dashboard responsiveness

## Migration Strategy

Since this is a logic change that doesn't affect data structure or API contracts, it can be deployed without any special migration steps. However, we should:

1. Deploy during low-usage period
2. Monitor correlation statistics for any unexpected changes
3. Have a rollback plan ready if issues are detected

## Unit Tests

Add the following test cases to `tests/unit/test_dashboard_sockets.py`:

### Test Correlation Matrix Calculation

```python
def test_compute_correlation_matrix_scoring():
    """Test that correlation matrix uses calculate_score correctly"""
    # Setup: Create mock team with rounds and answers
    team = Teams(team_name="test_team")
    db.session.add(team)
    db.session.commit()

    # Test cases to verify correlation values match CHSH game rules
    test_cases = [
        # For A, answers should match
        (ItemEnum.A, ItemEnum.X, True, True, 1),   # Same answers = positive correlation
        (ItemEnum.A, ItemEnum.Y, False, False, 1), # Same answers = positive correlation
        (ItemEnum.A, ItemEnum.X, True, False, -1), # Different answers = negative correlation
        
        # For B and X, answers should match
        (ItemEnum.B, ItemEnum.X, True, True, 1),
        (ItemEnum.B, ItemEnum.X, False, False, 1),
        (ItemEnum.B, ItemEnum.X, True, False, -1),
        
        # For B and Y, answers should differ
        (ItemEnum.B, ItemEnum.Y, True, False, 1),  # Different answers = positive correlation
        (ItemEnum.B, ItemEnum.Y, False, True, 1),  # Different answers = positive correlation
        (ItemEnum.B, ItemEnum.Y, True, True, -1)   # Same answers = negative correlation
    ]

    # Create test rounds and answers
    for p1_item, p2_item, p1_ans, p2_ans, expected_corr in test_cases:
        # Create round
        round = PairQuestionRounds(
            team_id=team.team_id,
            round_number_for_team=1,
            player1_item=p1_item,
            player2_item=p2_item
        )
        db.session.add(round)
        db.session.commit()
        
        # Add player answers
        ans1 = Answers(
            team_id=team.team_id,
            player_session_id="p1",
            question_round_id=round.round_id,
            assigned_item=p1_item,
            response_value=p1_ans
        )
        ans2 = Answers(
            team_id=team.team_id,
            player_session_id="p2",
            question_round_id=round.round_id,
            assigned_item=p2_item,
            response_value=p2_ans
        )
        db.session.add_all([ans1, ans2])
        db.session.commit()

    # Call compute_correlation_matrix
    corr_matrix, item_values, *_ = compute_correlation_matrix(team.team_id)
    
    # Verify correlations match expected values
    for p1_item, p2_item, _, _, expected_corr in test_cases:
        p1_idx = item_values.index(p1_item.value)
        p2_idx = item_values.index(p2_item.value)
        num, den = corr_matrix[p1_idx][p2_idx]
        assert den > 0, f"No data for {p1_item.value}-{p2_item.value}"
        actual_corr = num/den
        assert abs(actual_corr - expected_corr) < 1e-10, \
            f"Wrong correlation for {p1_item.value}-{p2_item.value}"
```

### Test Edge Cases

```python
def test_compute_correlation_matrix_validation():
    """Test input validation and edge cases in correlation matrix computation"""
    # Test with nonexistent team
    corr_matrix, item_values, *_ = compute_correlation_matrix(999)
    assert all(all(num == 0 and den == 0 for num, den in row) for row in corr_matrix)
    
    # Test with team but no rounds
    team = Teams(team_name="empty_team")
    db.session.add(team)
    db.session.commit()
    corr_matrix, item_values, *_ = compute_correlation_matrix(team.team_id)
    assert all(all(num == 0 and den == 0 for num, den in row) for row in corr_matrix)
    
    # Test with rounds but no answers
    round = PairQuestionRounds(
        team_id=team.team_id,
        round_number_for_team=1,
        player1_item=ItemEnum.A,
        player2_item=ItemEnum.X
    )
    db.session.add(round)
    db.session.commit()
    corr_matrix, item_values, *_ = compute_correlation_matrix(team.team_id)
    assert all(all(num == 0 and den == 0 for num, den in row) for row in corr_matrix)
```

### Test Same Item Assignment

```python
def test_compute_correlation_matrix_same_items():
    """Test correlation calculation when both players get the same item"""
    team = Teams(team_name="same_item_team")
    db.session.add(team)
    db.session.commit()
    
    # Create round where both players get item A
    round = PairQuestionRounds(
        team_id=team.team_id,
        round_number_for_team=1,
        player1_item=ItemEnum.A,
        player2_item=ItemEnum.A
    )
    db.session.add(round)
    db.session.commit()
    
    # Add matching answers
    ans1 = Answers(
        team_id=team.team_id,
        player_session_id="p1",
        question_round_id=round.round_id,
        assigned_item=ItemEnum.A,
        response_value=True
    )
    ans2 = Answers(
        team_id=team.team_id,
        player_session_id="p2",
        question_round_id=round.round_id,
        assigned_item=ItemEnum.A,
        response_value=True
    )
    db.session.add_all([ans1, ans2])
    db.session.commit()
    
    # Verify correlation and same-item balance metrics
    corr_matrix, item_values, avg_balance, same_item_balance, *_ = compute_correlation_matrix(team.team_id)
    
    # Check same-item balance
    assert 'A' in same_item_balance
    assert abs(same_item_balance['A'] - 0.0) < 1e-10  # Both answers True = 0 balance
    
    # Check average balance
    assert abs(avg_balance - 0.0) < 1e-10
```

### Test Coverage

These tests verify:
1. Correlation calculations properly use calculate_score for all valid item combinations
2. Edge cases (nonexistent team, no rounds, no answers) are handled gracefully
3. Special case of same items assigned to both players works correctly
4. Correlation matrix dimensions and values are correct
5. Same-item balance metrics are calculated correctly

### Dependencies

The tests require:
1. Access to database through pytest fixtures
2. Mock objects for Teams, PairQuestionRounds, and Answers tables
3. The calculate_score function from game_logic.py

## Next Steps

1. Add the new unit tests to test_dashboard_sockets.py
2. Use the switch_mode tool to transition to Code mode for implementation:

```
<switch_mode>
<mode_slug>code</mode_slug>
<reason>Implement correlation calculation improvements and corresponding unit tests</reason>
</switch_mode>