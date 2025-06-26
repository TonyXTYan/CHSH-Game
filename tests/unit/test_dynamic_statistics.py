"""
Test dynamic statistics functionality for dashboard mode switching.
"""
import pytest
from unittest.mock import patch, MagicMock
from src.sockets.dashboard import _process_single_team, _calculate_team_statistics, _calculate_success_statistics
from src.models.quiz_models import ItemEnum
from src.game_logic import QUESTION_ITEMS, TARGET_COMBO_REPEATS


class TestDynamicStatistics:
    """Test dynamic statistics functionality for mode switching."""

    @pytest.fixture
    def mock_state(self):
        """Mock state with different game modes."""
        with patch('src.sockets.dashboard.state') as mock_state:
            mock_state.active_teams = {}
            mock_state.game_mode = 'classic'  # Default value
            yield mock_state

    @pytest.fixture(autouse=True)
    def clear_caches(self):
        """Clear LRU caches before each test."""
        from src.sockets.dashboard import _process_single_team, _calculate_team_statistics, _calculate_success_statistics
        _process_single_team.cache_clear()
        _calculate_team_statistics.cache_clear()
        _calculate_success_statistics.cache_clear()
        yield

    @pytest.fixture
    def mock_compute_functions(self):
        """Mock the computation functions."""
        with patch('src.sockets.dashboard.compute_team_hashes') as mock_hashes, \
             patch('src.sockets.dashboard.compute_correlation_matrix') as mock_corr, \
             patch('src.sockets.dashboard.compute_success_metrics') as mock_success, \
             patch('src.sockets.dashboard.ItemEnum') as mock_item_enum, \
             patch('src.sockets.dashboard.QUESTION_ITEMS') as mock_question_items, \
             patch('src.sockets.dashboard.TARGET_COMBO_REPEATS', 3):
            
            # Mock ItemEnum
            mock_item_enum.A = ItemEnum.A
            mock_item_enum.B = ItemEnum.B
            mock_item_enum.X = ItemEnum.X
            mock_item_enum.Y = ItemEnum.Y
            
            # Mock QUESTION_ITEMS
            mock_question_items.__iter__ = lambda x: iter([ItemEnum.A, ItemEnum.B, ItemEnum.X, ItemEnum.Y])
            
            # Mock correlation matrix result
            mock_corr.return_value = (
                [[(1, 10), (2, 10), (3, 10), (4, 10)] for _ in range(4)],  # corr_matrix_tuples
                ['A', 'B', 'X', 'Y'],  # item_values
                0.8,  # same_item_balance_avg
                {'A': 0.8, 'B': 0.7},  # same_item_balance
                {'A': {'true': 8, 'false': 2}},  # same_item_responses
                {('A', 'B'): 5},  # correlation_sums
                {('A', 'B'): 10}  # pair_counts
            )
            
            # Mock success metrics result
            mock_success.return_value = (
                [[(8, 10), (7, 10), (6, 10), (5, 10)] for _ in range(4)],  # success_matrix_tuples
                ['A', 'B', 'X', 'Y'],  # success_item_values
                0.75,  # overall_success_rate
                0.5,   # normalized_cumulative_score
                {('A', 'B'): 8},  # success_counts
                {('A', 'B'): 10}, # success_pair_counts
                {'A': {'true': 8, 'false': 2}, 'B': {'true': 5, 'false': 5}, 'X': {'true': 7, 'false': 3}, 'Y': {'true': 6, 'false': 4}}  # player_responses
            )
            
            mock_hashes.return_value = ('hash1', 'hash2')
            
            yield mock_hashes, mock_corr, mock_success

    def test_classic_mode_team_processing(self, mock_state, mock_compute_functions):
        """Test that classic mode returns appropriate data structure."""
        mock_state.game_mode = 'classic'
        
        with patch('src.sockets.dashboard._calculate_team_statistics') as mock_calc_classic, \
             patch('src.sockets.dashboard._calculate_success_statistics') as mock_calc_success:
            
            mock_calc_classic.return_value = {
                'trace_average_statistic': 0.6,
                'trace_average_statistic_uncertainty': 0.1,
                'same_item_balance': 0.8,
                'same_item_balance_uncertainty': 0.05,
                'cross_term_combination_statistic': 2.5,
                'cross_term_combination_statistic_uncertainty': 0.2
            }
            
            mock_calc_success.return_value = {
                'trace_average_statistic': 0.75,
                'trace_average_statistic_uncertainty': 0.08,
                'chsh_value_statistic': 0.5,
                'chsh_value_statistic_uncertainty': 0.1,
                'same_item_balance': 0.7,
                'same_item_balance_uncertainty': 0.06
            }
            
            result = _process_single_team(1, 'TestTeam', True, '2023-01-01', 5, 'p1', 'p2')
            
            assert result is not None
            assert result['game_mode'] == 'classic'
            
            # Should have both classic and new stats
            assert 'classic_stats' in result
            assert 'new_stats' in result
            assert 'classic_matrix' in result
            assert 'new_matrix' in result
            
            # Display should use classic stats (correlation_stats points to classic)
            assert result['correlation_stats'] == mock_calc_classic.return_value
            
            # Verify both stats are included
            assert result['classic_stats']['trace_average_statistic'] == 0.6
            assert result['new_stats']['trace_average_statistic'] == 0.75

    def test_new_mode_team_processing(self, mock_state, mock_compute_functions):
        """Test that new mode returns appropriate data structure."""
        mock_state.game_mode = 'new'
        
        with patch('src.sockets.dashboard._calculate_team_statistics') as mock_calc_classic, \
             patch('src.sockets.dashboard._calculate_success_statistics') as mock_calc_success:
            
            mock_calc_classic.return_value = {
                'trace_average_statistic': 0.6,
                'trace_average_statistic_uncertainty': 0.1,
                'same_item_balance': 0.8,
                'same_item_balance_uncertainty': 0.05,
                'cross_term_combination_statistic': 2.5,
                'cross_term_combination_statistic_uncertainty': 0.2
            }
            
            mock_calc_success.return_value = {
                'trace_average_statistic': 0.75,
                'trace_average_statistic_uncertainty': 0.08,
                'chsh_value_statistic': 0.5,
                'chsh_value_statistic_uncertainty': 0.1,
                'same_item_balance': 0.7,
                'same_item_balance_uncertainty': 0.06
            }
            
            result = _process_single_team(1, 'TestTeam', True, '2023-01-01', 5, 'p1', 'p2')
            
            assert result is not None
            assert result['game_mode'] == 'new'
            
            # Should have both classic and new stats
            assert 'classic_stats' in result
            assert 'new_stats' in result
            assert 'classic_matrix' in result
            assert 'new_matrix' in result
            
            # Display should use new stats (correlation_stats points to new)
            assert result['correlation_stats'] == mock_calc_success.return_value
            
            # Verify both stats are included
            assert result['classic_stats']['trace_average_statistic'] == 0.6
            assert result['new_stats']['trace_average_statistic'] == 0.75

    def test_success_statistics_calculation(self):
        """Test that success statistics are calculated correctly."""
        # Mock success data
        success_data = (
            [[(8, 10), (7, 10), (6, 10), (5, 10)] for _ in range(4)],  # success_matrix_tuples
            ['A', 'B', 'X', 'Y'],  # item_values
            0.75,  # overall_success_rate
            0.5,   # normalized_cumulative_score
            {('A', 'B'): 8, ('A', 'X'): 6},  # success_counts
            {('A', 'B'): 10, ('A', 'X'): 10}, # pair_counts
            {'A': {'true': 8, 'false': 2}, 'B': {'true': 5, 'false': 5}, 'X': {'true': 7, 'false': 3}, 'Y': {'true': 6, 'false': 4}}  # player_responses
        )
        
        success_metrics_str = str(success_data)
        result = _calculate_success_statistics(success_metrics_str)
        
        assert isinstance(result, dict)
        assert 'trace_average_statistic' in result  # This should be overall_success_rate
        assert 'chsh_value_statistic' in result    # This should be normalized_cumulative_score
        assert 'cross_term_combination_statistic' in result
        assert 'same_item_balance' in result
        
        # Verify the mapping
        assert result['trace_average_statistic'] == 0.75  # overall_success_rate
        assert result['chsh_value_statistic'] == 0.5     # normalized_cumulative_score

    def test_both_computations_called(self, mock_state, mock_compute_functions):
        """Test that both classic and new computations are called regardless of mode."""
        mock_state.game_mode = 'classic'
        
        with patch('src.sockets.dashboard._calculate_team_statistics') as mock_calc_classic, \
             patch('src.sockets.dashboard._calculate_success_statistics') as mock_calc_success:
            
            mock_calc_classic.return_value = {}
            mock_calc_success.return_value = {}
            
            _process_single_team(1, 'TestTeam', True, '2023-01-01', 5, 'p1', 'p2')
            
            # Both calculation functions should be called
            mock_calc_classic.assert_called_once()
            mock_calc_success.assert_called_once()
            
            # Both computation functions should be called
            mock_hashes, mock_corr, mock_success = mock_compute_functions
            mock_corr.assert_called_once()
            mock_success.assert_called_once()

    def test_mode_toggle_preserves_data_structure(self, mock_state, mock_compute_functions):
        """Test that switching modes preserves the data structure."""
        with patch('src.sockets.dashboard._calculate_team_statistics') as mock_calc_classic, \
             patch('src.sockets.dashboard._calculate_success_statistics') as mock_calc_success:
            
            mock_calc_classic.return_value = {'classic_stat': 1.0}
            mock_calc_success.return_value = {'new_stat': 2.0}
            
            # Test classic mode first
            mock_state.game_mode = 'classic'
            result_classic = _process_single_team(1, 'TestTeam', True, '2023-01-01', 5, 'p1', 'p2')
            
            # Test new mode
            mock_state.game_mode = 'new'
            result_new = _process_single_team(1, 'TestTeam', True, '2023-01-01', 5, 'p1', 'p2')
            
            # Both results should have the same structure
            assert set(result_classic.keys()) == set(result_new.keys())
            
            # Both should contain all statistics
            for result in [result_classic, result_new]:
                assert 'classic_stats' in result
                assert 'new_stats' in result
                assert 'classic_matrix' in result
                assert 'new_matrix' in result
                assert 'correlation_stats' in result  # Current display stats
                assert 'correlation_matrix' in result  # Current display matrix

    def test_new_mode_individual_balance_calculation(self):
        """Test that NEW mode correctly calculates individual player balance instead of same-question balance."""
        # Mock success data with realistic player responses for NEW mode
        # Player 1 gets A,B questions; Player 2 gets X,Y questions
        success_data = (
            [[(8, 10), (7, 10), (6, 10), (5, 10)] for _ in range(4)],  # success_matrix_tuples
            ['A', 'B', 'X', 'Y'],  # item_values
            0.75,  # overall_success_rate
            0.5,   # normalized_cumulative_score
            {('A', 'X'): 8, ('A', 'Y'): 6, ('B', 'X'): 7, ('B', 'Y'): 5},  # success_counts
            {('A', 'X'): 10, ('A', 'Y'): 10, ('B', 'X'): 10, ('B', 'Y'): 10}, # pair_counts
            {
                # Player 1 responses (A,B questions)
                'A': {'true': 8, 'false': 2},   # 80% true, balance = 0.4 (min(8,2)/10 * 2)
                'B': {'true': 5, 'false': 5},   # 50% true, balance = 1.0 (min(5,5)/10 * 2)
                # Player 2 responses (X,Y questions)  
                'X': {'true': 7, 'false': 3},   # 70% true, balance = 0.6 (min(7,3)/10 * 2)
                'Y': {'true': 6, 'false': 4}    # 60% true, balance = 0.8 (min(6,4)/10 * 2)
            }
        )
        
        success_metrics_str = str(success_data)
        result = _calculate_success_statistics(success_metrics_str)
        
        # Expected individual balances:
        # A: min(8,2)/10 * 2 = 0.4
        # B: min(5,5)/10 * 2 = 1.0  
        # X: min(7,3)/10 * 2 = 0.6
        # Y: min(6,4)/10 * 2 = 0.8
        # Average: (0.4 + 1.0 + 0.6 + 0.8) / 4 = 0.7
        
        expected_balance = (0.4 + 1.0 + 0.6 + 0.8) / 4
        
        assert isinstance(result, dict)
        assert 'same_item_balance' in result
        assert result['same_item_balance'] == pytest.approx(expected_balance, abs=1e-6)
        
        # Verify uncertainty calculation
        assert 'same_item_balance_uncertainty' in result
        assert result['same_item_balance_uncertainty'] is not None

    def test_compute_success_metrics_tracks_individual_responses(self):
        """Test that compute_success_metrics properly tracks individual player responses for NEW mode."""
        from unittest.mock import MagicMock
        from src.sockets.dashboard import compute_success_metrics
        from src.models.quiz_models import PairQuestionRounds, Answers, ItemEnum
        
        # Mock the database queries
        with patch('src.sockets.dashboard.PairQuestionRounds') as mock_rounds_model, \
             patch('src.sockets.dashboard.Answers') as mock_answers_model:
            
            # Mock rounds data - NEW mode pattern (Player 1: A,B; Player 2: X,Y)
            mock_round_1 = MagicMock()
            mock_round_1.round_id = 1
            mock_round_1.player1_item = ItemEnum.A
            mock_round_1.player2_item = ItemEnum.X
            
            mock_round_2 = MagicMock()
            mock_round_2.round_id = 2
            mock_round_2.player1_item = ItemEnum.B
            mock_round_2.player2_item = ItemEnum.Y
            
            mock_rounds_query = MagicMock()
            mock_rounds_query.filter_by.return_value.order_by.return_value.all.return_value = [mock_round_1, mock_round_2]
            mock_rounds_model.query = mock_rounds_query
            
            # Mock answers data
            # Round 1: Player 1 (A) = True, Player 2 (X) = False  
            # Round 2: Player 1 (B) = False, Player 2 (Y) = True
            mock_answer_1a = MagicMock()
            mock_answer_1a.question_round_id = 1
            mock_answer_1a.assigned_item = ItemEnum.A
            mock_answer_1a.response_value = True
            
            mock_answer_1b = MagicMock()
            mock_answer_1b.question_round_id = 1  
            mock_answer_1b.assigned_item = ItemEnum.X
            mock_answer_1b.response_value = False
            
            mock_answer_2a = MagicMock()
            mock_answer_2a.question_round_id = 2
            mock_answer_2a.assigned_item = ItemEnum.B
            mock_answer_2a.response_value = False
            
            mock_answer_2b = MagicMock()
            mock_answer_2b.question_round_id = 2
            mock_answer_2b.assigned_item = ItemEnum.Y  
            mock_answer_2b.response_value = True
            
            mock_answers_query = MagicMock()
            mock_answers_query.filter_by.return_value.order_by.return_value.all.return_value = [
                mock_answer_1a, mock_answer_1b, mock_answer_2a, mock_answer_2b
            ]
            mock_answers_model.query = mock_answers_query
            
            # Call the function
            result = compute_success_metrics(team_id=1)
            
            # Verify return structure
            assert len(result) == 7
            success_matrix, item_values, overall_success_rate, normalized_score, success_counts, pair_counts, player_responses = result
            
            # Verify player_responses tracks individual responses correctly
            assert 'A' in player_responses
            assert 'B' in player_responses
            assert 'X' in player_responses
            assert 'Y' in player_responses
            
            # Check that player responses are tracked correctly
            # Player 1: A=True, B=False
            # Player 2: X=False, Y=True
            assert player_responses['A']['true'] == 1
            assert player_responses['A']['false'] == 0
            assert player_responses['B']['true'] == 0
            assert player_responses['B']['false'] == 1
            assert player_responses['X']['true'] == 0
            assert player_responses['X']['false'] == 1
            assert player_responses['Y']['true'] == 1
            assert player_responses['Y']['false'] == 0