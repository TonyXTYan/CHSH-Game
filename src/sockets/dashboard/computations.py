"""
Data computation functions for dashboard analytics.

Contains all computational functions for team statistics, correlation matrices, 
success metrics, and data processing.
"""

import math
import hashlib
import logging
from typing import Dict, List, Tuple, Any, Optional
from uncertainties import ufloat, UFloat
import uncertainties.umath as um

from src.models.quiz_models import Teams, Answers, PairQuestionRounds, ItemEnum
from src.state import state
from .cache_system import (
    selective_cache, _hash_cache, _correlation_cache, _success_cache,
    _classic_stats_cache, _new_stats_cache, _team_process_cache, MIN_STD_DEV
)

logger = logging.getLogger(__name__)

def _get_team_id_from_name(team_name: str) -> Optional[int]:
    """Helper function to resolve team_name to team_id from state or database."""
    try:
        # First check active teams
        team_info = state.active_teams.get(team_name)
        if team_info and 'team_id' in team_info:
            return team_info['team_id']
        
        # Fall back to database lookup
        team = Teams.query.filter_by(team_name=team_name).first()
        return team.team_id if team else None
    except Exception as e:
        logger.error(f"Error getting team_id for team_name {team_name}: {str(e)}", exc_info=True)
        return None

@selective_cache(_hash_cache)
def compute_team_hashes(team_name: str) -> Tuple[str, str]:
    """Generate unique history hashes for team data consistency checking."""
    try:
        # Get team_id from team_name
        team_id = _get_team_id_from_name(team_name)
        if team_id is None:
            logger.warning(f"Could not find team_id for team_name: {team_name}")
            return "NO_TEAM", "NO_TEAM"
        
        # Get all rounds and answers for this team in chronological order
        rounds = PairQuestionRounds.query.filter_by(team_id=team_id).order_by(PairQuestionRounds.timestamp_initiated).all()
        answers = Answers.query.filter_by(team_id=team_id).order_by(Answers.timestamp).all()

        # Create history string containing both questions and answers
        history = []
        for round in rounds:
            history.append(f"P1:{round.player1_item.value if round.player1_item else 'None'}")
            history.append(f"P2:{round.player2_item.value if round.player2_item else 'None'}")
        for answer in answers:
            history.append(f"A:{answer.assigned_item.value}:{answer.response_value}")
        
        history_str = "|".join(history)
        
        # Generate two different hashes
        hash1 = hashlib.sha256(history_str.encode()).hexdigest()[:8]
        hash2 = hashlib.md5(history_str.encode()).hexdigest()[:8]
        
        return hash1, hash2
    except Exception as e:
        logger.error(f"Error computing team hashes: {str(e)}")
        return "ERROR", "ERROR"

@selective_cache(_success_cache)
def compute_success_metrics(team_name: str) -> Tuple[List[List[Tuple[int, int]]], List[str], float, float, Dict[Tuple[str, str], int], Dict[Tuple[str, str], int], Dict[str, Dict[str, int]]]:
    """
    Compute success metrics for new mode instead of correlation matrix.
    Returns success rate matrix, overall success metrics, and individual player balance data.
    """
    try:
        # Get team_id from team_name
        team_id = _get_team_id_from_name(team_name)
        if team_id is None:
            logger.warning(f"Could not find team_id for team_name: {team_name}")
            return ([[(0, 0) for _ in range(4)] for _ in range(4)], ['A', 'B', 'X', 'Y'], 0.0, 0.0, {}, {}, {})
        
        # Get all rounds and their corresponding answers for this team
        rounds = PairQuestionRounds.query.filter_by(team_id=team_id).order_by(PairQuestionRounds.timestamp_initiated).all()
        round_map = {round.round_id: round for round in rounds}
        answers = Answers.query.filter_by(team_id=team_id).order_by(Answers.timestamp).all()
        
        # Group answers by round_id
        answers_by_round: Dict[int, List[Any]] = {}
        for answer in answers:
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
        # NEW MODE: Track each player's responses to their assigned question types
        player_responses: Dict[str, Dict[str, int]] = {}  # {item: {'true': count, 'false': count}}
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
        logger.error(f"Error computing success metrics: {str(e)}", exc_info=True)
        return ([[(0, 0) for _ in range(4)] for _ in range(4)], ['A', 'B', 'X', 'Y'], 0.0, 0.0, {}, {}, {})

