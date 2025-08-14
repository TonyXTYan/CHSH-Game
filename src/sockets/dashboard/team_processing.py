"""
Team data processing functions for dashboard.

Contains functions for processing team data, optimized computation functions,
and the main get_all_teams function.
"""

import hashlib
import logging
from time import time
from typing import Dict, List, Tuple, Any, Optional

from src.config import app
from src.models.quiz_models import Teams, Answers, PairQuestionRounds, ItemEnum
from src.state import state
from src.game_logic import QUESTION_ITEMS, TARGET_COMBO_REPEATS
from .cache_system import (
    selective_cache, _team_process_cache, _safe_dashboard_operation,
    REFRESH_DELAY_QUICK, _last_refresh_time, _cached_teams_result
)
from .computations import (
    compute_team_hashes, compute_correlation_matrix, compute_success_metrics,
    _calculate_team_statistics, _calculate_success_statistics
)

logger = logging.getLogger(__name__)

def _compute_team_hashes_optimized(team_id: int, team_rounds: List[Any], team_answers: List[Any]) -> Tuple[str, str]:
    """Generate unique history hashes for team data consistency checking using pre-fetched data."""
    try:
        # Create history string containing both questions and answers using pre-fetched data
        history = []
        for round_obj in team_rounds:
            history.append(f"P1:{round_obj.player1_item.value if round_obj.player1_item else 'None'}")
            history.append(f"P2:{round_obj.player2_item.value if round_obj.player2_item else 'None'}")
        for answer in team_answers:
            history.append(f"A:{answer.assigned_item.value}:{answer.response_value}")
        
        history_str = "|".join(history)
        
        # Generate two different hashes
        hash1 = hashlib.sha256(history_str.encode()).hexdigest()[:8]
        hash2 = hashlib.md5(history_str.encode()).hexdigest()[:8]
        
        return hash1, hash2
    except Exception as e:
        logger.error(f"Error computing team hashes for team {team_id}: {str(e)}")
        return "ERROR", "ERROR"

