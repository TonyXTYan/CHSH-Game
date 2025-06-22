from flask import jsonify, Response
import math
from uncertainties import ufloat
import uncertainties.umath as um  # for ufloat‑compatible fabs
import warnings
from functools import lru_cache
from sqlalchemy.orm import joinedload
from src.config import app, socketio, db
from src.state import state
from src.models.quiz_models import Teams, Answers, PairQuestionRounds
from src.game_logic import QUESTION_ITEMS, TARGET_COMBO_REPEATS
from flask_socketio import emit
from src.game_logic import start_new_round_for_pair
from time import time
import hashlib
import csv
import io
import logging
from datetime import datetime

# Configure logging
logger = logging.getLogger(__name__)

# Store last activity time for each dashboard client
dashboard_last_activity = {}

CACHE_SIZE = 1024  # Adjust cache size as needed
REFRESH_DELAY = 1 # seconds

# Throttling variables for get_all_teams
_last_refresh_time = 0
_cached_teams_result = None

@socketio.on('keep_alive')
def on_keep_alive():
    try:
        from flask import request
        sid = request.sid
        if sid in state.dashboard_clients:
            dashboard_last_activity[sid] = time()
            emit('keep_alive_ack', room=sid)
    except Exception as e:
        logger.error(f"Error in on_keep_alive: {str(e)}", exc_info=True)

@lru_cache(maxsize=CACHE_SIZE)
def compute_team_hashes(team_id):
    try:
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
def compute_correlation_matrix(team_id):
    try:
        # Get all rounds and their corresponding answers for this team
        # Use separate optimized queries with proper indexing
        rounds = PairQuestionRounds.query.filter_by(team_id=team_id).order_by(PairQuestionRounds.timestamp_initiated).all()
        
        # Create a mapping from round_id to the round object for quick access
        round_map = {round.round_id: round for round in rounds}
        
        # Get all answers for this team with optimized query
        answers = Answers.query.filter_by(team_id=team_id).order_by(Answers.timestamp).all()
        
        # Group answers by round_id
        answers_by_round = {}
        for answer in answers:
            if answer.question_round_id not in answers_by_round:
                answers_by_round[answer.question_round_id] = []
            answers_by_round[answer.question_round_id].append(answer)
        
        # Prepare the 4x4 correlation matrix for A, B, X, Y combinations
        item_values = ['A', 'B', 'X', 'Y']
        # corr_matrix will store (numerator, denominator) tuples
        corr_matrix = [[(0, 0) for _ in range(4)] for _ in range(4)]
        
        # Count pairs for each item combination
        pair_counts = {(i, j): 0 for i in item_values for j in item_values}
        correlation_sums = {(i, j): 0 for i in item_values for j in item_values}
        
        # Track same-item responses for the new metric
        same_item_responses = {}  # Will track {item: {'true': count, 'false': count}}
        
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
        same_item_balance = {}
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