@selective_cache(_correlation_cache)
def compute_correlation_matrix(team_name: str) -> Tuple[List[List[Tuple[int, int]]], List[str], float, Dict[str, float], Dict[str, Dict[str, int]], Dict[Tuple[str, str], int], Dict[Tuple[str, str], int]]:
    try:
        # Get team_id from team_name
        team_id = _get_team_id_from_name(team_name)
        if team_id is None:
            logger.warning(f"Could not find team_id for team_name: {team_name}")
            return ([[ (0,0) for _ in range(4) ] for _ in range(4)], ['A', 'B', 'X', 'Y'], 0.0, {}, {}, {}, {})
        
        # Get all rounds and their corresponding answers for this team
        # Use separate optimized queries with proper indexing
        rounds = PairQuestionRounds.query.filter_by(team_id=team_id).order_by(PairQuestionRounds.timestamp_initiated).all()
        
        # Create a mapping from round_id to the round object for quick access
        round_map = {round.round_id: round for round in rounds}
        
        # Get all answers for this team with optimized query
        answers = Answers.query.filter_by(team_id=team_id).order_by(Answers.timestamp).all()
        
        # Group answers by round_id
        answers_by_round: Dict[int, List[Any]] = {}
        for answer in answers:
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
        same_item_responses: Dict[str, Dict[str, int]] = {}  # Will track {item: {'true': count, 'false': count}}
        
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
            # Find which answer belongs to which player
            p1_answer = None
            p2_answer = None

            # We've already checked that len(round_answers) == 2
            ans_A = round_answers[0]
            ans_B = round_answers[1]

            if p1_item == p2_item:
                # Both players were assigned the same item.
                # Both answers in round_answers should correspond to this item.
                # We assign one response to p1_answer and the other to p2_answer.
                # The specific order (ans_A to p1 vs. ans_B to p1) doesn't affect
                # the (p1_answer == p2_answer) correlation calculation.
                if ans_A.assigned_item.value == p1_item and ans_B.assigned_item.value == p1_item: # Or p2_item, they are the same
                    p1_answer = ans_A.response_value
                    p2_answer = ans_B.response_value
                    
                    # Track responses for same-item balance metric
                    if p1_item not in same_item_responses:
                        same_item_responses[p1_item] = {'true': 0, 'false': 0}
                    
                    # Count each response separately
                    same_item_responses[p1_item]['true' if p1_answer else 'false'] += 1
                    same_item_responses[p1_item]['true' if p2_answer else 'false'] += 1
                # If assigned_item values don't match, p1_answer/p2_answer might remain None,
                # and the round will be skipped by the check below, which is appropriate for inconsistent data.
            else:
                # p1_item and p2_item are different.
                # Match answers to their respective items.
                if ans_A.assigned_item.value == p1_item and ans_B.assigned_item.value == p2_item:
                    p1_answer = ans_A.response_value
                    p2_answer = ans_B.response_value
                elif ans_A.assigned_item.value == p2_item and ans_B.assigned_item.value == p1_item:
                    # ans_A is for p2_item, ans_B is for p1_item
                    p1_answer = ans_B.response_value 
                    p2_answer = ans_A.response_value
                # If items don't match as expected, p1_answer/p2_answer might remain None,
                # and the round will be skipped by the check below.
            
            # Skip if we don't have both answers (e.g., due to data inconsistency)
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
            avg_same_item_balance = 0.0  # Default if no same-item responses
        
        return (corr_matrix, item_values,
                avg_same_item_balance, same_item_balance, same_item_responses,
                correlation_sums, pair_counts)
    except Exception as e:
        logger.error(f"Error computing correlation matrix: {str(e)}", exc_info=True)
        return ([[ (0,0) for _ in range(4) ] for _ in range(4)],
                ['A', 'B', 'X', 'Y'], 0.0, {}, {}, {}, {})