def _compute_correlation_matrix_optimized(team_id: int, team_rounds: List[Any], team_answers: List[Any]) -> Tuple[List[List[Tuple[int, int]]], List[str], float, Dict[str, float], Dict[str, Dict[str, int]], Dict[Tuple[str, str], int], Dict[Tuple[str, str], int]]:
    """Compute correlation matrix using pre-fetched rounds and answers data."""
    try:
        # Create a mapping from round_id to the round object for quick access
        round_map = {round_obj.round_id: round_obj for round_obj in team_rounds}
        
        # Group answers by round_id
        answers_by_round: Dict[int, List[Any]] = {}
        for answer in team_answers:
            if answer.question_round_id not in answers_by_round:
                answers_by_round[answer.question_round_id] = []
            answers_by_round[answer.question_round_id].append(answer)
        
        # Prepare the 4x4 correlation matrix for A, B, X, Y combinations
        item_values = ['A', 'B', 'X', 'Y']
        # corr_matrix will store (numerator, denominator) tuples
        corr_matrix = [[(0, 0) for _ in range(4)] for _ in range(4)]
        
        # Count pairs for each item combination
        pair_counts: Dict[Tuple[str, str], int] = {(i, j): 0 for i in item_values for j in item_values}
        correlation_sums: Dict[Tuple[str, str], int] = {(i, j): 0 for i in item_values for j in item_values}
        
        # Track same-item responses for the new metric
        same_item_responses: Dict[str, Dict[str, int]] = {}
        
        # Analyze each round that has both player answers
        for round_id, round_answers in answers_by_round.items():
            # Skip if we don't have exactly 2 answers (one from each player)
            if len(round_answers) != 2 or round_id not in round_map:
                continue
                
            round_obj = round_map[round_id]
            p1_item = round_obj.player1_item.value if round_obj.player1_item else None
            p2_item = round_obj.player2_item.value if round_obj.player2_item else None
            
            # Skip if we don't have both items
            if not p1_item or not p2_item:
                continue
                
            # Get player responses (True/False)
            p1_answer = None
            p2_answer = None

            ans_A = round_answers[0]
            ans_B = round_answers[1]

            if p1_item == p2_item:
                # Both players were assigned the same item
                if ans_A.assigned_item.value == p1_item and ans_B.assigned_item.value == p1_item:
                    p1_answer = ans_A.response_value
                    p2_answer = ans_B.response_value
                    
                    # Track responses for same-item balance metric
                    if p1_item not in same_item_responses:
                        same_item_responses[p1_item] = {'true': 0, 'false': 0}
                    
                    # Count each response separately
                    same_item_responses[p1_item]['true' if p1_answer else 'false'] += 1
                    same_item_responses[p1_item]['true' if p2_answer else 'false'] += 1
            else:
                # p1_item and p2_item are different
                if ans_A.assigned_item.value == p1_item and ans_B.assigned_item.value == p2_item:
                    p1_answer = ans_A.response_value
                    p2_answer = ans_B.response_value
                elif ans_A.assigned_item.value == p2_item and ans_B.assigned_item.value == p1_item:
                    p1_answer = ans_B.response_value 
                    p2_answer = ans_A.response_value
            
            # Skip if we don't have both answers
            if p1_answer is None or p2_answer is None:
                continue
                
            # Calculate correlation: (T,T) or (F,F) count as 1, (T,F) or (F,T) count as -1
            correlation = 1 if p1_answer == p2_answer else -1
            
            pair_counts[(p1_item, p2_item)] += 1
            correlation_sums[(p1_item, p2_item)] += correlation
        
        # Populate the corr_matrix with (numerator, denominator) tuples
        for i, row_item in enumerate(item_values):
            for j, col_item in enumerate(item_values):
                numerator = correlation_sums.get((row_item, col_item), 0)
                denominator = pair_counts.get((row_item, col_item), 0)
                corr_matrix[i][j] = (numerator, denominator)
        
        # Calculate the same-item balance metric
        same_item_balance: Dict[str, float] = {}
        for item, counts in same_item_responses.items():
            total = counts['true'] + counts['false']
            if total == 0:
                same_item_balance[item] = 0.0
            else:
                diff = abs(counts['true'] - counts['false'])
                same_item_balance[item] = 1.0 - diff / total
        
        # Calculate the average balance across all same items
        if same_item_responses:
            avg_same_item_balance = sum(same_item_balance.values()) / len(same_item_balance)
        else:
            avg_same_item_balance = 0.0
        
        return (corr_matrix, item_values,
                avg_same_item_balance, same_item_balance, same_item_responses,
                correlation_sums, pair_counts)
    except Exception as e:
        logger.error(f"Error computing correlation matrix for team {team_id}: {str(e)}", exc_info=True)
        return ([[ (0,0) for _ in range(4) ] for _ in range(4)],
                ['A', 'B', 'X', 'Y'], 0.0, {}, {}, {}, {})

