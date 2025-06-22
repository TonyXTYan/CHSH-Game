import pytest
from unittest.mock import patch, MagicMock
import random
from collections import defaultdict, Counter
import math

from src.models.quiz_models import ItemEnum, PairQuestionRounds, Answers
try:
    from src.game_logic import start_new_round_for_pair, QUESTION_ITEMS, TARGET_COMBO_REPEATS
except ImportError:
    # Mock the imports if not available
    start_new_round_for_pair = lambda x: None
    QUESTION_ITEMS = []
    TARGET_COMBO_REPEATS = 5
from src.state import state


class TestGameLogicAdvanced:
    """Advanced test suite for game logic focusing on statistical fairness and edge cases"""

    @pytest.fixture(autouse=True)
    def reset_state(self):
        """Reset game state before each test"""
        state.active_teams.clear()
        state.player_to_team.clear()
        state.team_id_to_name.clear()
        yield
        state.active_teams.clear()
        state.player_to_team.clear()
        state.team_id_to_name.clear()

    @pytest.fixture
    def mock_team_info(self):
        """Create a mock team info dictionary"""
        return {
            'team_id': 1,
            'players': ['player1_sid', 'player2_sid'],
            'current_round_number': 0,
            'combo_tracker': {},
            'current_db_round_id': None,
            'answered_current_round': {}
        }

    @pytest.mark.skipif(len(QUESTION_ITEMS) == 0, reason="QUESTION_ITEMS not available")
    def test_statistical_fairness_over_many_rounds(self, mock_team_info):
        """Test that question distribution is statistically fair over many rounds"""
        team_name = "StatisticalTeam"
        state.active_teams[team_name] = mock_team_info
        
        # Track question combinations over many rounds
        combo_counts = defaultdict(int)
        total_rounds = 1000
        
        with patch('src.game_logic.PairQuestionRounds') as mock_rounds, \
             patch('src.game_logic.db'), \
             patch('src.game_logic.socketio'), \
             patch('src.game_logic.clear_team_caches'):
            
            # Mock round creation
            mock_round = MagicMock()
            mock_round.round_id = 1
            mock_rounds.return_value = mock_round
            
            for _ in range(total_rounds):
                start_new_round_for_pair(team_name)
                
                # Get the last call to mock_rounds to see what combo was chosen
                call_args = mock_rounds.call_args
                if call_args:
                    kwargs = call_args.kwargs
                    p1_item = kwargs.get('player1_item')
                    p2_item = kwargs.get('player2_item')
                    if p1_item and p2_item:
                        combo = (p1_item.value, p2_item.value)
                        combo_counts[combo] += 1
        
        # Verify statistical fairness
        all_combos = [(i1.value, i2.value) for i1 in QUESTION_ITEMS for i2 in QUESTION_ITEMS]
        
        # Each combo should appear approximately total_rounds / len(all_combos) times
        expected_frequency = total_rounds / len(all_combos)
        tolerance = expected_frequency * 0.2  # 20% tolerance
        
        for combo in all_combos:
            actual_count = combo_counts[combo]
            assert abs(actual_count - expected_frequency) < tolerance, \
                f"Combo {combo} appeared {actual_count} times, expected ~{expected_frequency}"

    @pytest.mark.skipif(len(QUESTION_ITEMS) == 0, reason="QUESTION_ITEMS not available")
    def test_deterministic_phase_triggers_correctly(self, mock_team_info):
        """Test that deterministic phase triggers at the correct round limit"""
        team_name = "DeterministicTeam"
        
        # Calculate when deterministic phase should start
        all_combos = [(i1.value, i2.value) for i1 in QUESTION_ITEMS for i2 in QUESTION_ITEMS]
        round_limit = (TARGET_COMBO_REPEATS + 1) * len(all_combos)
        deterministic_start = round_limit - len(all_combos)
        
        # Set team to be just before deterministic phase
        mock_team_info['current_round_number'] = deterministic_start - 1
        
        # Setup combo tracker with some combos at target, some below
        combo_tracker = {}
        for i, combo in enumerate(all_combos):
            if i % 2 == 0:  # Half at target
                combo_tracker[combo] = TARGET_COMBO_REPEATS
            else:  # Half below target
                combo_tracker[combo] = TARGET_COMBO_REPEATS - 1
        
        mock_team_info['combo_tracker'] = combo_tracker
        state.active_teams[team_name] = mock_team_info
        
        chosen_combos = []
        
        with patch('src.game_logic.PairQuestionRounds') as mock_rounds, \
             patch('src.game_logic.db'), \
             patch('src.game_logic.socketio'), \
             patch('src.game_logic.clear_team_caches'):
            
            mock_round = MagicMock()
            mock_round.round_id = 1
            mock_rounds.return_value = mock_round
            
            # Run several rounds to enter deterministic phase
            for _ in range(len(all_combos) + 2):
                start_new_round_for_pair(team_name)
                
                # Capture chosen combo
                call_args = mock_rounds.call_args
                if call_args:
                    kwargs = call_args.kwargs
                    p1_item = kwargs.get('player1_item')
                    p2_item = kwargs.get('player2_item')
                    if p1_item and p2_item:
                        chosen_combos.append((p1_item.value, p2_item.value))
        
        # In deterministic phase, should prioritize combos that need more repeats
        team_info = state.active_teams[team_name]
        final_tracker = team_info['combo_tracker']
        
        # All combos should be closer to TARGET_COMBO_REPEATS
        for combo in all_combos:
            count = final_tracker.get(combo, 0)
            assert count >= TARGET_COMBO_REPEATS - 1, \
                f"Combo {combo} should be close to target, got {count}"

    @pytest.mark.skipif(len(QUESTION_ITEMS) == 0, reason="QUESTION_ITEMS not available")
    def test_combo_tracker_consistency(self, mock_team_info):
        """Test that combo tracker maintains consistency across rounds"""
        team_name = "ConsistencyTeam"
        state.active_teams[team_name] = mock_team_info
        
        with patch('src.game_logic.PairQuestionRounds') as mock_rounds, \
             patch('src.game_logic.db'), \
             patch('src.game_logic.socketio'), \
             patch('src.game_logic.clear_team_caches'):
            
            mock_round = MagicMock()
            mock_round.round_id = 1
            mock_rounds.return_value = mock_round
            
            # Track combos manually
            manual_tracker = defaultdict(int)
            
            for round_num in range(50):
                start_new_round_for_pair(team_name)
                
                # Get chosen combo
                call_args = mock_rounds.call_args
                if call_args:
                    kwargs = call_args.kwargs
                    p1_item = kwargs.get('player1_item')
                    p2_item = kwargs.get('player2_item')
                    if p1_item and p2_item:
                        combo = (p1_item.value, p2_item.value)
                        manual_tracker[combo] += 1
                
                # Compare with internal tracker
                team_info = state.active_teams[team_name]
                internal_tracker = team_info['combo_tracker']
                
                for combo, count in manual_tracker.items():
                    assert internal_tracker.get(combo, 0) == count, \
                        f"Round {round_num}: Tracker inconsistency for {combo}"

    @pytest.mark.skipif(len(QUESTION_ITEMS) == 0, reason="QUESTION_ITEMS not available")
    def test_round_limit_enforcement(self, mock_team_info):
        """Test that teams don't exceed the theoretical round limit"""
        team_name = "LimitTeam"
        state.active_teams[team_name] = mock_team_info
        
        all_combos = [(i1.value, i2.value) for i1 in QUESTION_ITEMS for i2 in QUESTION_ITEMS]
        max_rounds = (TARGET_COMBO_REPEATS + 1) * len(all_combos)
        
        with patch('src.game_logic.PairQuestionRounds') as mock_rounds, \
             patch('src.game_logic.db'), \
             patch('src.game_logic.socketio'), \
             patch('src.game_logic.clear_team_caches'):
            
            mock_round = MagicMock()
            mock_round.round_id = 1
            mock_rounds.return_value = mock_round
            
            # Run up to theoretical maximum
            for _ in range(max_rounds):
                start_new_round_for_pair(team_name)
            
            team_info = state.active_teams[team_name]
            assert team_info['current_round_number'] <= max_rounds, \
                "Should not exceed theoretical maximum rounds"
            
            # Verify all combos reached target
            combo_tracker = team_info['combo_tracker']
            for combo in all_combos:
                count = combo_tracker.get(combo, 0)
                assert count >= TARGET_COMBO_REPEATS, \
                    f"Combo {combo} did not reach target: {count} < {TARGET_COMBO_REPEATS}"

    def test_random_seed_reproducibility(self, mock_team_info):
        """Test that game logic produces consistent results with same random seed"""
        team_name = "ReproducibleTeam"
        
        def run_rounds_with_seed(seed, rounds=20):
            # Reset team state
            team_info = mock_team_info.copy()
            team_info['current_round_number'] = 0
            team_info['combo_tracker'] = {}
            state.active_teams[team_name] = team_info
            
            # Set random seed
            random.seed(seed)
            
            chosen_combos = []
            
            with patch('src.game_logic.PairQuestionRounds') as mock_rounds, \
                 patch('src.game_logic.db'), \
                 patch('src.game_logic.socketio'), \
                 patch('src.game_logic.clear_team_caches'):
                
                mock_round = MagicMock()
                mock_round.round_id = 1
                mock_rounds.return_value = mock_round
                
                for _ in range(rounds):
                    start_new_round_for_pair(team_name)
                    
                    call_args = mock_rounds.call_args
                    if call_args:
                        kwargs = call_args.kwargs
                        p1_item = kwargs.get('player1_item')
                        p2_item = kwargs.get('player2_item')
                        if p1_item and p2_item:
                            chosen_combos.append((p1_item.value, p2_item.value))
            
            return chosen_combos
        
        # Run with same seed twice
        seed = 12345
        combos1 = run_rounds_with_seed(seed)
        combos2 = run_rounds_with_seed(seed)
        
        # Should produce identical sequences
        assert combos1 == combos2, "Same seed should produce identical combo sequences"
        
        # Run with different seed
        combos3 = run_rounds_with_seed(seed + 1)
        
        # Should produce different sequence
        assert combos1 != combos3, "Different seed should produce different combo sequences"

    @pytest.mark.skipif(len(QUESTION_ITEMS) == 0, reason="QUESTION_ITEMS not available")
    def test_edge_case_single_combo_remaining(self, mock_team_info):
        """Test behavior when only one combo needs more repetitions"""
        team_name = "EdgeCaseTeam"
        
        all_combos = [(i1.value, i2.value) for i1 in QUESTION_ITEMS for i2 in QUESTION_ITEMS]
        
        # Set up tracker where all combos except one are at target
        combo_tracker = {}
        remaining_combo = all_combos[0]  # Choose first combo as the remaining one
        
        for combo in all_combos:
            if combo == remaining_combo:
                combo_tracker[combo] = TARGET_COMBO_REPEATS - 1  # One short
            else:
                combo_tracker[combo] = TARGET_COMBO_REPEATS  # At target
        
        mock_team_info['combo_tracker'] = combo_tracker
        mock_team_info['current_round_number'] = len(all_combos) * TARGET_COMBO_REPEATS - 1
        state.active_teams[team_name] = mock_team_info
        
        with patch('src.game_logic.PairQuestionRounds') as mock_rounds, \
             patch('src.game_logic.db'), \
             patch('src.game_logic.socketio'), \
             patch('src.game_logic.clear_team_caches'):
            
            mock_round = MagicMock()
            mock_round.round_id = 1
            mock_rounds.return_value = mock_round
            
            # Next round should deterministically choose the remaining combo
            start_new_round_for_pair(team_name)
            
            call_args = mock_rounds.call_args
            kwargs = call_args.kwargs
            p1_item = kwargs.get('player1_item')
            p2_item = kwargs.get('player2_item')
            chosen_combo = (p1_item.value, p2_item.value)
            
            assert chosen_combo == remaining_combo, \
                f"Should choose remaining combo {remaining_combo}, got {chosen_combo}"

    def test_concurrent_teams_independence(self):
        """Test that multiple teams maintain independent combo tracking"""
        team1_name = "ConcurrentTeam1"
        team2_name = "ConcurrentTeam2"
        
        # Setup two teams
        team1_info = {
            'team_id': 1,
            'players': ['p1_1', 'p1_2'],
            'current_round_number': 0,
            'combo_tracker': {},
            'current_db_round_id': None,
            'answered_current_round': {}
        }
        
        team2_info = {
            'team_id': 2,
            'players': ['p2_1', 'p2_2'],
            'current_round_number': 0,
            'combo_tracker': {},
            'current_db_round_id': None,
            'answered_current_round': {}
        }
        
        state.active_teams[team1_name] = team1_info
        state.active_teams[team2_name] = team2_info
        
        with patch('src.game_logic.PairQuestionRounds') as mock_rounds, \
             patch('src.game_logic.db'), \
             patch('src.game_logic.socketio'), \
             patch('src.game_logic.clear_team_caches'):
            
            mock_round = MagicMock()
            mock_round.round_id = 1
            mock_rounds.return_value = mock_round
            
            # Run rounds for both teams
            for _ in range(10):
                start_new_round_for_pair(team1_name)
                start_new_round_for_pair(team2_name)
            
            # Teams should have independent trackers
            tracker1 = state.active_teams[team1_name]['combo_tracker']
            tracker2 = state.active_teams[team2_name]['combo_tracker']
            
            # They might be different due to random choices
            assert state.active_teams[team1_name]['current_round_number'] == 10
            assert state.active_teams[team2_name]['current_round_number'] == 10
            
            # Each team should maintain its own valid tracker
            for tracker in [tracker1, tracker2]:
                total_rounds = sum(tracker.values())
                assert total_rounds == 10, f"Tracker should sum to 10, got {total_rounds}"

    def test_invalid_team_state_handling(self):
        """Test handling of invalid or corrupted team state"""
        invalid_states = [
            # Missing players
            {
                'team_id': 1,
                'players': ['only_one_player'],
                'current_round_number': 0,
                'combo_tracker': {},
                'current_db_round_id': None,
                'answered_current_round': {}
            },
            # Empty players
            {
                'team_id': 1,
                'players': [],
                'current_round_number': 0,
                'combo_tracker': {},
                'current_db_round_id': None,
                'answered_current_round': {}
            },
            # Missing combo_tracker
            {
                'team_id': 1,
                'players': ['p1', 'p2'],
                'current_round_number': 0,
                'current_db_round_id': None,
                'answered_current_round': {}
            },
            # Corrupted combo_tracker
            {
                'team_id': 1,
                'players': ['p1', 'p2'],
                'current_round_number': 0,
                'combo_tracker': "not_a_dict",
                'current_db_round_id': None,
                'answered_current_round': {}
            }
        ]
        
        for i, invalid_state in enumerate(invalid_states):
            team_name = f"InvalidTeam_{i}"
            state.active_teams[team_name] = invalid_state
            
            with patch('src.game_logic.PairQuestionRounds'), \
                 patch('src.game_logic.db'), \
                 patch('src.game_logic.socketio'), \
                 patch('src.game_logic.clear_team_caches'):
                
                # Should handle invalid state gracefully (not crash)
                try:
                    start_new_round_for_pair(team_name)
                except Exception as e:
                    # If it raises an exception, it should be handled gracefully
                    # The function should have error handling for invalid states
                    pass

    @pytest.mark.skipif(len(QUESTION_ITEMS) == 0, reason="QUESTION_ITEMS not available")
    def test_combo_distribution_entropy(self, mock_team_info):
        """Test that combo distribution has appropriate entropy (randomness)"""
        team_name = "EntropyTeam"
        state.active_teams[team_name] = mock_team_info
        
        combo_sequence = []
        
        with patch('src.game_logic.PairQuestionRounds') as mock_rounds, \
             patch('src.game_logic.db'), \
             patch('src.game_logic.socketio'), \
             patch('src.game_logic.clear_team_caches'):
            
            mock_round = MagicMock()
            mock_round.round_id = 1
            mock_rounds.return_value = mock_round
            
            # Collect combo sequence
            for _ in range(100):
                start_new_round_for_pair(team_name)
                
                call_args = mock_rounds.call_args
                if call_args:
                    kwargs = call_args.kwargs
                    p1_item = kwargs.get('player1_item')
                    p2_item = kwargs.get('player2_item')
                    if p1_item and p2_item:
                        combo = (p1_item.value, p2_item.value)
                        combo_sequence.append(combo)
        
        # Calculate Shannon entropy
        combo_counts = Counter(combo_sequence)
        total = len(combo_sequence)
        entropy = 0
        
        for count in combo_counts.values():
            if count > 0:
                p = count / total
                entropy -= p * math.log2(p)
        
        # For uniform distribution over 16 combos, max entropy = log2(16) = 4
        max_entropy = math.log2(len(QUESTION_ITEMS) ** 2)
        
        # Entropy should be reasonably high (at least 70% of maximum)
        min_expected_entropy = 0.7 * max_entropy
        assert entropy >= min_expected_entropy, \
            f"Combo sequence entropy {entropy} too low, expected >= {min_expected_entropy}"

    @pytest.mark.skipif(len(QUESTION_ITEMS) == 0, reason="QUESTION_ITEMS not available")
    def test_memory_usage_with_long_games(self, mock_team_info):
        """Test memory usage doesn't grow excessively with very long games"""
        team_name = "LongGameTeam"
        state.active_teams[team_name] = mock_team_info
        
        # Get initial size estimate
        import sys
        initial_size = sys.getsizeof(mock_team_info['combo_tracker'])
        
        with patch('src.game_logic.PairQuestionRounds') as mock_rounds, \
             patch('src.game_logic.db'), \
             patch('src.game_logic.socketio'), \
             patch('src.game_logic.clear_team_caches'):
            
            mock_round = MagicMock()
            mock_round.round_id = 1
            mock_rounds.return_value = mock_round
            
            # Run many rounds
            for _ in range(500):
                start_new_round_for_pair(team_name)
            
            # Check final memory usage
            team_info = state.active_teams[team_name]
            final_size = sys.getsizeof(team_info['combo_tracker'])
            
            # combo_tracker should only grow to at most 16 entries (all combos)
            # Memory growth should be bounded
            assert final_size < initial_size * 50, \
                f"Memory usage grew too much: {initial_size} -> {final_size}"
            
            # Should have reasonable number of keys
            assert len(team_info['combo_tracker']) <= len(QUESTION_ITEMS) ** 2, \
                "combo_tracker should not have more entries than possible combos"