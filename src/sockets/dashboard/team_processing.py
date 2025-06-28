import logging
from typing import Dict, List, Any, Optional
from time import time
from sqlalchemy.orm import joinedload
from src.config import app, socketio, db
from src.state import state
from src.models.quiz_models import Teams, Answers, PairQuestionRounds, ItemEnum
from src.game_logic import QUESTION_ITEMS, TARGET_COMBO_REPEATS
from .cache_management import (
    selective_cache, _team_process_cache, _safe_dashboard_operation,
    REFRESH_DELAY_QUICK, REFRESH_DELAY_FULL, _last_refresh_time, _cached_teams_result,
    dashboard_teams_streaming
)
from .team_data import (
    compute_team_hashes, _compute_team_hashes_optimized,
    _compute_correlation_matrix_optimized, _compute_success_metrics_optimized
)
from .statistics import (
    _calculate_team_statistics, _calculate_success_statistics,
    _calculate_team_statistics_from_data, _calculate_success_statistics_from_data
)

# Configure logging
logger = logging.getLogger(__name__)

# Global throttling state for dashboard update functions with differentiated timing
_last_team_update_time = 0
_last_full_update_time = 0
_cached_team_metrics: Optional[Dict[str, Any]] = None
_cached_full_metrics: Optional[Dict[str, Any]] = None

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
        from .team_data import compute_correlation_matrix, compute_success_metrics
        
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

def emit_dashboard_team_update() -> None:
    """
    Send team status updates to dashboard clients with throttled metrics calculation.
    Always sends fresh connected_players_count but throttles expensive metrics.
    Uses REFRESH_DELAY_QUICK for frequent team status updates.
    Thread-safe with proper error handling.
    """
    global _last_team_update_time, _cached_team_metrics
    
    try:
        # Always compute teams data and metrics for all dashboard clients
        if not state.dashboard_clients:
            return  # No dashboard clients at all
        
        # Always calculate connected_players_count fresh since it changes frequently
        connected_players_count = len(state.connected_players)
        
        with _safe_dashboard_operation():
            # Check if any clients need teams streaming
            streaming_clients = [sid for sid in state.dashboard_clients if dashboard_teams_streaming.get(sid, False)]
            non_streaming_clients = [sid for sid in state.dashboard_clients if not dashboard_teams_streaming.get(sid, False)]
            
            # Throttle team updates to prevent spam during mass connect/disconnect
            current_time = time()
            time_since_last_update = current_time - _last_team_update_time
            
            # Only compute expensive teams data if there are streaming clients
            if streaming_clients:
                if time_since_last_update < REFRESH_DELAY_QUICK and _cached_team_metrics is not None:
                    # Use cached data for both teams and metrics to avoid expensive calculations
                    serialized_teams = _cached_team_metrics.get('cached_teams', [])
                    active_teams_count = _cached_team_metrics.get('active_teams_count', 0)
                    ready_players_count = _cached_team_metrics.get('ready_players_count', 0)
                    logger.debug("Using cached team data and metrics for team update")
                else:
                    # Calculate fresh data including expensive team computation
                    serialized_teams = get_all_teams()
                    active_teams = [team for team in serialized_teams if team.get('is_active', False) or team.get('status') == 'waiting_pair']
                    active_teams_count = len(active_teams)
                    ready_players_count = sum(
                        (1 if team.get('player1_sid') else 0) + (1 if team.get('player2_sid') else 0)
                        for team in active_teams
                    )
                    
                    # Cache both the expensive teams data AND the calculated metrics
                    _cached_team_metrics = {
                        'cached_teams': serialized_teams,
                        'active_teams_count': active_teams_count,
                        'ready_players_count': ready_players_count,
                    }
                    _last_team_update_time = current_time
                    logger.debug("Computed fresh team data and metrics for team update")
            else:
                # No streaming clients - compute lightweight metrics only
                serialized_teams = []
                if time_since_last_update < REFRESH_DELAY_QUICK and _cached_team_metrics is not None:
                    active_teams_count = _cached_team_metrics.get('active_teams_count', 0)
                    ready_players_count = _cached_team_metrics.get('ready_players_count', 0)
                    logger.debug("Using cached metrics for non-streaming team update")
                else:
                    # Calculate lightweight metrics from state without expensive team processing
                    active_teams = [team_info for team_info in state.active_teams.values() 
                                  if team_info.get('status') in ['active', 'waiting_pair']]
                    active_teams_count = len(active_teams)
                    ready_players_count = sum(len(team_info.get('players', [])) for team_info in active_teams)
                    
                    # Cache just the lightweight metrics
                    _cached_team_metrics = {
                        'cached_teams': [],  # No teams data cached for non-streaming updates
                        'active_teams_count': active_teams_count,
                        'ready_players_count': ready_players_count,
                    }
                    _last_team_update_time = current_time
                    logger.debug("Computed lightweight metrics for non-streaming team update")
        
        # Send updates outside the lock to prevent blocking
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
    """
    Send full dashboard update including all teams data to dashboard clients.
    More comprehensive than emit_dashboard_team_update but with REFRESH_DELAY_FULL throttling.
    """
    global _last_full_update_time, _cached_full_metrics
    
    try:
        # Determine target clients
        if client_sid:
            target_clients = [client_sid] if client_sid in state.dashboard_clients else []
        else:
            target_clients = list(state.dashboard_clients)
            if exclude_sid:
                target_clients = [sid for sid in target_clients if sid != exclude_sid]
        
        if not target_clients:
            return  # No valid dashboard clients
        
        # Always calculate connected_players_count fresh
        connected_players_count = len(state.connected_players)
        
        with _safe_dashboard_operation():
            # Throttle full dashboard updates more aggressively than team updates
            current_time = time()
            time_since_last_update = current_time - _last_full_update_time
            
            if time_since_last_update < REFRESH_DELAY_FULL and _cached_full_metrics is not None:
                # Use cached comprehensive data
                serialized_teams = _cached_full_metrics.get('cached_teams', [])
                active_teams_count = _cached_full_metrics.get('active_teams_count', 0)
                ready_players_count = _cached_full_metrics.get('ready_players_count', 0)
                logger.debug("Using cached comprehensive data for full dashboard update")
            else:
                # Calculate fresh comprehensive data
                serialized_teams = get_all_teams()
                active_teams = [team for team in serialized_teams if team.get('is_active', False) or team.get('status') == 'waiting_pair']
                active_teams_count = len(active_teams)
                ready_players_count = sum(
                    (1 if team.get('player1_sid') else 0) + (1 if team.get('player2_sid') else 0)
                    for team in active_teams
                )
                
                # Cache comprehensive data
                _cached_full_metrics = {
                    'cached_teams': serialized_teams,
                    'active_teams_count': active_teams_count,
                    'ready_players_count': ready_players_count,
                }
                _last_full_update_time = current_time
                logger.debug("Computed fresh comprehensive data for full dashboard update")
        
        # Send update outside the lock to prevent blocking
        update_data = {
            'teams': serialized_teams,
            'connected_players_count': connected_players_count,
            'active_teams_count': active_teams_count,
            'ready_players_count': ready_players_count,
            'game_mode': state.game_mode
        }
        
        for sid in target_clients:
            socketio.emit('teams_data_for_dashboard', update_data, to=sid)  # type: ignore
        
    except Exception as e:
        logger.error(f"Error in emit_dashboard_full_update: {str(e)}", exc_info=True)