def _compute_success_metrics_optimized(team_id: int, team_rounds: List[Any], team_answers: List[Any]) -> Tuple[List[List[Tuple[int, int]]], List[str], float, float, Dict[Tuple[str, str], int], Dict[Tuple[str, str], int], Dict[str, Dict[str, int]]]:
    """Compute success metrics for new mode using pre-fetched rounds and answers data."""
    try:
        # Create a mapping from round_id to the round object for quick access
        round_map = {round_obj.round_id: round_obj for round_obj in team_rounds}
        
        # Group answers by round_id
        answers_by_round: Dict[int, List[Any]] = {}
        for answer in team_answers:
            if answer.question_round_id not in answers_by_round:
                answers_by_round[answer.question_round_id] = []
            answers_by_round[answer.question_round_id].append(answer)
        
        # Initialize success metrics
        item_values = ['A', 'B', 'X', 'Y']
        success_matrix = [[(0, 0) for _ in range(4)] for _ in range(4)]  # (successful_rounds, total_rounds)
        
        # Count pairs for each item combination
        pair_counts: Dict[Tuple[str, str], int] = {(i, j): 0 for i in item_values for j in item_values}
        success_counts: Dict[Tuple[str, str], int] = {(i, j): 0 for i in item_values for j in item_values}
        
        # Track individual player responses for balance calculation
        player_responses: Dict[str, Dict[str, int]] = {}
        for item in item_values:
            player_responses[item] = {'true': 0, 'false': 0}
        
        total_rounds = 0
        successful_rounds = 0
        
        # Analyze each round that has both player answers
        for round_id, round_answers in answers_by_round.items():
            # Skip if we don't have exactly 2 answers (one from each player)
            if len(round_answers) != 2 or round_id not in round_map:
                continue
                
            round_obj = round_map[round_id]
            p1_item = round_obj.player1_item.value if round_obj.player1_item else None
            p2_item = round_obj.player2_item.value if round_obj.player2_item else None
            
            # Skip if we don't have both items
            if not p1_item or not p2_item:
                continue
                
            # Get player responses
            p1_answer = None
            p2_answer = None

            ans_A = round_answers[0]
            ans_B = round_answers[1]

            if p1_item == p2_item:
                # Both players were assigned the same item
                if ans_A.assigned_item.value == p1_item and ans_B.assigned_item.value == p1_item:
                    p1_answer = ans_A.response_value
                    p2_answer = ans_B.response_value
            else:
                # Different items
                if ans_A.assigned_item.value == p1_item and ans_B.assigned_item.value == p2_item:
                    p1_answer = ans_A.response_value
                    p2_answer = ans_B.response_value
                elif ans_A.assigned_item.value == p2_item and ans_B.assigned_item.value == p1_item:
                    p1_answer = ans_B.response_value 
                    p2_answer = ans_A.response_value
            
            # Skip if we don't have both answers
            if p1_answer is None or p2_answer is None:
                continue
                
            # Track individual player responses for balance calculation
            player_responses[p1_item]['true' if p1_answer else 'false'] += 1
            player_responses[p2_item]['true' if p2_answer else 'false'] += 1
                
            # Apply success rules for new mode
            # Success Rule: {B,Y} combinations require different answers; all others require same answers
            is_by_combination = (p1_item == 'B' and p2_item == 'Y') or (p1_item == 'Y' and p2_item == 'B')
            players_answered_differently = p1_answer != p2_answer
            
            if is_by_combination:
                # B,Y combination: players should answer differently
                is_successful = players_answered_differently
            else:
                # All other combinations: players should answer the same
                is_successful = not players_answered_differently
            
            # Update counts
            total_rounds += 1
            if is_successful:
                successful_rounds += 1
                success_counts[(p1_item, p2_item)] += 1
            
            pair_counts[(p1_item, p2_item)] += 1
        
        # Populate the success matrix with (successful, total) tuples
        for i, row_item in enumerate(item_values):
            for j, col_item in enumerate(item_values):
                successful = success_counts.get((row_item, col_item), 0)
                total = pair_counts.get((row_item, col_item), 0)
                success_matrix[i][j] = (successful, total)
        
        # Calculate overall success rate and normalized score
        overall_success_rate = successful_rounds / total_rounds if total_rounds > 0 else 0.0
        
        # Normalized cumulative score: +1 for success, -1 for failure, divided by total rounds
        score_sum = successful_rounds - (total_rounds - successful_rounds)  # successful - failed
        normalized_cumulative_score = score_sum / total_rounds if total_rounds > 0 else 0.0
        
        return (success_matrix, item_values, overall_success_rate, normalized_cumulative_score, success_counts, pair_counts, player_responses)
        
    except Exception as e:
        logger.error(f"Error computing success metrics for team {team_id}: {str(e)}", exc_info=True)
        return ([[(0, 0) for _ in range(4)] for _ in range(4)], ['A', 'B', 'X', 'Y'], 0.0, 0.0, {}, {}, {})

