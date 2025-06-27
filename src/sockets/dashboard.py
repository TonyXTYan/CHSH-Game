from flask import jsonify, Response
import math
from uncertainties import ufloat, UFloat
import uncertainties.umath as um  # for ufloat‑compatible fabs
from functools import lru_cache
from sqlalchemy.orm import joinedload
from src.config import app, socketio, db
from src.state import state
from src.models.quiz_models import Teams, Answers, PairQuestionRounds, ItemEnum
from src.game_logic import QUESTION_ITEMS, TARGET_COMBO_REPEATS
from flask_socketio import emit
from src.game_logic import start_new_round_for_pair
from time import time
import hashlib
import csv
import io
import logging
from datetime import datetime
from typing import Dict, List, Tuple, Any, Optional, Union
from flask import request

# Configure logging
logger = logging.getLogger(__name__)

# Store last activity time for each dashboard client
dashboard_last_activity: Dict[str, float] = {}

# Store teams streaming preference for each dashboard client
dashboard_teams_streaming: Dict[str, bool] = {}

CACHE_SIZE = 1024  # Adjust cache size as needed
REFRESH_DELAY = 1 # seconds
REFRESH_DELAY_QUICK = 0.5  # seconds - for throttled force_refresh calls
MIN_STD_DEV = 1e-10  # Minimum standard deviation to avoid zero uncertainty warnings

# Throttling variables for get_all_teams
_last_refresh_time = 0
_last_force_refresh_time = 0  # Separate tracking for force_refresh calls
_cached_teams_result: Optional[List[Dict[str, Any]]] = None

# Throttling variables for dashboard updates
_last_team_update_time = 0
_last_full_update_time = 0
_cached_team_metrics: Optional[Dict[str, int]] = None
_cached_full_metrics: Optional[Dict[str, int]] = None

def _get_team_id_from_name(team_name: str) -> Optional[int]:
    """Helper function to get team_id from team_name."""
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

@socketio.on('keep_alive')
def on_keep_alive() -> None:
    try:
        sid = request.sid  # type: ignore
        if sid in state.dashboard_clients:
            dashboard_last_activity[sid] = time()
            emit('keep_alive_ack', to=sid)  # type: ignore
    except Exception as e:
        logger.error(f"Error in on_keep_alive: {str(e)}", exc_info=True)

@socketio.on('set_teams_streaming')
def on_set_teams_streaming(data: Dict[str, Any]) -> None:
    try:
        sid = request.sid  # type: ignore
        if sid in state.dashboard_clients:
            enabled = data.get('enabled', False)
            dashboard_teams_streaming[sid] = enabled
            logger.info(f"Dashboard client {sid} set teams streaming to: {enabled}")
    except Exception as e:
        logger.error(f"Error in on_set_teams_streaming: {str(e)}", exc_info=True)

@socketio.on('request_teams_update')
def on_request_teams_update() -> None:
    try:
        sid = request.sid  # type: ignore
        if sid in state.dashboard_clients and dashboard_teams_streaming.get(sid, False):
            # Send current teams data to this specific client
            emit_dashboard_full_update(client_sid=sid)
            logger.info(f"Sent teams update to dashboard client {sid}")
    except Exception as e:
        logger.error(f"Error in on_request_teams_update: {str(e)}", exc_info=True)

