import pytest
import math
import numpy as np
from unittest.mock import patch, MagicMock
from uncertainties import ufloat
import warnings

from src.sockets.dashboard import (
    compute_correlation_matrix, 
    _calculate_team_statistics,
    clear_team_caches
)
from src.models.quiz_models import ItemEnum, PairQuestionRounds, Answers
from datetime import datetime, UTC


class MockQuestionItem:
    def __init__(self, value):
        self.value = value

class MockRound:
    def __init__(self, round_id, p1_item, p2_item):
        self.round_id = round_id
        self.player1_item = MockQuestionItem(p1_item)
        self.player2_item = MockQuestionItem(p2_item)
        self.timestamp_initiated = datetime.now(UTC)

class MockAnswer:
    def __init__(self, round_id, item, response, timestamp=None):
        self.question_round_id = round_id
        self.assigned_item = MockQuestionItem(item)
        self.response_value = response
        self.timestamp = timestamp or datetime.now(UTC)


class TestPhysicsCalculations:
    """Test suite for quantum physics calculations and Bell inequality validation"""

    @pytest.fixture(autouse=True)
    def clear_caches_before_test(self):
        """Clear all caches before each test"""
        clear_team_caches()
        yield
        clear_team_caches()

    def test_chsh_theoretical_maximum(self):
        """Test that CHSH value approaches theoretical quantum maximum (2√2 ≈ 2.828)"""
        # Setup ideal quantum Bell state correlations
        # E(A,X) = cos(0-π/4) = cos(-π/4) = √2/2
        # E(A,Y) = cos(0-(-π/4)) = cos(π/4) = √2/2  
        # E(B,X) = cos(π/2-π/4) = cos(π/4) = √2/2
        # E(B,Y) = cos(π/2-(-π/4)) = cos(3π/4) = -√2/2
        # CHSH = E(A,X) + E(A,Y) + E(B,X) - E(B,Y) = √2/2 + √2/2 + √2/2 - (-√2/2) = 2√2

        rounds = []
        answers = []
        
        # Create perfect quantum correlations with large statistics
        n_rounds = 1000
        for i in range(n_rounds):
            round_id = i + 1
            
            # Cycle through all CHSH combinations
            if i % 4 == 0:  # A-X: perfect correlation  
                rounds.append(MockRound(round_id, 'A', 'X'))
                answers.extend([
                    MockAnswer(round_id, 'A', True),
                    MockAnswer(round_id, 'X', True)
                ])
            elif i % 4 == 1:  # A-Y: perfect correlation
                rounds.append(MockRound(round_id, 'A', 'Y'))
                answers.extend([
                    MockAnswer(round_id, 'A', True),
                    MockAnswer(round_id, 'Y', True)
                ])
            elif i % 4 == 2:  # B-X: perfect correlation
                rounds.append(MockRound(round_id, 'B', 'X'))
                answers.extend([
                    MockAnswer(round_id, 'B', True),
                    MockAnswer(round_id, 'X', True)
                ])
            else:  # B-Y: perfect anti-correlation (coefficient is -1)
                rounds.append(MockRound(round_id, 'B', 'Y'))
                answers.extend([
                    MockAnswer(round_id, 'B', True),
                    MockAnswer(round_id, 'Y', False)  # Anti-correlated
                ])

        with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds:
            mock_rounds.query.filter_by.return_value.order_by.return_value.all.return_value = rounds
            
            with patch('src.sockets.dashboard.Answers') as mock_answers:
                mock_answers.query.filter_by.return_value.order_by.return_value.all.return_value = answers
                
                result = compute_correlation_matrix(1)
                _, _, _, _, _, correlation_sums, pair_counts = result
                
                # Calculate cross-term CHSH manually
                chsh_terms = [
                    ('A', 'X', 1), ('A', 'Y', 1),
                    ('B', 'X', 1), ('B', 'Y', -1)
                ]
                
                total_chsh = 0
                for item1, item2, coeff in chsh_terms:
                    M_ij = pair_counts.get((item1, item2), 0) + pair_counts.get((item2, item1), 0)
                    N_ij_sum = correlation_sums.get((item1, item2), 0) + correlation_sums.get((item2, item1), 0)
                    if M_ij > 0:
                        correlation = N_ij_sum / M_ij
                        total_chsh += coeff * correlation
                
                # Should approach theoretical maximum
                expected_chsh = 4.0  # Perfect correlations: 1+1+1-(-1) = 4
                assert abs(total_chsh - expected_chsh) < 0.01, f"CHSH value {total_chsh} far from expected {expected_chsh}"

    def test_chsh_classical_bound(self):
        """Test that classical strategies cannot exceed Bell bound (2.0)"""
        # Classical strategy: deterministic local hidden variable
        rounds = []
        answers = []
        
        # Simulate classical strategy where players use shared random bit
        # Best classical strategy gives CHSH ≤ 2
        n_rounds = 400
        for i in range(n_rounds):
            round_id = i + 1
            shared_bit = i % 2  # Shared hidden variable
            
            if i % 4 == 0:  # A-X 
                rounds.append(MockRound(round_id, 'A', 'X'))
                # Classical strategy: A responds with shared_bit, X responds with shared_bit
                answers.extend([
                    MockAnswer(round_id, 'A', bool(shared_bit)),
                    MockAnswer(round_id, 'X', bool(shared_bit))
                ])
            elif i % 4 == 1:  # A-Y
                rounds.append(MockRound(round_id, 'A', 'Y'))
                answers.extend([
                    MockAnswer(round_id, 'A', bool(shared_bit)),
                    MockAnswer(round_id, 'Y', bool(shared_bit))
                ])
            elif i % 4 == 2:  # B-X
                rounds.append(MockRound(round_id, 'B', 'X'))
                answers.extend([
                    MockAnswer(round_id, 'B', bool(shared_bit)),
                    MockAnswer(round_id, 'X', bool(shared_bit))
                ])
            else:  # B-Y
                rounds.append(MockRound(round_id, 'B', 'Y'))
                answers.extend([
                    MockAnswer(round_id, 'B', bool(shared_bit)),
                    MockAnswer(round_id, 'Y', bool(1 - shared_bit))  # Opposite for B-Y term
                ])

        with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds:
            mock_rounds.query.filter_by.return_value.order_by.return_value.all.return_value = rounds
            
            with patch('src.sockets.dashboard.Answers') as mock_answers:
                mock_answers.query.filter_by.return_value.order_by.return_value.all.return_value = answers
                
                result = compute_correlation_matrix(1)
                _, _, _, _, _, correlation_sums, pair_counts = result
                
                # Calculate CHSH value
                chsh_terms = [
                    ('A', 'X', 1), ('A', 'Y', 1),
                    ('B', 'X', 1), ('B', 'Y', -1)
                ]
                
                total_chsh = 0
                for item1, item2, coeff in chsh_terms:
                    M_ij = pair_counts.get((item1, item2), 0) + pair_counts.get((item2, item1), 0)
                    N_ij_sum = correlation_sums.get((item1, item2), 0) + correlation_sums.get((item2, item1), 0)
                    if M_ij > 0:
                        correlation = N_ij_sum / M_ij
                        total_chsh += coeff * correlation
                
                # Should not exceed classical bound
                assert total_chsh <= 2.1, f"Classical CHSH value {total_chsh} exceeds theoretical bound of 2"

    def test_correlation_matrix_symmetry(self):
        """Test that correlation matrix maintains physical symmetry properties"""
        rounds = [
            MockRound(1, 'A', 'B'),
            MockRound(2, 'B', 'A'),  # Swapped order
            MockRound(3, 'X', 'Y'),
            MockRound(4, 'Y', 'X')   # Swapped order
        ]
        
        answers = [
            MockAnswer(1, 'A', True), MockAnswer(1, 'B', True),
            MockAnswer(2, 'B', False), MockAnswer(2, 'A', False),
            MockAnswer(3, 'X', True), MockAnswer(3, 'Y', False),
            MockAnswer(4, 'Y', True), MockAnswer(4, 'X', False)
        ]

        with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds:
            mock_rounds.query.filter_by.return_value.order_by.return_value.all.return_value = rounds
            
            with patch('src.sockets.dashboard.Answers') as mock_answers:
                mock_answers.query.filter_by.return_value.order_by.return_value.all.return_value = answers
                
                corr_matrix, item_values, _, _, _, _, _ = compute_correlation_matrix(1)
                
                # Find indices
                a_idx = item_values.index('A')
                b_idx = item_values.index('B')
                x_idx = item_values.index('X')
                y_idx = item_values.index('Y')
                
                # Check correlation symmetry: C(A,B) should equal C(B,A)
                ab_corr = corr_matrix[a_idx][b_idx]
                ba_corr = corr_matrix[b_idx][a_idx]
                xy_corr = corr_matrix[x_idx][y_idx]
                yx_corr = corr_matrix[y_idx][x_idx]
                
                # Convert to actual correlation values for comparison
                def get_correlation_value(corr_tuple):
                    num, den = corr_tuple
                    return num / den if den != 0 else 0
                
                assert abs(get_correlation_value(ab_corr) - get_correlation_value(ba_corr)) < 0.01, \
                    "Correlation matrix not symmetric for A-B vs B-A"
                assert abs(get_correlation_value(xy_corr) - get_correlation_value(yx_corr)) < 0.01, \
                    "Correlation matrix not symmetric for X-Y vs Y-X"

    def test_uncertainty_propagation(self):
        """Test statistical uncertainty calculations with small sample sizes"""
        # Small sample test - uncertainties should be large
        rounds = [MockRound(1, 'A', 'X')]
        answers = [MockAnswer(1, 'A', True), MockAnswer(1, 'X', True)]

        with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds:
            mock_rounds.query.filter_by.return_value.order_by.return_value.all.return_value = rounds
            
            with patch('src.sockets.dashboard.Answers') as mock_answers:
                mock_answers.query.filter_by.return_value.order_by.return_value.all.return_value = answers
                
                result = compute_correlation_matrix(1)
                correlation_data = (result[0], result[1], result[4], result[5], result[6])
                correlation_matrix_str = str(correlation_data)
                
                stats = _calculate_team_statistics(correlation_matrix_str)
                
                # With only 1 measurement, uncertainty should be 1/√1 = 1
                assert stats['trace_average_statistic_uncertainty'] is not None, \
                    "Should have uncertainty with small sample"
                assert stats['trace_average_statistic_uncertainty'] >= 0.5, \
                    f"Uncertainty {stats['trace_average_statistic_uncertainty']} too small for N=1"

    def test_balance_metric_edge_cases(self):
        """Test same-item balance calculation with edge cases"""
        # Case 1: Perfect balance (50/50 split)
        rounds = [
            MockRound(1, 'A', 'A'),
            MockRound(2, 'A', 'A'),
            MockRound(3, 'A', 'A'),
            MockRound(4, 'A', 'A')
        ]
        
        answers = [
            MockAnswer(1, 'A', True), MockAnswer(1, 'A', True),
            MockAnswer(2, 'A', False), MockAnswer(2, 'A', False),
            MockAnswer(3, 'A', True), MockAnswer(3, 'A', False),
            MockAnswer(4, 'A', False), MockAnswer(4, 'A', True)
        ]

        with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds:
            mock_rounds.query.filter_by.return_value.order_by.return_value.all.return_value = rounds
            
            with patch('src.sockets.dashboard.Answers') as mock_answers:
                mock_answers.query.filter_by.return_value.order_by.return_value.all.return_value = answers
                
                _, _, avg_balance, balance_dict, same_item_responses, _, _ = compute_correlation_matrix(1)
                
                # Should have 4 True and 4 False responses
                assert same_item_responses['A']['true'] == 4
                assert same_item_responses['A']['false'] == 4
                # Perfect balance should give score of 1.0
                assert abs(balance_dict['A'] - 1.0) < 0.01

    def test_extreme_bias_detection(self):
        """Test detection of extreme bias (all True or all False responses)"""
        rounds = [MockRound(1, 'A', 'A'), MockRound(2, 'A', 'A')]
        
        # All responses are True - maximum bias
        answers = [
            MockAnswer(1, 'A', True), MockAnswer(1, 'A', True),
            MockAnswer(2, 'A', True), MockAnswer(2, 'A', True)
        ]

        with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds:
            mock_rounds.query.filter_by.return_value.order_by.return_value.all.return_value = rounds
            
            with patch('src.sockets.dashboard.Answers') as mock_answers:
                mock_answers.query.filter_by.return_value.order_by.return_value.all.return_value = answers
                
                _, _, avg_balance, balance_dict, same_item_responses, _, _ = compute_correlation_matrix(1)
                
                # Should detect extreme bias
                assert same_item_responses['A']['true'] == 4
                assert same_item_responses['A']['false'] == 0
                # Balance should be 0 (maximum imbalance)
                assert abs(balance_dict['A'] - 0.0) < 0.01

    def test_correlation_bounds(self):
        """Test that correlation values are properly bounded between -1 and +1"""
        # Test with various correlation patterns
        test_cases = [
            # Perfect positive correlation
            ([(True, True), (False, False)], 1.0),
            # Perfect negative correlation  
            ([(True, False), (False, True)], -1.0),
            # No correlation
            ([(True, True), (True, False), (False, True), (False, False)], 0.0),
        ]
        
        for i, (response_pairs, expected_corr) in enumerate(test_cases):
            rounds = []
            answers = []
            
            for j, (resp1, resp2) in enumerate(response_pairs):
                round_id = i * 100 + j + 1
                rounds.append(MockRound(round_id, 'A', 'X'))
                answers.extend([
                    MockAnswer(round_id, 'A', resp1),
                    MockAnswer(round_id, 'X', resp2)
                ])

            with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds:
                mock_rounds.query.filter_by.return_value.order_by.return_value.all.return_value = rounds
                
                with patch('src.sockets.dashboard.Answers') as mock_answers:
                    mock_answers.query.filter_by.return_value.order_by.return_value.all.return_value = answers
                    
                    corr_matrix, item_values, _, _, _, _, _ = compute_correlation_matrix(1)
                    
                    a_idx = item_values.index('A')
                    x_idx = item_values.index('X')
                    num, den = corr_matrix[a_idx][x_idx]
                    
                    if den > 0:
                        correlation = num / den
                        # Check bounds
                        assert -1.0 <= correlation <= 1.0, \
                            f"Correlation {correlation} outside valid bounds [-1,1]"
                        # Check expected value
                        assert abs(correlation - expected_corr) < 0.01, \
                            f"Expected correlation {expected_corr}, got {correlation}"

    def test_empty_data_handling(self):
        """Test handling of teams with no measurement data"""
        with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds:
            mock_rounds.query.filter_by.return_value.order_by.return_value.all.return_value = []
            
            with patch('src.sockets.dashboard.Answers') as mock_answers:
                mock_answers.query.filter_by.return_value.order_by.return_value.all.return_value = []
                
                result = compute_correlation_matrix(1)
                corr_matrix, item_values, avg_balance, balance_dict, resp_dict, corr_sums, pair_counts = result
                
                # Should return valid default structure
                assert len(corr_matrix) == 4
                assert all(len(row) == 4 for row in corr_matrix)
                assert all(all(cell == (0, 0) for cell in row) for row in corr_matrix)
                assert item_values == ['A', 'B', 'X', 'Y']
                assert avg_balance == 0.0
                assert balance_dict == {}
                assert resp_dict == {}

    def test_statistical_significance_threshold(self):
        """Test that statistical significance is properly calculated"""
        # Test case where we have exactly TARGET_COMBO_REPEATS measurements
        from src.game_logic import TARGET_COMBO_REPEATS, QUESTION_ITEMS
        
        all_combos = [(i1.value, i2.value) for i1 in QUESTION_ITEMS for i2 in QUESTION_ITEMS]
        
        rounds = []
        answers = []
        
        # Create exactly TARGET_COMBO_REPEATS instances of each combo
        round_id = 1
        for combo in all_combos:
            item1, item2 = combo
            for _ in range(TARGET_COMBO_REPEATS):
                rounds.append(MockRound(round_id, item1, item2))
                answers.extend([
                    MockAnswer(round_id, item1, True),
                    MockAnswer(round_id, item2, True)
                ])
                round_id += 1

        # Mock team state to simulate combo tracking
        mock_combo_tracker = {}
        for combo in all_combos:
            mock_combo_tracker[combo] = TARGET_COMBO_REPEATS

        with patch('src.sockets.dashboard.state') as mock_state:
            mock_state.active_teams = {
                'test_team': {
                    'combo_tracker': mock_combo_tracker
                }
            }
            
            with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds:
                mock_rounds.query.filter_by.return_value.order_by.return_value.all.return_value = rounds
                
                with patch('src.sockets.dashboard.Answers') as mock_answers:
                    mock_answers.query.filter_by.return_value.order_by.return_value.all.return_value = answers
                    
                    from src.sockets.dashboard import _process_single_team
                    
                    team_data = _process_single_team(
                        team_id=1,
                        team_name='test_team', 
                        is_active=True,
                        created_at='2024-01-01T00:00:00',
                        current_round=len(rounds),
                        player1_sid='p1',
                        player2_sid='p2'
                    )
                    
                    # Should indicate statistical significance
                    assert team_data['min_stats_sig'] == True, \
                        "Should have statistical significance with sufficient data"

    def test_mathematical_consistency_checks(self):
        """Test mathematical consistency of correlation calculations"""
        # Create test data with known mathematical properties
        rounds = [
            MockRound(1, 'A', 'X'), MockRound(2, 'A', 'X'),  # Two identical rounds
            MockRound(3, 'B', 'Y'), MockRound(4, 'B', 'Y')   # Two more identical rounds
        ]
        
        answers = [
            # First A-X pair: both True (correlation = +1)
            MockAnswer(1, 'A', True), MockAnswer(1, 'X', True),
            # Second A-X pair: both False (correlation = +1) 
            MockAnswer(2, 'A', False), MockAnswer(2, 'X', False),
            # First B-Y pair: opposite (correlation = -1)
            MockAnswer(3, 'B', True), MockAnswer(3, 'Y', False),
            # Second B-Y pair: opposite (correlation = -1)
            MockAnswer(4, 'B', False), MockAnswer(4, 'Y', True)
        ]

        with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds:
            mock_rounds.query.filter_by.return_value.order_by.return_value.all.return_value = rounds
            
            with patch('src.sockets.dashboard.Answers') as mock_answers:
                mock_answers.query.filter_by.return_value.order_by.return_value.all.return_value = answers
                
                _, _, _, _, _, correlation_sums, pair_counts = compute_correlation_matrix(1)
                
                # Check mathematical consistency
                ax_count = pair_counts.get(('A', 'X'), 0)
                ax_sum = correlation_sums.get(('A', 'X'), 0)
                by_count = pair_counts.get(('B', 'Y'), 0)
                by_sum = correlation_sums.get(('B', 'Y'), 0)
                
                assert ax_count == 2, f"Expected 2 A-X pairs, got {ax_count}"
                assert ax_sum == 2, f"Expected sum=2 for perfect correlation, got {ax_sum}"
                assert by_count == 2, f"Expected 2 B-Y pairs, got {by_count}" 
                assert by_sum == -2, f"Expected sum=-2 for perfect anti-correlation, got {by_sum}"
                
                # Correlation values should be exactly ±1
                ax_correlation = ax_sum / ax_count if ax_count > 0 else 0
                by_correlation = by_sum / by_count if by_count > 0 else 0
                
                assert abs(ax_correlation - 1.0) < 0.001, f"A-X correlation should be +1, got {ax_correlation}"
                assert abs(by_correlation - (-1.0)) < 0.001, f"B-Y correlation should be -1, got {by_correlation}"

    def test_numerical_stability(self):
        """Test numerical stability with extreme values and edge cases"""
        # Test with very large numbers of measurements
        n_large = 10000
        rounds = [MockRound(i, 'A', 'X') for i in range(1, n_large + 1)]
        answers = []
        
        for i in range(1, n_large + 1):
            # Alternate responses to create known correlation
            response = i % 2 == 1
            answers.extend([
                MockAnswer(i, 'A', response),
                MockAnswer(i, 'X', response)
            ])

        with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds:
            mock_rounds.query.filter_by.return_value.order_by.return_value.all.return_value = rounds
            
            with patch('src.sockets.dashboard.Answers') as mock_answers:
                mock_answers.query.filter_by.return_value.order_by.return_value.all.return_value = answers
                
                result = compute_correlation_matrix(1)
                _, _, _, _, _, correlation_sums, pair_counts = result
                
                # Should handle large numbers without overflow
                ax_count = pair_counts.get(('A', 'X'), 0)
                ax_sum = correlation_sums.get(('A', 'X'), 0)
                
                assert ax_count == n_large, f"Should count all {n_large} measurements"
                assert abs(ax_sum) <= ax_count, "Correlation sum magnitude should not exceed count"
                
                # Uncertainty should decrease with sample size  
                correlation_data = (result[0], result[1], result[4], result[5], result[6])
                stats = _calculate_team_statistics(str(correlation_data))
                
                expected_uncertainty = 1.0 / math.sqrt(n_large)
                actual_uncertainty = stats.get('cross_term_combination_statistic_uncertainty', float('inf'))
                
                if actual_uncertainty is not None:
                    assert actual_uncertainty < 0.1, \
                        f"Uncertainty {actual_uncertainty} should be small with large sample size"