def _calculate_team_statistics_from_data(correlation_result: Tuple) -> Dict[str, Optional[float]]:
    """Calculate classic mode statistics using pre-computed correlation data."""
    try:
        from .computations import MIN_STD_DEV
        import math
        from uncertainties import ufloat, UFloat
        
        (corr_matrix_tuples, item_values,
         same_item_balance_avg, same_item_balance, same_item_responses,
         correlation_sums, pair_counts) = correlation_result
        
        # Same logic as _calculate_team_statistics but using pre-computed data
        # [Previous implementation from original function]
        
        # Stat1: Trace Average Statistic
        sum_of_cii_ufloats: UFloat = ufloat(0, MIN_STD_DEV)
        if len(corr_matrix_tuples) == 4 and all(len(row) == 4 for row in corr_matrix_tuples):
            for i in range(4):
                num, den = corr_matrix_tuples[i][i]
                if den > 0:
                    c_ii_val = num / den
                    c_ii_val = max(-1.0, min(1.0, c_ii_val))
                    stdev_ii = 1 / math.sqrt(den)
                    c_ii_ufloat = ufloat(c_ii_val, stdev_ii)
                else:
                    c_ii_ufloat = ufloat(0, float("inf"))
                sum_of_cii_ufloats += c_ii_ufloat
        
        raw_trace_avg_ufloat = (1 / 4) * sum_of_cii_ufloats
        if raw_trace_avg_ufloat.nominal_value >= 0:
            trace_average_statistic_ufloat = raw_trace_avg_ufloat
        else:
            trace_average_statistic_ufloat = ufloat(-raw_trace_avg_ufloat.nominal_value, raw_trace_avg_ufloat.std_dev)

        # Stat2: CHSH Value Statistic
        chsh_sum_ufloat: UFloat = ufloat(0, MIN_STD_DEV)
        if len(corr_matrix_tuples) == 4 and all(len(row) == 4 for row in corr_matrix_tuples) and all(item in item_values for item in ['A', 'B', 'X', 'Y']):
            try:
                A_idx = item_values.index('A')
                B_idx = item_values.index('B')
                X_idx = item_values.index('X')
                Y_idx = item_values.index('Y')

                terms_indices_coeffs = [
                    (A_idx, X_idx, 1), (A_idx, Y_idx, 1),
                    (B_idx, X_idx, 1), (B_idx, Y_idx, -1),
                    (X_idx, A_idx, 1), (X_idx, B_idx, 1),
                    (Y_idx, A_idx, 1), (Y_idx, B_idx, -1)
                ]

                for r_idx, c_idx, coeff in terms_indices_coeffs:
                    num, den = corr_matrix_tuples[r_idx][c_idx]
                    if den > 0:
                        c_ij_val = num / den
                        c_ij_val = max(-1.0, min(1.0, c_ij_val))
                        stdev_ij = 1 / math.sqrt(den)
                        c_ij_ufloat = ufloat(c_ij_val, stdev_ij)
                    else:
                        c_ij_ufloat = ufloat(0, float("inf"))
                    chsh_sum_ufloat += coeff * c_ij_ufloat
            except ValueError:
                pass
        chsh_value_statistic_ufloat = (1/2) * chsh_sum_ufloat

        # Stat3: Cross-Term Combination Statistic
        cross_term_sum_ufloat: UFloat = ufloat(0, MIN_STD_DEV)
        if all(item in item_values for item in ['A', 'B', 'X', 'Y']):
            term_item_pairs_coeffs = [
                ('A', 'X', 1), ('A', 'Y', 1),
                ('B', 'X', 1), ('B', 'Y', -1)
            ]
            for item1, item2, coeff in term_item_pairs_coeffs:
                M_ij = pair_counts.get((item1, item2), 0) + pair_counts.get((item2, item1), 0)
                if M_ij > 0:
                    N_ij_sum_prod = correlation_sums.get((item1, item2), 0) + correlation_sums.get((item2, item1), 0)
                    t_ij_val = N_ij_sum_prod / M_ij
                    t_ij_val = max(-1.0, min(1.0, t_ij_val))
                    stdev_t_ij = 1 / math.sqrt(M_ij)
                    t_ij_ufloat = ufloat(t_ij_val, stdev_t_ij)
                else:
                    t_ij_ufloat = ufloat(0, float("inf"))
                cross_term_sum_ufloat += coeff * t_ij_ufloat
        cross_term_combination_statistic_ufloat = cross_term_sum_ufloat

        # Same-item balance with uncertainty
        same_item_balance_ufloats: List[UFloat] = []
        for item, counts in (same_item_responses or {}).items():
            T_count = counts.get('true', 0)
            F_count = counts.get('false', 0)
            total_tf = T_count + F_count
            if total_tf > 0:
                p_val = T_count / total_tf
                var_p = 1 / total_tf
                p_true = ufloat(p_val, math.sqrt(var_p))
                p_val2 = 2 * p_true - 1
                if p_val2.nominal_value >= 0:
                    abs_p_val2 = p_val2
                else:
                    abs_p_val2 = ufloat(-p_val2.nominal_value, p_val2.std_dev)
                balance_ufloat = 1 - abs_p_val2
                same_item_balance_ufloats.append(balance_ufloat)
            else:
                balance_ufloat = ufloat(0, float("inf"))
                same_item_balance_ufloats.append(balance_ufloat)

        if same_item_balance_ufloats:
            avg_same_item_balance_ufloat = sum(same_item_balance_ufloats) / len(same_item_balance_ufloats)
        else:
            avg_same_item_balance_ufloat = ufloat(0, float("inf"))
        
        return {
            'trace_average_statistic': trace_average_statistic_ufloat.nominal_value,
            'trace_average_statistic_uncertainty': trace_average_statistic_ufloat.std_dev if not math.isinf(trace_average_statistic_ufloat.std_dev) else None,
            'chsh_value_statistic': chsh_value_statistic_ufloat.nominal_value,
            'chsh_value_statistic_uncertainty': chsh_value_statistic_ufloat.std_dev if not math.isinf(chsh_value_statistic_ufloat.std_dev) else None,
            'cross_term_combination_statistic': cross_term_combination_statistic_ufloat.nominal_value,
            'cross_term_combination_statistic_uncertainty': cross_term_combination_statistic_ufloat.std_dev if not math.isinf(cross_term_combination_statistic_ufloat.std_dev) else None,
            'same_item_balance': avg_same_item_balance_ufloat.nominal_value,
            'same_item_balance_uncertainty': (avg_same_item_balance_ufloat.std_dev
                                              if not math.isinf(avg_same_item_balance_ufloat.std_dev) else None)
        }
    except Exception as e:
        logger.error(f"Error calculating team statistics from data: {str(e)}", exc_info=True)
        return {
            'trace_average_statistic': 0.0,
            'trace_average_statistic_uncertainty': None,
            'chsh_value_statistic': 0.0,
            'chsh_value_statistic_uncertainty': None,
            'cross_term_combination_statistic': 0.0,
            'cross_term_combination_statistic_uncertainty': None,
            'same_item_balance': 0.0,
            'same_item_balance_uncertainty': None
        }