@selective_cache(_classic_stats_cache)
def _calculate_team_statistics(team_name: str) -> Dict[str, Optional[float]]:
    """Calculate ufloat statistics from correlation matrix for the given team."""
    try:
        # Get correlation matrix data for this team
        correlation_result = compute_correlation_matrix(team_name)
        (corr_matrix_tuples, item_values,
         same_item_balance_avg, same_item_balance, same_item_responses,
         correlation_sums, pair_counts) = correlation_result
        
        # --- Calculate statistics with uncertainties using ufloat ---

        # Stat1: Trace Average Statistic
        sum_of_cii_ufloats: UFloat = ufloat(0, MIN_STD_DEV)  # Use small non-zero std_dev to avoid warning
        if len(corr_matrix_tuples) == 4 and all(len(row) == 4 for row in corr_matrix_tuples):
            for i in range(4):
                num, den = corr_matrix_tuples[i][i]
                if den > 0:
                    c_ii_val = num / den
                    c_ii_val = max(-1.0, min(1.0, c_ii_val))  # Clamp to valid range
                    stdev_ii = 1 / math.sqrt(den)            # σ = 1/√N
                    c_ii_ufloat = ufloat(c_ii_val, stdev_ii)
                else:
                    # No statistics → infinite uncertainty
                    c_ii_ufloat = ufloat(0, float("inf"))
                sum_of_cii_ufloats += c_ii_ufloat
        # Average of the four diagonal correlations
        raw_trace_avg_ufloat = (1 / 4) * sum_of_cii_ufloats
        # Force the magnitude to be positive
        # Handle absolute value without using abs() or um.fabs() which are deprecated
        if raw_trace_avg_ufloat.nominal_value >= 0:
            trace_average_statistic_ufloat = raw_trace_avg_ufloat
        else:
            # Create a new ufloat with positive nominal value but same std_dev
            trace_average_statistic_ufloat = ufloat(-raw_trace_avg_ufloat.nominal_value, raw_trace_avg_ufloat.std_dev)

        # Stat2: CHSH Value Statistic
        chsh_sum_ufloat: UFloat = ufloat(0, MIN_STD_DEV)  # Use small non-zero std_dev to avoid warning
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
                        stdev_ij = 1 / math.sqrt(den)      # σ = 1/√N
                        c_ij_ufloat = ufloat(c_ij_val, stdev_ij)
                    else:
                        c_ij_ufloat = ufloat(0, float("inf"))
                    chsh_sum_ufloat += coeff * c_ij_ufloat
            except ValueError:
                pass  # Already handled by the outer condition check
        chsh_value_statistic_ufloat = (1/2) * chsh_sum_ufloat

        # Stat3: Cross-Term Combination Statistic
        cross_term_sum_ufloat: UFloat = ufloat(0, MIN_STD_DEV)  # Use small non-zero std_dev to avoid warning
        # Ensure item_values contains A,B,X,Y before proceeding
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
                    stdev_t_ij = 1 / math.sqrt(M_ij)       # σ = 1/√N
                    t_ij_ufloat = ufloat(t_ij_val, stdev_t_ij)
                else:
                    t_ij_ufloat = ufloat(0, float("inf"))
                cross_term_sum_ufloat += coeff * t_ij_ufloat
        cross_term_combination_statistic_ufloat = cross_term_sum_ufloat

        # --- Same‑item balance with uncertainty (ufloat) ---
        same_item_balance_ufloats: List[UFloat] = []
        for item, counts in (same_item_responses or {}).items():
            T_count = counts.get('true', 0)
            F_count = counts.get('false', 0)
            total_tf = T_count + F_count
            if total_tf > 0:
                p_val = T_count / total_tf
                var_p = 1 / total_tf  # simplified variance 1/N
                p_true = ufloat(p_val, math.sqrt(var_p))
                p_val2 = 2 * p_true - 1
                if p_val2.nominal_value >= 0:
                    abs_p_val2 = p_val2
                else:
                    abs_p_val2 = ufloat(-p_val2.nominal_value, p_val2.std_dev)
                balance_ufloat = 1 - abs_p_val2
                same_item_balance_ufloats.append(balance_ufloat)
            else:
                # Not enough statistics – propagate infinite uncertainty
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
        logger.error(f"Error calculating team statistics: {str(e)}", exc_info=True)
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

