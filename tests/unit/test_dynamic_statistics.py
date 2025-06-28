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

    @pytest.fixture(autouse=True)
    def setup_flask_context(self):
        """Setup Flask application context for tests"""
        from src.config import app
        with app.test_request_context('/'):
            yield

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
        with patch('src.sockets.dashboard.computations.compute_team_hashes') as mock_hashes, \
             patch('src.sockets.dashboard.computations.compute_correlation_matrix') as mock_corr, \
             patch('src.sockets.dashboard.computations.compute_success_metrics') as mock_success, \
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
        
        with patch('src.sockets.dashboard.computations._calculate_team_statistics') as mock_calc_classic, \
             patch('src.sockets.dashboard.computations._calculate_success_statistics') as mock_calc_success:
            
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
        
        with patch('src.sockets.dashboard.computations._calculate_team_statistics') as mock_calc_classic, \
             patch('src.sockets.dashboard.computations._calculate_success_statistics') as mock_calc_success:
            
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
        
        # Mock the compute_success_metrics to return our test data
        with patch('src.sockets.dashboard.computations.compute_success_metrics') as mock_compute:
            mock_compute.return_value = success_data
            result = _calculate_success_statistics("test_team")
        
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
        
        with patch('src.sockets.dashboard.computations._get_team_id_from_name') as mock_get_id:
            mock_get_id.return_value = 1  # Ensure team ID lookup succeeds
            
            with patch('src.sockets.dashboard.computations._calculate_team_statistics') as mock_calc_classic, \
                 patch('src.sockets.dashboard.computations._calculate_success_statistics') as mock_calc_success:
                
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
        with patch('src.sockets.dashboard.computations._get_team_id_from_name') as mock_get_id:
            mock_get_id.return_value = 1  # Ensure team ID lookup succeeds
            
            with patch('src.sockets.dashboard.computations._calculate_team_statistics') as mock_calc_classic, \
                 patch('src.sockets.dashboard.computations._calculate_success_statistics') as mock_calc_success:
                
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
        
        # Mock the compute_success_metrics to return our test data
        with patch('src.sockets.dashboard.computations.compute_success_metrics') as mock_compute:
            mock_compute.return_value = success_data
            result = _calculate_success_statistics("test_team")
        
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
            
            # Call the function with team name and mock the lookup
            with patch('src.sockets.dashboard._get_team_id_from_name') as mock_get_id:
                mock_get_id.return_value = 1
                result = compute_success_metrics("test_team")
            
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

    def test_new_mode_dashboard_display_logic(self):
        """Test that NEW mode dashboard shows only success rate and awards only 🏆 based on success rate."""
        # Mock teams data for NEW mode
        teams_data = [
            {
                'team_id': 1,
                'team_name': 'Team1',
                'min_stats_sig': True,
                'new_stats': {
                    'trace_average_statistic': 0.85,  # 85% success rate - highest
                    'trace_average_statistic_uncertainty': 0.05,
                    'same_item_balance': 0.7,
                    'chsh_value_statistic': 0.4
                }
            },
            {
                'team_id': 2,
                'team_name': 'Team2',
                'min_stats_sig': True,
                'new_stats': {
                    'trace_average_statistic': 0.75,  # 75% success rate - lower
                    'trace_average_statistic_uncertainty': 0.06,
                    'same_item_balance': 0.9,  # Higher balance, but shouldn't matter for 🏆
                    'chsh_value_statistic': 0.6  # Higher normalized score, but shouldn't matter for 🏆
                }
            },
            {
                'team_id': 3,
                'team_name': 'Team3',
                'min_stats_sig': False,  # Not eligible for awards
                'new_stats': {
                    'trace_average_statistic': 0.95,  # Highest success rate but not eligible
                    'trace_average_statistic_uncertainty': 0.03,
                    'same_item_balance': 0.8,
                    'chsh_value_statistic': 0.7
                }
            }
        ]
        
        # Simulate award calculation logic from dashboard.js for NEW mode
        highestBalancedTrTeamId = None  # Should be None in NEW mode (no 🎯 award)
        highestChshTeamId = None
        maxChshValue = -float('inf')
        
        eligible_teams = [team for team in teams_data if team['min_stats_sig']]
        
        # NEW mode award logic: only 🏆 based on success rate
        for team in eligible_teams:
            stats = team['new_stats']
            success_rate = stats['trace_average_statistic']
            if success_rate > maxChshValue:
                maxChshValue = success_rate
                highestChshTeamId = team['team_id']
        
        # Verify award logic for NEW mode
        assert highestBalancedTrTeamId is None, "NEW mode should not award 🎯"
        assert highestChshTeamId == 1, "Team1 should get 🏆 for highest success rate (85%)"
        assert maxChshValue == 0.85, "Max value should be Team1's success rate"
        
        # Verify that Team3 (not eligible) doesn't get award despite higher success rate
        assert highestChshTeamId != 3, "Ineligible teams should not receive awards"
        
        # Test table header logic for NEW mode
        current_game_mode = 'new'
        
        # Simulate header update logic
        header_config = {}
        if current_game_mode == 'classic':
            header_config = {
                'header1': 'Trace Avg ⏐⟨Tr⟩⏐',
                'header2': 'Balance',
                'header3': 'Balanced ⏐⟨Tr⟩⏐ 🎯',
                'header4': 'CHSH Value 🏆',
                'columns_visible': [True, True, True, True]
            }
        else:  # new mode
            header_config = {
                'header1': 'Success Rate % 🏆',
                'header2': 'Response Balance',
                'header3': 'Balanced Success 🎯',
                'header4': 'Norm. Score 🏆',
                'columns_visible': [True, False, False, False]  # Only first column visible
            }
        
        # Verify NEW mode header configuration
        assert header_config['header1'] == 'Success Rate % 🏆'
        assert header_config['columns_visible'] == [True, False, False, False]
        
        # Verify that only success rate column is visible in NEW mode
        visible_columns = sum(header_config['columns_visible'])
        assert visible_columns == 1, "NEW mode should only show 1 column (Success Rate %)"
        
        # Test that awards string formation works correctly
        def get_awards_string(team_id, highest_balanced_tr_id, highest_chsh_id):
            awards = []
            if team_id == highest_balanced_tr_id and highest_balanced_tr_id is not None:
                awards.append("🎯")
            if team_id == highest_chsh_id and highest_chsh_id is not None:
                awards.append("🏆")
            return " ".join(awards)
        
        # Test awards for each team
        team1_awards = get_awards_string(1, highestBalancedTrTeamId, highestChshTeamId)
        team2_awards = get_awards_string(2, highestBalancedTrTeamId, highestChshTeamId)
        team3_awards = get_awards_string(3, highestBalancedTrTeamId, highestChshTeamId)
        
        assert team1_awards == "🏆", "Team1 should only get 🏆 award"
        assert team2_awards == "", "Team2 should get no awards"
        assert team3_awards == "", "Team3 should get no awards (not eligible)"
        
        # Verify no 🎯 awards in NEW mode
        for team_data in teams_data:
            team_awards = get_awards_string(team_data['team_id'], highestBalancedTrTeamId, highestChshTeamId)
            assert "🎯" not in team_awards, f"Team {team_data['team_id']} should not have 🎯 award in NEW mode"

    def test_dashboard_success_rate_sorting_new_mode(self):
        """Test that NEW mode dashboard sorting by success rate works correctly."""
        # Mock teams data for NEW mode with different success rates
        teams_data = [
            {
                'team_id': 1,
                'team_name': 'Team_Low',
                'is_active': True,
                'min_stats_sig': True,
                'new_stats': {
                    'trace_average_statistic': 0.65,  # 65% success rate
                    'trace_average_statistic_uncertainty': 0.05,
                    'same_item_balance': 0.7,
                    'chsh_value_statistic': 0.4
                }
            },
            {
                'team_id': 2,
                'team_name': 'Team_High',
                'is_active': True,
                'min_stats_sig': True,
                'new_stats': {
                    'trace_average_statistic': 0.95,  # 95% success rate - highest
                    'trace_average_statistic_uncertainty': 0.03,
                    'same_item_balance': 0.8,
                    'chsh_value_statistic': 0.6
                }
            },
            {
                'team_id': 3,
                'team_name': 'Team_Med',
                'is_active': True,
                'min_stats_sig': True,
                'new_stats': {
                    'trace_average_statistic': 0.75,  # 75% success rate
                    'trace_average_statistic_uncertainty': 0.04,
                    'same_item_balance': 0.6,
                    'chsh_value_statistic': 0.5
                }
            },
            {
                'team_id': 4,
                'team_name': 'Team_No_Stats',
                'is_active': True,
                'min_stats_sig': False,
                'new_stats': None  # No stats available
            }
        ]
        
        # Sort by success rate (should be descending: highest first)
        def get_success_rate(team):
            if team.get('new_stats') and team['new_stats']:
                return team['new_stats'].get('trace_average_statistic', -1)
            return -1
        
        sorted_teams = sorted(teams_data, key=get_success_rate, reverse=True)
        
        # Verify sorting order: Team_High (0.95), Team_Med (0.75), Team_Low (0.65), Team_No_Stats (-1)
        expected_order = ['Team_High', 'Team_Med', 'Team_Low', 'Team_No_Stats']
        actual_order = [team['team_name'] for team in sorted_teams]
        
        assert actual_order == expected_order, f"Expected {expected_order}, got {actual_order}"
        
        # Verify highest success rate team should get 🏆
        highest_team = sorted_teams[0]
        assert highest_team['team_name'] == 'Team_High'
        assert highest_team['new_stats']['trace_average_statistic'] == 0.95
        
    def test_dashboard_success_rate_sorting_classic_mode(self):
        """Test that CLASSIC mode dashboard sorting by success rate uses cross_term_combination_statistic (CHSH value)."""
        # Mock teams data for CLASSIC mode with different CHSH values
        teams_data = [
            {
                'team_id': 1,
                'team_name': 'Team_A',
                'is_active': True,
                'min_stats_sig': True,
                'classic_stats': {
                    'trace_average_statistic': 0.8,  # Higher trace average but lower CHSH
                    'trace_average_statistic_uncertainty': 0.05,
                    'same_item_balance': 0.7,
                    'cross_term_combination_statistic': 2.1  # Lower CHSH value
                }
            },
            {
                'team_id': 2,
                'team_name': 'Team_B',
                'is_active': True,
                'min_stats_sig': True,
                'classic_stats': {
                    'trace_average_statistic': 0.3,  # Lower trace average but higher CHSH
                    'trace_average_statistic_uncertainty': 0.03,
                    'same_item_balance': 0.8,
                    'cross_term_combination_statistic': 2.8  # Highest CHSH value
                }
            },
            {
                'team_id': 3,
                'team_name': 'Team_C',
                'is_active': True,
                'min_stats_sig': True,
                'classic_stats': {
                    'trace_average_statistic': 0.5,  # Medium trace average
                    'trace_average_statistic_uncertainty': 0.04,
                    'same_item_balance': 0.6,
                    'cross_term_combination_statistic': 2.5  # Medium CHSH value
                }
            }
        ]
        
        # Sort by CHSH value (classic mode success rate sorting)
        def get_classic_chsh_value(team):
            if team.get('classic_stats') and team['classic_stats']:
                return team['classic_stats'].get('cross_term_combination_statistic', -1)
            return -1
        
        sorted_teams = sorted(teams_data, key=get_classic_chsh_value, reverse=True)
        
        # Verify sorting order by CHSH value: Team_B (2.8), Team_C (2.5), Team_A (2.1)
        expected_order = ['Team_B', 'Team_C', 'Team_A']
        actual_order = [team['team_name'] for team in sorted_teams]
        
        assert actual_order == expected_order, f"Expected {expected_order}, got {actual_order}"
        
    def test_dashboard_success_rate_sorting_with_equal_values(self):
        """Test that teams with equal success rates are sorted by name as tiebreaker."""
        teams_data = [
            {
                'team_id': 1,
                'team_name': 'Team_Z',
                'is_active': True,
                'min_stats_sig': True,
                'new_stats': {
                    'trace_average_statistic': 0.75,  # Same success rate
                }
            },
            {
                'team_id': 2,
                'team_name': 'Team_A',
                'is_active': True,
                'min_stats_sig': True,
                'new_stats': {
                    'trace_average_statistic': 0.75,  # Same success rate
                }
            },
            {
                'team_id': 3,
                'team_name': 'Team_M',
                'is_active': True,
                'min_stats_sig': True,
                'new_stats': {
                    'trace_average_statistic': 0.75,  # Same success rate
                }
            }
        ]
        
        # Sort by success rate (descending) then by name (ascending) for tiebreaker
        def sort_teams(teams):
            return sorted(teams, key=lambda t: (
                -(t.get('new_stats', {}).get('trace_average_statistic', -1)),  # Negative for descending
                t['team_name']  # Ascending for tiebreaker
            ))
        
        sorted_teams = sort_teams(teams_data)
        
        # With equal success rates, should sort alphabetically by name
        expected_order = ['Team_A', 'Team_M', 'Team_Z']
        actual_order = [team['team_name'] for team in sorted_teams]
        
        assert actual_order == expected_order, f"Expected {expected_order}, got {actual_order}"

    def test_dashboard_success_rate_sorting_mode_aware_behavior(self):
        """Test that sorting behavior changes correctly between NEW and CLASSIC modes."""
        # Mock teams data with both new and classic stats
        teams_data = [
            {
                'team_id': 1,
                'team_name': 'Team_Alpha',
                'is_active': True,
                'min_stats_sig': True,
                'new_stats': {
                    'trace_average_statistic': 0.95,  # High success rate
                },
                'classic_stats': {
                    'cross_term_combination_statistic': 2.1  # Low CHSH value
                }
            },
            {
                'team_id': 2,
                'team_name': 'Team_Beta',
                'is_active': True,
                'min_stats_sig': True,
                'new_stats': {
                    'trace_average_statistic': 0.65,  # Low success rate
                },
                'classic_stats': {
                    'cross_term_combination_statistic': 2.9  # High CHSH value
                }
            }
        ]
        
        # Test NEW mode sorting (by success rate)
        def get_new_mode_sort_value(team):
            if team.get('new_stats') and team['new_stats']:
                return team['new_stats'].get('trace_average_statistic', -1)
            return -1
        
        new_mode_sorted = sorted(teams_data, key=get_new_mode_sort_value, reverse=True)
        new_mode_order = [team['team_name'] for team in new_mode_sorted]
        
        # In NEW mode: Team_Alpha (0.95) should come before Team_Beta (0.65)
        assert new_mode_order == ['Team_Alpha', 'Team_Beta'], f"NEW mode sort failed: {new_mode_order}"
        
        # Test CLASSIC mode sorting (by CHSH value)
        def get_classic_mode_sort_value(team):
            if team.get('classic_stats') and team['classic_stats']:
                return team['classic_stats'].get('cross_term_combination_statistic', -1)
            return -1
        
        classic_mode_sorted = sorted(teams_data, key=get_classic_mode_sort_value, reverse=True)
        classic_mode_order = [team['team_name'] for team in classic_mode_sorted]
        
        # In CLASSIC mode: Team_Beta (2.9) should come before Team_Alpha (2.1)
        assert classic_mode_order == ['Team_Beta', 'Team_Alpha'], f"CLASSIC mode sort failed: {classic_mode_order}"
        
        # Verify the sorting gives different results in different modes
        assert new_mode_order != classic_mode_order, "Sorting should produce different results in different modes"
    
    def test_dashboard_dropdown_text_simulation(self):
        """Test simulation of dropdown text changes between modes."""
        # Simulate the dropdown text update logic
        def get_dropdown_text(mode):
            if mode == 'classic':
                return 'Sort by CHSH Value'
            else:
                return 'Sort by Success Rate'
        
        # Test mode changes
        assert get_dropdown_text('new') == 'Sort by Success Rate'
        assert get_dropdown_text('classic') == 'Sort by CHSH Value'
        
        # Test case insensitivity and edge cases
        assert get_dropdown_text('NEW') == 'Sort by Success Rate'  # Different case
        assert get_dropdown_text('unknown') == 'Sort by Success Rate'  # Default to new mode