def _calculate_success_statistics_from_data(success_result: Tuple) -> Dict[str, Optional[float]]:
    """Calculate new mode statistics using pre-computed success data."""
    try:
        import math
        
        (success_matrix_tuples, item_values, overall_success_rate, normalized_cumulative_score, 
         success_counts, pair_counts, player_responses) = success_result
        
        # Calculate success statistics with uncertainties using ufloat
        # Replace trace_average_statistic with overall_success_rate
        if overall_success_rate >= 0:
            total_rounds = sum(pair_counts.values())
            if total_rounds > 0:
                success_rate_uncertainty = math.sqrt(overall_success_rate * (1 - overall_success_rate) / total_rounds)
            else:
                success_rate_uncertainty = None
        else:
            success_rate_uncertainty = None
            
        # Replace chsh_value_statistic with normalized_cumulative_score  
        if normalized_cumulative_score is not None:
            total_rounds = sum(pair_counts.values())
            if total_rounds > 0:
                score_uncertainty = 2 / math.sqrt(total_rounds)
            else:
                score_uncertainty = None
        else:
            score_uncertainty = None
            
        # Calculate cross-term combination statistic as average success rate across specific pairs
        cross_term_pairs = [('A', 'X'), ('A', 'Y'), ('B', 'X'), ('B', 'Y')]
        cross_term_success_rates = []
        cross_term_uncertainties = []
        
        for item1, item2 in cross_term_pairs:
            total_pair = pair_counts.get((item1, item2), 0) + pair_counts.get((item2, item1), 0)
            successful_pair = success_counts.get((item1, item2), 0) + success_counts.get((item2, item1), 0)
            
            if total_pair > 0:
                pair_success_rate = successful_pair / total_pair
                pair_uncertainty = math.sqrt(pair_success_rate * (1 - pair_success_rate) / total_pair)
                cross_term_success_rates.append(pair_success_rate)
                cross_term_uncertainties.append(pair_uncertainty)
        
        if cross_term_success_rates:
            cross_term_avg = sum(cross_term_success_rates) / len(cross_term_success_rates)
            if cross_term_uncertainties:
                cross_term_uncertainty = math.sqrt(sum(u**2 for u in cross_term_uncertainties)) / len(cross_term_uncertainties)
            else:
                cross_term_uncertainty = None
        else:
            cross_term_avg = 0.0
            cross_term_uncertainty = None
            
        # Calculate individual player balance for NEW mode
        individual_balances = []
        
        for item, responses in player_responses.items():
            true_count = responses.get('true', 0)
            false_count = responses.get('false', 0)
            total_responses = true_count + false_count
            
            if total_responses > 0:
                balance_ratio = min(true_count, false_count) / total_responses
                item_balance = balance_ratio * 2
                individual_balances.append(item_balance)
        
        if individual_balances:
            same_item_balance_avg = sum(individual_balances) / len(individual_balances)
            if len(individual_balances) > 1:
                variance = sum((b - same_item_balance_avg)**2 for b in individual_balances) / len(individual_balances)
                same_item_balance_uncertainty = math.sqrt(variance)
            else:
                same_item_balance_uncertainty = None
        else:
            same_item_balance_avg = 0.0
            same_item_balance_uncertainty = None
        
        return {
            'trace_average_statistic': overall_success_rate,
            'trace_average_statistic_uncertainty': success_rate_uncertainty,
            'chsh_value_statistic': normalized_cumulative_score,
            'chsh_value_statistic_uncertainty': score_uncertainty,
            'cross_term_combination_statistic': cross_term_avg,
            'cross_term_combination_statistic_uncertainty': cross_term_uncertainty,
            'same_item_balance': same_item_balance_avg,
            'same_item_balance_uncertainty': same_item_balance_uncertainty
        }
    except Exception as e:
        logger.error(f"Error calculating success statistics from data: {str(e)}", exc_info=True)
        return {
            'trace_average_statistic': 0.0,
            'trace_average_statistic_uncertainty': None,
            'chsh_value_statistic': 0.0,
            'chsh_value_statistic_uncertainty': None,
            'cross_term_combination_statistic': 0.0,
            'cross_term_combination_statistic_uncertainty': None,
            'same_item_balance': 0.0,
            'same_item_balance_uncertainty': None
        }