@selective_cache(_new_stats_cache)
def _calculate_success_statistics(team_name: str) -> Dict[str, Optional[float]]:
    """Calculate success statistics for new mode from success metrics for the given team."""
    try:
        # Get success metrics data for this team
        success_result = compute_success_metrics(team_name)
        (success_matrix_tuples, item_values, overall_success_rate, normalized_cumulative_score, 
         success_counts, pair_counts, player_responses) = success_result
        
        # Calculate success statistics with uncertainties using ufloat
        # Replace trace_average_statistic with overall_success_rate
        if overall_success_rate >= 0:
            # Calculate uncertainty based on total number of rounds
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
                # Uncertainty for normalized score based on binomial distribution
                score_uncertainty = 2 / math.sqrt(total_rounds)  # Conservative estimate
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
            # Propagate uncertainty (simplified)
            if cross_term_uncertainties:
                cross_term_uncertainty = math.sqrt(sum(u**2 for u in cross_term_uncertainties)) / len(cross_term_uncertainties)
            else:
                cross_term_uncertainty = None
        else:
            cross_term_avg = 0.0
            cross_term_uncertainty = None
            
        # Calculate individual player balance for NEW mode
        # Balance measures how evenly each player distributes True/False answers for their question types
        individual_balances = []
        
        for item, responses in player_responses.items():
            true_count = responses.get('true', 0)
            false_count = responses.get('false', 0)
            total_responses = true_count + false_count
            
            if total_responses > 0:
                # Calculate balance: 1.0 if perfectly balanced (50/50), 0.0 if all same answer
                balance_ratio = min(true_count, false_count) / total_responses
                # Scale to 0-1 range where 1 is perfect balance (50/50)
                item_balance = balance_ratio * 2  # multiply by 2 to make 0.5 ratio = 1.0 balance
                individual_balances.append(item_balance)
        
        if individual_balances:
            same_item_balance_avg = sum(individual_balances) / len(individual_balances)
            # Simple uncertainty calculation based on variance
            if len(individual_balances) > 1:
                variance = sum((b - same_item_balance_avg)**2 for b in individual_balances) / len(individual_balances)
                same_item_balance_uncertainty = math.sqrt(variance)
            else:
                same_item_balance_uncertainty = None
        else:
            same_item_balance_avg = 0.0
            same_item_balance_uncertainty = None
        
        return {
            'trace_average_statistic': overall_success_rate,  # Replace with overall success rate
            'trace_average_statistic_uncertainty': success_rate_uncertainty,
            'chsh_value_statistic': normalized_cumulative_score,  # Replace with normalized score
            'chsh_value_statistic_uncertainty': score_uncertainty,
            'cross_term_combination_statistic': cross_term_avg,
            'cross_term_combination_statistic_uncertainty': cross_term_uncertainty,
            'same_item_balance': same_item_balance_avg,
            'same_item_balance_uncertainty': same_item_balance_uncertainty
        }
    except Exception as e:
        logger.error(f"Error calculating success statistics: {str(e)}", exc_info=True)
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