@socketio.on('toggle_game_mode')
def on_toggle_game_mode() -> None:
    """Toggle between 'classic' and 'new' game modes"""
    try:
        sid = request.sid  # type: ignore
        if sid not in state.dashboard_clients:
            emit('error', {'message': 'Unauthorized: Not a dashboard client'})  # type: ignore
            return

        # Toggle the mode
        new_mode = 'new' if state.game_mode == 'classic' else 'classic'
        state.game_mode = new_mode
        logger.info(f"Game mode toggled to: {new_mode}")
        
        # Clear caches to force recalculation with new mode
        clear_team_caches()
        
        # Notify all clients (players and dashboards) about the mode change
        socketio.emit('game_mode_changed', {'mode': new_mode})
        
        # Trigger dashboard update to recalculate metrics immediately
        emit_dashboard_full_update()
        
    except Exception as e:
        logger.error(f"Error in on_toggle_game_mode: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while toggling game mode'})  # type: ignore

@lru_cache(maxsize=CACHE_SIZE)
def compute_team_hashes(team_name: str) -> Tuple[str, str]:
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

        # logger.debug(f"History for team {team_id}: {history_str}")
        # logger.debug(rounds)
        
        # Generate two different hashes
        hash1 = hashlib.sha256(history_str.encode()).hexdigest()[:8]
        hash2 = hashlib.md5(history_str.encode()).hexdigest()[:8]
        
        return hash1, hash2
    except Exception as e:
        logger.error(f"Error computing team hashes: {str(e)}")
        return "ERROR", "ERROR"

@lru_cache(maxsize=CACHE_SIZE)
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

@lru_cache(maxsize=CACHE_SIZE)
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
                
            # Update counts
            # p1_idx = item_values.index(p1_item) # Not needed here anymore
            # p2_idx = item_values.index(p2_item) # Not needed here anymore
            
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

def compute_correlation_stats(team_name: str) -> Tuple[float, float, float]: # NOT USED
    try:
        # Get the correlation matrix and new metrics  
        result = compute_correlation_matrix(team_name)  # type: ignore
        corr_matrix, item_values = result[0], result[1]
        same_item_balance_avg = result[2]
        
        # Validate matrix dimensions and contents
        if not all(isinstance(row, list) and len(row) == 4 for row in corr_matrix) or len(corr_matrix) != 4:
            logger.error(f"Invalid correlation matrix dimensions for team_name {team_name}")
            return 0.0, 0.0, 0.0
            
        # Validate expected item values
        expected_items = ['A', 'B', 'X', 'Y']
        if not all(item in item_values for item in expected_items):
            logger.error(f"Missing expected items in correlation matrix for team_name {team_name}")
            return 0.0, 0.0, 0.0
            
        # Calculate first statistic: Trace(corr_matrix) / 4
        try:
            trace_sum = sum(corr_matrix[i][i] for i in range(4))
            trace_average_statistic = trace_sum / 4
        except (TypeError, IndexError) as e:
            logger.error(f"Error calculating trace statistic: {e}")
            trace_average_statistic = 0.0
        
        # Calculate second statistic using CHSH game formula
        # corrAX + corrAY + corrBX - corrBY + corrXA + corrXB + corrYA - corrYB
        # Get indices for A, B, X, Y from item_values
        try:
            A_idx = item_values.index('A')
            B_idx = item_values.index('B')
            X_idx = item_values.index('X')
            Y_idx = item_values.index('Y')
            
            chsh_value_statistic = (
                corr_matrix[A_idx][X_idx] + corr_matrix[A_idx][Y_idx] + 
                corr_matrix[B_idx][X_idx] - corr_matrix[B_idx][Y_idx] +
                corr_matrix[X_idx][A_idx] + corr_matrix[X_idx][B_idx] + 
                corr_matrix[Y_idx][A_idx] - corr_matrix[Y_idx][B_idx]
            )/2
        except (ValueError, IndexError, TypeError) as e:
            logger.error(f"Error calculating CHSH statistic: {e}")
            chsh_value_statistic = 0.0
        
        return trace_average_statistic, chsh_value_statistic, same_item_balance_avg
    except Exception as e:
        logger.error(f"Error computing correlation statistics: {str(e)}", exc_info=True)
        return 0.0, 0.0, 0.0


@lru_cache(maxsize=CACHE_SIZE)
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

@lru_cache(maxsize=CACHE_SIZE)
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

@lru_cache(maxsize=CACHE_SIZE)
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
        correlation_result = compute_correlation_matrix(team_name)  # type: ignore
        (corr_matrix_tuples, item_values,
         same_item_balance_avg, same_item_balance, same_item_responses,
         correlation_sums, pair_counts) = correlation_result
        
        success_result = compute_success_metrics(team_name)  # type: ignore
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

def get_all_teams(force_refresh: bool = False) -> List[Dict[str, Any]]:
    global _last_refresh_time, _last_force_refresh_time, _cached_teams_result
    
    try:
        # Check if we should throttle the request
        current_time = time()
        time_since_last_refresh = current_time - _last_refresh_time
        time_since_last_force_refresh = current_time - _last_force_refresh_time
        
        # Throttle logic with separate handling for force_refresh
        if force_refresh:
            # Throttle force_refresh calls with REFRESH_DELAY_QUICK
            if time_since_last_force_refresh < REFRESH_DELAY_QUICK and _cached_teams_result is not None:
                # logger.debug("Returning cached team data (force_refresh throttled)")
                return _cached_teams_result
        else:
            # Regular throttling for non-force_refresh calls
            if time_since_last_refresh < REFRESH_DELAY and _cached_teams_result is not None:
                # logger.debug("Returning cached team data")
                return _cached_teams_result
        
        # logger.debug("Computing fresh team data")
        
        # Compute fresh data
        # Query all teams from database - eager loading will be done per team as needed
        all_teams = Teams.query.all()
        teams_list = []
        
        for team in all_teams:
            # Get active team info from state if available
            team_info = state.active_teams.get(team.team_name)
            
            # Get players from either active state or database
            players = team_info['players'] if team_info else []
            current_round = team_info.get('current_round_number', 0) if team_info else 0
            
            # Use cached helper function for heavy computation
            team_data = _process_single_team(
                team.team_id,
                team.team_name,
                team.is_active,
                team.created_at.isoformat() if team.created_at else None,
                current_round,
                players[0] if len(players) > 0 else None,
                players[1] if len(players) > 1 else None
            )
            
            if team_data:
                teams_list.append(team_data)
        
        # Update cache and timestamp
        _cached_teams_result = teams_list
        _last_refresh_time = current_time
        if force_refresh:
            _last_force_refresh_time = current_time
        
        return teams_list
    except Exception as e:
        logger.error(f"Error in get_all_teams: {str(e)}", exc_info=True)
        return []

def clear_team_caches() -> None:
    """Clear all team-related LRU caches to prevent stale data."""
    global _last_refresh_time, _last_force_refresh_time, _cached_teams_result
    global _last_team_update_time, _last_full_update_time, _cached_team_metrics, _cached_full_metrics
    
    try:
        compute_team_hashes.cache_clear()
        compute_correlation_matrix.cache_clear()
        compute_success_metrics.cache_clear()
        _calculate_team_statistics.cache_clear()
        _calculate_success_statistics.cache_clear()
        _process_single_team.cache_clear()
        
        # Clear throttle cache for critical team state changes like disconnections
        _last_refresh_time = 0
        _last_force_refresh_time = 0
        _cached_teams_result = None
        
        # Clear dashboard update throttle caches
        _last_team_update_time = 0
        _last_full_update_time = 0
        _cached_team_metrics = None
        _cached_full_metrics = None
    except Exception as e:
        logger.error(f"Error clearing team caches: {str(e)}", exc_info=True)

def emit_dashboard_team_update(force_refresh: bool = False) -> None:
    global _last_team_update_time, _cached_team_metrics
    
    try:
        # Always compute teams data and metrics for all dashboard clients
        if not state.dashboard_clients:
            return  # No dashboard clients at all
        
        # Always calculate connected_players_count fresh since it changes frequently
        connected_players_count = len(state.connected_players)
        
        # Throttle team updates to prevent spam during mass connect/disconnect
        current_time = time()
        time_since_last_update = current_time - _last_team_update_time
        
        # Always get teams data first to ensure consistency
        serialized_teams = get_all_teams(force_refresh=force_refresh)
        
        # Use the same throttling logic as get_all_teams to ensure metrics and teams data are synchronized
        if not force_refresh and time_since_last_update < REFRESH_DELAY and _cached_team_metrics is not None:
            # Use cached metrics to avoid expensive calculations
            active_teams_count = _cached_team_metrics.get('active_teams_count', 0)
            ready_players_count = _cached_team_metrics.get('ready_players_count', 0)
        else:
            # Calculate fresh metrics from the teams data we just fetched
            active_teams = [team for team in serialized_teams if team.get('is_active', False) or team.get('status') == 'waiting_pair']
            active_teams_count = len(active_teams)
            ready_players_count = sum(
                (1 if team.get('player1_sid') else 0) + (1 if team.get('player2_sid') else 0)
                for team in active_teams
            )
            
            # Cache only the expensive-to-calculate metrics
            _cached_team_metrics = {
                'active_teams_count': active_teams_count,
                'ready_players_count': ready_players_count,
            }
            _last_team_update_time = current_time
        
        # Separate clients by streaming preference
        streaming_clients = [sid for sid in state.dashboard_clients if dashboard_teams_streaming.get(sid, False)]
        non_streaming_clients = [sid for sid in state.dashboard_clients if not dashboard_teams_streaming.get(sid, False)]
        
        # Send full teams data to streaming clients
        if streaming_clients:
            streaming_update_data = {
                'teams': serialized_teams,
                'connected_players_count': connected_players_count,
                'active_teams_count': active_teams_count,
                'ready_players_count': ready_players_count
            }
            
            for sid in streaming_clients:
                socketio.emit('team_status_changed_for_dashboard', streaming_update_data, to=sid)  # type: ignore
        
        # Send metrics-only updates to non-streaming clients
        if non_streaming_clients:
            metrics_update_data = {
                'teams': [],  # Empty teams array for non-streaming clients
                'connected_players_count': connected_players_count,
                'active_teams_count': active_teams_count,
                'ready_players_count': ready_players_count
            }
            
            for sid in non_streaming_clients:
                socketio.emit('team_status_changed_for_dashboard', metrics_update_data, to=sid)  # type: ignore
                
    except Exception as e:
        logger.error(f"Error in emit_dashboard_team_update: {str(e)}", exc_info=True)

def emit_dashboard_full_update(client_sid: Optional[str] = None, exclude_sid: Optional[str] = None) -> None:
    global _last_full_update_time, _cached_full_metrics
    
    try:
        # Check if there are any dashboard clients to send updates to
        if not state.dashboard_clients:
            return  # No dashboard clients at all
        
        # Always calculate connected_players_count fresh since it changes frequently
        connected_players_count = len(state.connected_players)
        
        # Throttle full updates to prevent spam during mass connect/disconnect
        current_time = time()
        time_since_last_update = current_time - _last_full_update_time
        
        # Always get teams data first to ensure consistency
        all_teams_for_metrics = get_all_teams()
        
        # Use the same throttling logic as get_all_teams to ensure metrics and teams data are synchronized
        if time_since_last_update < REFRESH_DELAY and _cached_full_metrics is not None:
            # Use cached data to avoid expensive operations
            total_answers = _cached_full_metrics.get('total_answers', 0)
            active_teams_count = _cached_full_metrics.get('active_teams_count', 0)
            ready_players_count = _cached_full_metrics.get('ready_players_count', 0)
        else:
            # Calculate fresh data
            with app.app_context():
                total_answers = Answers.query.count()

            # Calculate metrics from the teams data we just fetched
            # Count teams that are active or waiting for a pair as "active" for metrics
            active_teams = [team for team in all_teams_for_metrics if team.get('is_active', False) or team.get('status') == 'waiting_pair']
            active_teams_count = len(active_teams)
            ready_players_count = sum(
                (1 if team.get('player1_sid') else 0) + (1 if team.get('player2_sid') else 0)
                for team in active_teams
            )
            
            # Cache only the expensive-to-calculate metrics
            _cached_full_metrics = {
                'total_answers': total_answers,
                'active_teams_count': active_teams_count,
                'ready_players_count': ready_players_count,
            }
            _last_full_update_time = current_time

        base_update_data = {
            'total_answers_count': total_answers,
            'connected_players_count': connected_players_count,
            'active_teams_count': active_teams_count,  # Always send metrics
            'ready_players_count': ready_players_count,  # Always send metrics
            'game_state': {
                'started': state.game_started,
                'paused': state.game_paused,
                'streaming_enabled': state.answer_stream_enabled,
                'mode': state.game_mode  # Include current game mode
            }
        }

        if client_sid:
            # For specific client, include teams only if they have streaming enabled
            update_data = base_update_data.copy()
            if dashboard_teams_streaming.get(client_sid, False):
                update_data['teams'] = all_teams_for_metrics
            else:
                update_data['teams'] = []  # Send empty array if streaming disabled
            socketio.emit('dashboard_update', update_data, to=client_sid)  # type: ignore
        else:
            # For all clients, send appropriate data based on their preferences
            for dash_sid in state.dashboard_clients:
                # Skip excluded client to prevent duplicate updates
                if exclude_sid and dash_sid == exclude_sid:
                    continue
                    
                update_data = base_update_data.copy()
                if dashboard_teams_streaming.get(dash_sid, False):
                    update_data['teams'] = all_teams_for_metrics
                else:
                    update_data['teams'] = []  # Send empty array if streaming disabled
                socketio.emit('dashboard_update', update_data, to=dash_sid)  # type: ignore
    except Exception as e:
        logger.error(f"Error in emit_dashboard_full_update: {str(e)}", exc_info=True)

@socketio.on('dashboard_join')
def on_dashboard_join(data: Optional[Dict[str, Any]] = None, callback: Optional[Any] = None) -> None:
    try:
        sid = request.sid  # type: ignore
        
        # Add to dashboard clients with teams streaming disabled by default (only for new clients)
        state.dashboard_clients.add(sid)
        dashboard_last_activity[sid] = time()
        if sid not in dashboard_teams_streaming:
            dashboard_teams_streaming[sid] = False  # Teams streaming off by default only for new clients
        logger.info(f"Dashboard client connected: {sid}")
        
        # Notify OTHER dashboard clients about the new connection (exclude the joining client to prevent duplicates)
        emit_dashboard_full_update(exclude_sid=sid)
        
        # Prepare update data for this specific client, respecting their streaming preference
        with app.app_context():
            total_answers = Answers.query.count()
            
        # Always get teams data for metrics calculation
        all_teams_for_metrics = get_all_teams()
        
        # Calculate metrics that should always be sent
        # Count teams that are active or waiting for a pair as "active" for metrics
        active_teams = [team for team in all_teams_for_metrics if team.get('is_active', False) or team.get('status') == 'waiting_pair']
        active_teams_count = len(active_teams)
        ready_players_count = sum(
            (1 if team.get('player1_sid') else 0) + (1 if team.get('player2_sid') else 0)
            for team in active_teams
        )
        
        update_data = {
            'teams': all_teams_for_metrics if dashboard_teams_streaming.get(sid, False) else [],  # Respect client's streaming preference
            'total_answers_count': total_answers,
            'connected_players_count': len(state.connected_players),
            'active_teams_count': active_teams_count,  # Always send metrics
            'ready_players_count': ready_players_count,  # Always send metrics
            'game_state': {
                'started': state.game_started,
                'streaming_enabled': state.answer_stream_enabled,
                'mode': state.game_mode  # Include current game mode
            }
        }
        
        # If callback provided, use it to return data directly
        if callback:
            callback(update_data)
        else:
            # Send update to the joining client only once
            socketio.emit('dashboard_update', update_data, to=sid)  # type: ignore
    except Exception as e:
        logger.error(f"Error in on_dashboard_join: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while joining the dashboard'})  # type: ignore

@socketio.on('start_game')
def on_start_game(data: Optional[Dict[str, Any]] = None) -> None:
    try:
        if request.sid in state.dashboard_clients:  # type: ignore
            state.game_started = True
            # Notify teams and dashboard that game has started
            for team_name, team_info in state.active_teams.items():
                if len(team_info['players']) == 2:  # Only notify paired teams
                    socketio.emit('game_start', {'game_started': True}, to=team_name)  # type: ignore
            
            # Notify dashboard
            for dashboard_sid in state.dashboard_clients:
                socketio.emit('game_started', to=dashboard_sid)  # type: ignore
                
            # Notify all clients about game state change
            socketio.emit('game_state_changed', {'game_started': True})  # type: ignore
                
            # Start first round for all paired teams
            for team_name, team_info in state.active_teams.items():
                if len(team_info['players']) == 2: # If team is paired
                    start_new_round_for_pair(team_name)
    except Exception as e:
        logger.error(f"Error in on_start_game: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while starting the game'})  # type: ignore

@socketio.on('pause_game')
def on_pause_game() -> None:
    try:
        if request.sid not in state.dashboard_clients:  # type: ignore
            emit('error', {'message': 'Unauthorized: Not a dashboard client'})  # type: ignore
            return

        state.game_paused = not state.game_paused  # Toggle pause state
        pause_status = "paused" if state.game_paused else "resumed"
        logger.info(f"Game {pause_status} by {request.sid}")  # type: ignore

        # Notify all clients about pause state change
        for team_name in state.active_teams.keys():
            socketio.emit('game_state_update', {
                'paused': state.game_paused
            }, to=team_name)  # type: ignore

        # Update dashboard state
        emit_dashboard_full_update()

    except Exception as e:
        logger.error(f"Error in on_pause_game: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while toggling game pause'})  # type: ignore

def handle_dashboard_disconnect(sid: str) -> None:
    """Handle disconnect logic for dashboard clients"""
    try:
        if sid in state.dashboard_clients:
            state.dashboard_clients.remove(sid)
            if sid in dashboard_last_activity:
                del dashboard_last_activity[sid]
            if sid in dashboard_teams_streaming:
                del dashboard_teams_streaming[sid]
    except Exception as e:
        logger.error(f"Error in handle_dashboard_disconnect: {str(e)}", exc_info=True)

@socketio.on('restart_game')
def on_restart_game() -> None:
    try:
        logger.info(f"Received restart_game from {request.sid}")  # type: ignore
        if request.sid not in state.dashboard_clients:  # type: ignore
            emit('error', {'message': 'Unauthorized: Not a dashboard client'})  # type: ignore
            emit('game_reset_complete', to=request.sid)  # type: ignore
            return

        # First update game state to prevent new answers during reset
        state.game_started = False
        # logger.debug("Set game_started=False")
        
        # Even if there are no active teams, clear the database
        try:
            # Clear database entries within a transaction
            db.session.begin_nested()  # Create savepoint
            PairQuestionRounds.query.delete()
            Answers.query.delete()
            db.session.commit()
            # Clear caches after successful database commit
            clear_team_caches()
        except Exception as db_error:
            db.session.rollback()
            logger.error(f"Database error during game reset: {str(db_error)}", exc_info=True)
            emit('error', {'message': 'Database error during reset'})  # type: ignore
            emit('game_reset_complete', to=request.sid)  # type: ignore
            return

        # If no active teams, still complete the reset successfully
        if not state.active_teams:
            socketio.emit('game_state_changed', {'game_started': False})  # type: ignore
            emit_dashboard_full_update()
            emit('game_reset_complete', to=request.sid)  # type: ignore
            return
        
        # Reset team state after successful database clear
        for team_name, team_info in state.active_teams.items():
            if team_info:  # Validate team info exists
                team_info['current_round_number'] = 0
                team_info['current_db_round_id'] = None
                team_info['answered_current_round'] = {}
                team_info['combo_tracker'] = {}
        
        # Notify all teams about the reset
        for team_name in state.active_teams.keys():
            socketio.emit('game_reset', to=team_name)  # type: ignore
        
        # Ensure all clients are notified of the state change
        socketio.emit('game_state_changed', {'game_started': False})  # type: ignore
        
        # Update dashboard with reset state
        emit_dashboard_full_update()

        # Notify dashboard clients that reset is complete
        logger.info("Emitting game_reset_complete to all dashboard clients")
        for dash_sid in state.dashboard_clients:
            socketio.emit('game_reset_complete', to=dash_sid)  # type: ignore
            
    except Exception as e:
        logger.error(f"Error in on_restart_game: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while restarting the game'})  # type: ignore

@app.route('/api/dashboard/data', methods=['GET'])
def get_dashboard_data():
    try:
        # Get all answers ordered by timestamp
        with app.app_context():
            all_answers = Answers.query.order_by(Answers.timestamp.asc()).all()
        
        answers_data = []
        for ans in all_answers:
            # Get team name for each answer
            team = Teams.query.get(ans.team_id)
            team_name = team.team_name if team else "Unknown Team"
            
            answers_data.append({
                'answer_id': ans.answer_id,
                'team_id': ans.team_id,
                'team_name': team_name,
                'player_session_id': ans.player_session_id,
                'question_round_id': ans.question_round_id,
                'assigned_item': ans.assigned_item.value,
                'response_value': ans.response_value,
                'timestamp': ans.timestamp.isoformat()
            })
        
        return jsonify({'answers': answers_data}), 200
    except Exception as e:
        logger.error(f"Error in get_dashboard_data: {str(e)}", exc_info=True)
        return jsonify({'error': 'An error occurred while retrieving dashboard data'}), 500

@app.route('/download', methods=['GET'])
def download_csv():
    try:
        # Get all answers ordered by timestamp
        with app.app_context():
            all_answers = Answers.query.order_by(Answers.timestamp.asc()).all()
        
        # Create CSV content in memory
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write CSV header
        writer.writerow(['Timestamp', 'Team Name', 'Team ID', 'Player ID', 'Round ID', 'Question Item (A/B/X/Y)', 'Answer (True/False)'])
        
        # Write data rows
        for ans in all_answers:
            # Get team name for each answer
            team = Teams.query.get(ans.team_id)
            team_name = team.team_name if team else "Unknown Team"
            
            writer.writerow([
                ans.timestamp.strftime('%m/%d/%Y, %I:%M:%S %p'),  # Format timestamp like JavaScript toLocaleString()
                team_name,
                ans.team_id,
                ans.player_session_id,
                ans.question_round_id,
                ans.assigned_item.value,
                ans.response_value
            ])
        
        # Get the CSV content
        csv_content = output.getvalue()
        output.close()
        
        # Create response with appropriate headers for CSV download
        response = Response(
            csv_content,
            mimetype='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename=chsh-game-data.csv'
            }
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error in download_csv: {str(e)}", exc_info=True)
        return Response(
            "An error occurred while generating the CSV file",
            status=500,
            mimetype='text/plain'
        )

# Disconnect handler is now consolidated in team_management.py
# The handle_dashboard_disconnect function is called from there