def _process_single_team_optimized(team_id: int, team_name: str, is_active: bool, created_at: Optional[str], current_round: int, player1_sid: Optional[str], player2_sid: Optional[str], team_rounds: List[Any], team_answers: List[Any]) -> Optional[Dict[str, Any]]:
    """
    Process all heavy computation for a single team using pre-fetched data.
    OPTIMIZATION: Uses pre-fetched rounds and answers to avoid database queries.
    """
    try:
        # For active teams, check game progress
        team_info = state.active_teams.get(team_name)
        
        # Mode-specific combo calculation for min_stats_sig
        if state.game_mode == 'new':
            # New mode: Only A,B x X,Y combinations are possible (Player 1: A/B, Player 2: X/Y)
            player1_items = [ItemEnum.A, ItemEnum.B]
            player2_items = [ItemEnum.X, ItemEnum.Y]
            all_combos = [(i1.value, i2.value) for i1 in player1_items for i2 in player2_items]
        else:
            # Classic mode: All combinations possible
            all_combos = [(i1.value, i2.value) for i1 in QUESTION_ITEMS for i2 in QUESTION_ITEMS]
            
        combo_tracker = team_info.get('combo_tracker', {}) if team_info else {}
        min_stats_sig = all(combo_tracker.get(combo, 0) >= TARGET_COMBO_REPEATS
                        for combo in all_combos) if team_info else False
        
        # Get players list
        players = team_info['players'] if team_info else []

        # Compute hashes for the team using pre-fetched data
        hash1, hash2 = _compute_team_hashes_optimized(team_id, team_rounds, team_answers)
        
        # ALWAYS compute both classic and new statistics for details modal
        # Get correlation matrix and success metrics data using pre-fetched data
        correlation_result = _compute_correlation_matrix_optimized(team_id, team_rounds, team_answers)
        (corr_matrix_tuples, item_values,
         same_item_balance_avg, same_item_balance, same_item_responses,
         correlation_sums, pair_counts) = correlation_result
        
        success_result = _compute_success_metrics_optimized(team_id, team_rounds, team_answers)
        (success_matrix_tuples, success_item_values, overall_success_rate, normalized_cumulative_score, 
         success_counts, success_pair_counts, player_responses) = success_result
        
        # Calculate statistics using pre-computed correlation and success data
        classic_stats = _calculate_team_statistics_from_data(correlation_result)
        new_stats = _calculate_success_statistics_from_data(success_result)
        
        # Determine which matrix and stats to use for the main display based on game mode
        if state.game_mode == 'new':
            display_matrix = success_matrix_tuples
            display_labels = success_item_values
            display_stats = new_stats
        else:
            display_matrix = corr_matrix_tuples
            display_labels = item_values
            display_stats = classic_stats
        
        team_data = {
            'team_name': team_name,
            'team_id': team_id,
            'is_active': is_active,
            'player1_sid': player1_sid,
            'player2_sid': player2_sid,
            'current_round_number': current_round,
            'history_hash1': hash1,
            'history_hash2': hash2,
            'min_stats_sig': min_stats_sig,
            'correlation_matrix': display_matrix,
            'correlation_labels': display_labels,
            'correlation_stats': display_stats,  # Current mode stats for main display
            'classic_stats': classic_stats,      # Always include classic stats for details modal
            'new_stats': new_stats,              # Always include new stats for details modal
            'classic_matrix': corr_matrix_tuples,    # Classic correlation matrix for details modal
            'new_matrix': success_matrix_tuples,     # New success matrix for details modal
            'created_at': created_at,
            'game_mode': state.game_mode  # Include current mode
        }
        
        # Add status field for active teams
        if team_info and 'status' in team_info:
            team_data['status'] = team_info['status']
        elif is_active and len(players) < 2:
            team_data['status'] = 'waiting_pair'
        elif is_active:
            team_data['status'] = 'active'
        else:
            team_data['status'] = 'inactive'
            
        return team_data
    except Exception as e:
        logger.error(f"Error processing team {team_id}: {str(e)}", exc_info=True)
        return None