def compute_correlation_stats(team_id): # NOT USED
    try:
        # Get the correlation matrix and new metrics
        corr_matrix, item_values, same_item_balance_avg, same_item_balance = compute_correlation_matrix(team_id)
        
        # Validate matrix dimensions and contents
        if not all(isinstance(row, list) and len(row) == 4 for row in corr_matrix) or len(corr_matrix) != 4:
            logger.error(f"Invalid correlation matrix dimensions for team_id {team_id}")
            return 0.0, 0.0, 0.0
            
        # Validate expected item values
        expected_items = ['A', 'B', 'X', 'Y']
        if not all(item in item_values for item in expected_items):
            logger.error(f"Missing expected items in correlation matrix for team_id {team_id}")
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
def _calculate_team_statistics(correlation_matrix_tuple_str):
    """Calculate ufloat statistics from correlation matrix string representation."""
    try:
        # Parse the correlation matrix from string back to tuple format
        import ast
        corr_matrix_tuples, item_values, same_item_responses, correlation_sums, pair_counts = ast.literal_eval(correlation_matrix_tuple_str)
        
        # --- Calculate statistics with uncertainties using ufloat ---

        # Stat1: Trace Average Statistic
        sum_of_cii_ufloats = 0
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
        # Suppress UserWarning about std_dev==0 and avoid using deprecated functions
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='Using UFloat objects with std_dev==0 may give unexpected results.')
            # Handle absolute value without using abs() or um.fabs() which are deprecated
            if raw_trace_avg_ufloat.nominal_value >= 0:
                trace_average_statistic_ufloat = raw_trace_avg_ufloat
            else:
                # Create a new ufloat with positive nominal value but same std_dev
                trace_average_statistic_ufloat = ufloat(-raw_trace_avg_ufloat.nominal_value, raw_trace_avg_ufloat.std_dev)

        # Stat2: CHSH Value Statistic
        chsh_sum_ufloat = 0
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
        cross_term_sum_ufloat = 0
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
        same_item_balance_ufloats = []
        for item, counts in (same_item_responses or {}).items():
            T_count = counts.get('true', 0)
            F_count = counts.get('false', 0)
            total_tf = T_count + F_count
            if total_tf > 0:
                p_val = T_count / total_tf
                var_p = 1 / total_tf  # simplified variance 1/N
                if var_p == 0:
                    p_true = ufloat(p_val, float("inf"))
                else:
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
            'trace_average_statistic': trace_average_statistic_ufloat.n,
            'trace_average_statistic_uncertainty': trace_average_statistic_ufloat.s if not math.isinf(trace_average_statistic_ufloat.s) else None,
            'chsh_value_statistic': chsh_value_statistic_ufloat.n,
            'chsh_value_statistic_uncertainty': chsh_value_statistic_ufloat.s if not math.isinf(chsh_value_statistic_ufloat.s) else None,
            'cross_term_combination_statistic': cross_term_combination_statistic_ufloat.n,
            'cross_term_combination_statistic_uncertainty': cross_term_combination_statistic_ufloat.s if not math.isinf(cross_term_combination_statistic_ufloat.s) else None,
            'same_item_balance': avg_same_item_balance_ufloat.n,
            'same_item_balance_uncertainty': (avg_same_item_balance_ufloat.s
                                              if not math.isinf(avg_same_item_balance_ufloat.s) else None)
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
def _process_single_team(team_id, team_name, is_active, created_at, current_round, player1_sid, player2_sid):
    """Process all heavy computation for a single team."""
    try:
        # For active teams, check game progress
        team_info = state.active_teams.get(team_name)
        all_combos = [(i1.value, i2.value) for i1 in QUESTION_ITEMS for i2 in QUESTION_ITEMS]
        combo_tracker = team_info.get('combo_tracker', {}) if team_info else {}
        min_stats_sig = all(combo_tracker.get(combo, 0) >= TARGET_COMBO_REPEATS
                        for combo in all_combos) if team_info else False
        
        # Get players list
        players = team_info['players'] if team_info else []

        # Compute hashes for the team
        hash1, hash2 = compute_team_hashes(team_id)
        
        # Compute correlation matrix and statistics
        (corr_matrix_tuples, item_values,
         same_item_balance_avg, same_item_balance, same_item_responses,
         correlation_sums, pair_counts) = compute_correlation_matrix(team_id)
        
        # Convert correlation matrix data to string for caching
        correlation_data = (corr_matrix_tuples, item_values, same_item_responses, correlation_sums, pair_counts)
        correlation_matrix_str = str(correlation_data)
        
        # Calculate statistics using cached function
        correlation_stats = _calculate_team_statistics(correlation_matrix_str)
        
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
            'correlation_matrix': corr_matrix_tuples, # Send the (numerator, denominator) tuples
            'correlation_labels': item_values,
            'correlation_stats': correlation_stats,
            'created_at': created_at
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

def get_all_teams():
    global _last_refresh_time, _cached_teams_result
    
    try:
        # Check if we should throttle the request
        current_time = time()
        time_since_last_refresh = current_time - _last_refresh_time
        
        # If within refresh delay and we have cached data, return cached result
        if time_since_last_refresh < REFRESH_DELAY and _cached_teams_result is not None:
            # logger.debug("Returning cached team data")
            return _cached_teams_result
        # else:
        #     logger.debug("Computing fresh team data")
        
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
        
        return teams_list
    except Exception as e:
        logger.error(f"Error in get_all_teams: {str(e)}", exc_info=True)
        return []

def clear_team_caches():
    """Clear all team-related LRU caches to prevent stale data."""
    # global _last_refresh_time, _cached_teams_result
    
    try:
        compute_team_hashes.cache_clear()
        compute_correlation_matrix.cache_clear()
        _calculate_team_statistics.cache_clear()
        _process_single_team.cache_clear()
        
        # Clear throttle cache to ensure fresh data is computed immediately
        # _last_refresh_time = 0
        # _cached_teams_result = None
    except Exception as e:
        logger.error(f"Error clearing team caches: {str(e)}", exc_info=True)

def emit_dashboard_team_update():
    try:
        serialized_teams = get_all_teams()
        update_data = {
            'teams': serialized_teams,
            'connected_players_count': len(state.connected_players)
        }
        for sid in state.dashboard_clients:
            socketio.emit('team_status_changed_for_dashboard', update_data, room=sid)
    except Exception as e:
        logger.error(f"Error in emit_dashboard_team_update: {str(e)}", exc_info=True)

