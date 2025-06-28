import math
import logging
from typing import Dict, List, Tuple, Any, Optional
from uncertainties import ufloat, UFloat
import uncertainties.umath as um
from .cache_management import (
    selective_cache, _classic_stats_cache, _new_stats_cache, MIN_STD_DEV
)
from .team_data import (
    compute_correlation_matrix, compute_success_metrics,
    _compute_correlation_matrix_optimized, _compute_success_metrics_optimized
)

# Configure logging
logger = logging.getLogger(__name__)

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

def _calculate_team_statistics_from_data(correlation_result: Tuple) -> Dict[str, Optional[float]]:
    """Calculate ufloat statistics from pre-computed correlation matrix data."""
    try:
        (corr_matrix_tuples, item_values,
         same_item_balance_avg, same_item_balance, same_item_responses,
         correlation_sums, pair_counts) = correlation_result
        
        # Use the same logic as _calculate_team_statistics but with pre-computed data
        # --- Calculate statistics with uncertainties using ufloat ---

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

        # Same‑item balance with uncertainty (ufloat)
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
    """Calculate success statistics for new mode from pre-computed success metrics data."""
    try:
        (success_matrix_tuples, item_values, overall_success_rate, normalized_cumulative_score, 
         success_counts, pair_counts, player_responses) = success_result
        
        # Calculate success statistics with uncertainties using ufloat
        if overall_success_rate >= 0:
            total_rounds = sum(pair_counts.values())
            if total_rounds > 0:
                success_rate_uncertainty = math.sqrt(overall_success_rate * (1 - overall_success_rate) / total_rounds)
            else:
                success_rate_uncertainty = None
        else:
            success_rate_uncertainty = None
            
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