@selective_cache(_team_process_cache)
def _process_single_team(team_id: int, team_name: str, is_active: bool, created_at: Optional[str], current_round: int, player1_sid: Optional[str], player2_sid: Optional[str]) -> Optional[Dict[str, Any]]:
    """Process all heavy computation for a single team."""
    try:
        # For active teams, check game progress
        team_info = state.active_teams.get(team_name)
        
        # Mode-specific combo calculation for min_stats_sig
        if state.game_mode == 'new':
            # New mode: Only A,B x X,Y combinations are possible (Player 1: A/B, Player 2: X/Y)
            player1_items = [ItemEnum.A, ItemEnum.B]
            player2_items = [ItemEnum.X, ItemEnum.Y]
            all_combos = [(i1.value, i2.value) for i1 in player1_items for i2 in player2_items]
        else:
            # Classic mode: All combinations possible
            all_combos = [(i1.value, i2.value) for i1 in QUESTION_ITEMS for i2 in QUESTION_ITEMS]
            
        combo_tracker = team_info.get('combo_tracker', {}) if team_info else {}
        min_stats_sig = all(combo_tracker.get(combo, 0) >= TARGET_COMBO_REPEATS
                        for combo in all_combos) if team_info else False
        
        # Get players list
        players = team_info['players'] if team_info else []

        # Compute hashes for the team
        hash1, hash2 = compute_team_hashes(team_name)
        
        # ALWAYS compute both classic and new statistics for details modal
        # Get correlation matrix and success metrics data (cached by team name)
        correlation_result = compute_correlation_matrix(team_name)
        (corr_matrix_tuples, item_values,
         same_item_balance_avg, same_item_balance, same_item_responses,
         correlation_sums, pair_counts) = correlation_result
        
        success_result = compute_success_metrics(team_name)
        (success_matrix_tuples, success_item_values, overall_success_rate, normalized_cumulative_score, 
         success_counts, success_pair_counts, player_responses) = success_result
        
        # Calculate statistics (cached by team name)
        classic_stats = _calculate_team_statistics(team_name)
        new_stats = _calculate_success_statistics(team_name)
        
        # Determine which matrix and stats to use for the main display based on game mode
        if state.game_mode == 'new':
            display_matrix = success_matrix_tuples
            display_labels = success_item_values
            display_stats = new_stats
        else:
            display_matrix = corr_matrix_tuples
            display_labels = item_values
            display_stats = classic_stats
        
        team_data = {
            'team_name': team_name,
            'team_id': team_id,
            'is_active': is_active,
            'player1_sid': player1_sid,
            'player2_sid': player2_sid,
            'current_round_number': current_round,
            'history_hash1': hash1,
            'history_hash2': hash2,
            'min_stats_sig': min_stats_sig,
            'correlation_matrix': display_matrix,
            'correlation_labels': display_labels,
            'correlation_stats': display_stats,  # Current mode stats for main display
            'classic_stats': classic_stats,      # Always include classic stats for details modal
            'new_stats': new_stats,              # Always include new stats for details modal
            'classic_matrix': corr_matrix_tuples,    # Classic correlation matrix for details modal
            'new_matrix': success_matrix_tuples,     # New success matrix for details modal
            'created_at': created_at,
            'game_mode': state.game_mode  # Include current mode
        }
        
        # Add status field for active teams
        if team_info and 'status' in team_info:
            team_data['status'] = team_info['status']
        elif is_active and len(players) < 2:
            team_data['status'] = 'waiting_pair'
        elif is_active:
            team_data['status'] = 'active'
        else:
            team_data['status'] = 'inactive'
            
        return team_data
    except Exception as e:
        logger.error(f"Error processing team {team_id}: {str(e)}", exc_info=True)
        return None