def emit_dashboard_full_update(client_sid=None):
    try:
        with app.app_context():
            total_answers = Answers.query.count()

        update_data = {
            'teams': get_all_teams(),
            'total_answers_count': total_answers,
            'connected_players_count': len(state.connected_players),
            'game_state': {
                'started': state.game_started,
                'paused': state.game_paused,
                'streaming_enabled': state.answer_stream_enabled
            }
        }
        if client_sid:
            socketio.emit('dashboard_update', update_data, room=client_sid)
        else:
            for dash_sid in state.dashboard_clients:
                socketio.emit('dashboard_update', update_data, room=dash_sid)
    except Exception as e:
        logger.error(f"Error in emit_dashboard_full_update: {str(e)}", exc_info=True)

@socketio.on('dashboard_join')
def on_dashboard_join(data=None, callback=None):
    try:
        from flask import request
        sid = request.sid
        
        # Add to dashboard clients
        state.dashboard_clients.add(sid)
        dashboard_last_activity[sid] = time()
        logger.info(f"Dashboard client connected: {sid}")
        
        # Whenever a dashboard client joins, emit updated status to all dashboards
        emit_dashboard_full_update()
        
        # Prepare update data
        with app.app_context():
            total_answers = Answers.query.count()
        update_data = {
            'teams': get_all_teams(),
            'total_answers_count': total_answers,
            'connected_players_count': len(state.connected_players),
            'game_state': {
                'started': state.game_started,
                'streaming_enabled': state.answer_stream_enabled
            }
        }
        
        # If callback provided, use it to return data directly
        if callback:
            callback(update_data)
        else:
            # Otherwise emit as usual
            socketio.emit('dashboard_update', update_data, room=sid)
    except Exception as e:
        logger.error(f"Error in on_dashboard_join: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while joining the dashboard'})

@socketio.on('start_game')
def on_start_game(data=None):
    try:
        from flask import request
        if request.sid in state.dashboard_clients:
            state.game_started = True
            # Notify teams and dashboard that game has started
            for team_name, team_info in state.active_teams.items():
                if len(team_info['players']) == 2:  # Only notify paired teams
                    socketio.emit('game_start', {'game_started': True}, room=team_name)
            
            # Notify dashboard
            for dashboard_sid in state.dashboard_clients:
                socketio.emit('game_started', room=dashboard_sid)
                
            # Notify all clients about game state change
            socketio.emit('game_state_changed', {'game_started': True})
                
            # Start first round for all paired teams
            for team_name, team_info in state.active_teams.items():
                if len(team_info['players']) == 2: # If team is paired
                    start_new_round_for_pair(team_name)
    except Exception as e:
        logger.error(f"Error in on_start_game: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while starting the game'})

@socketio.on('pause_game')
def on_pause_game():
    try:
        from flask import request
        if request.sid not in state.dashboard_clients:
            emit('error', {'message': 'Unauthorized: Not a dashboard client'})
            return

        state.game_paused = not state.game_paused  # Toggle pause state
        pause_status = "paused" if state.game_paused else "resumed"
        logger.info(f"Game {pause_status} by {request.sid}")

        # Notify all clients about pause state change
        for team_name in state.active_teams.keys():
            socketio.emit('game_state_update', {
                'paused': state.game_paused
            }, room=team_name)

        # Update dashboard state
        emit_dashboard_full_update()

    except Exception as e:
        logger.error(f"Error in on_pause_game: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while toggling game pause'})

@socketio.on('disconnect')
def on_disconnect():
    try:
        from flask import request
        sid = request.sid
        if sid in state.dashboard_clients:
            state.dashboard_clients.remove(sid)
            if sid in dashboard_last_activity:
                del dashboard_last_activity[sid]
    except Exception as e:
        logger.error(f"Error in on_disconnect: {str(e)}", exc_info=True)

@socketio.on('restart_game')
def on_restart_game():
    try:
        from flask import request
        logger.info(f"Received restart_game from {request.sid}")
        if request.sid not in state.dashboard_clients:
            emit('error', {'message': 'Unauthorized: Not a dashboard client'})
            emit('game_reset_complete', room=request.sid)
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
            emit('error', {'message': 'Database error during reset'})
            emit('game_reset_complete', room=request.sid)
            return

        # If no active teams, still complete the reset successfully
        if not state.active_teams:
            emit('game_state_changed', {'game_started': False})
            emit_dashboard_full_update()
            emit('game_reset_complete', room=request.sid)
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
            socketio.emit('game_reset', room=team_name)
        
        # Ensure all clients are notified of the state change
        socketio.emit('game_state_changed', {'game_started': False})
        
        # Update dashboard with reset state
        emit_dashboard_full_update()

        # Notify dashboard clients that reset is complete
        logger.info("Emitting game_reset_complete to all dashboard clients")
        for dash_sid in state.dashboard_clients:
            socketio.emit('game_reset_complete', room=dash_sid)
            
    except Exception as e:
        logger.error(f"Error in on_restart_game: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while restarting the game'})

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