def get_all_teams() -> List[Dict[str, Any]]:
    """
    Retrieve and serialize all team data with throttling for performance.
    Returns cached result if called within REFRESH_DELAY_QUICK seconds.
    Thread-safe with proper error handling and lock management.
    
    OPTIMIZATION: Uses bulk queries to prevent N+1 database query problem.
    """
    global _last_refresh_time, _cached_teams_result
    
    try:
        with _safe_dashboard_operation():
            # Check if we should throttle the request
            current_time = time()
            time_since_last_refresh = current_time - _last_refresh_time
            
            # Throttle all calls with REFRESH_DELAY_QUICK
            if time_since_last_refresh < REFRESH_DELAY_QUICK and _cached_teams_result is not None:
                # logger.debug("Returning cached team data")
                return _cached_teams_result
            
            # logger.debug("Computing fresh team data")
            
            # OPTIMIZATION: Bulk fetch all data to prevent N+1 queries
            # Fetch all teams
            all_teams = Teams.query.all()
            
            if not all_teams:
                _cached_teams_result = []
                _last_refresh_time = current_time
                return []
            
            # Extract team IDs for bulk queries
            team_ids = [team.team_id for team in all_teams]
            
            # Bulk fetch all rounds and answers for all teams
            all_rounds = PairQuestionRounds.query.filter(
                PairQuestionRounds.team_id.in_(team_ids)
            ).order_by(PairQuestionRounds.team_id, PairQuestionRounds.timestamp_initiated).all()
            
            all_answers = Answers.query.filter(
                Answers.team_id.in_(team_ids)
            ).order_by(Answers.team_id, Answers.timestamp).all()
            
            # Group data by team_id for efficient lookup
            rounds_by_team = {}
            answers_by_team = {}
            
            for round_obj in all_rounds:
                if round_obj.team_id not in rounds_by_team:
                    rounds_by_team[round_obj.team_id] = []
                rounds_by_team[round_obj.team_id].append(round_obj)
            
            for answer in all_answers:
                if answer.team_id not in answers_by_team:
                    answers_by_team[answer.team_id] = []
                answers_by_team[answer.team_id].append(answer)
            
            # Process teams using pre-fetched data
            teams_list = []
            
            for team in all_teams:
                # Get active team info from state if available
                team_info = state.active_teams.get(team.team_name)
                
                # Get players from either active state or database
                players = team_info['players'] if team_info else []
                current_round = team_info.get('current_round_number', 0) if team_info else 0
                
                # Get pre-fetched data for this team
                team_rounds = rounds_by_team.get(team.team_id, [])
                team_answers = answers_by_team.get(team.team_id, [])
                
                # Use optimized helper function with pre-fetched data
                team_data = _process_single_team_optimized(
                    team.team_id,
                    team.team_name,
                    team.is_active,
                    team.created_at.isoformat() if team.created_at else None,
                    current_round,
                    players[0] if len(players) > 0 else None,
                    players[1] if len(players) > 1 else None,
                    team_rounds,
                    team_answers
                )
                
                if team_data:
                    teams_list.append(team_data)
            
            # Update cache and timestamp
            _cached_teams_result = teams_list
            _last_refresh_time = current_time
            
            return teams_list
    except Exception as e:
        logger.error(f"Error in get_all_teams: {str(e)}", exc_info=True)
        return []