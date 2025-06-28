"""
Utility functions for dashboard functionality.

This module handles team processing, data retrieval, CSV export,
and dashboard update emissions.
"""

import csv
import io
import logging
import threading
from datetime import datetime
from typing import Dict, List, Any, Optional
from flask import Response, jsonify
from flask_socketio import emit
from sqlalchemy.orm import joinedload

from src.config import app, socketio, db
from src.state import state
from src.models.quiz_models import Teams, PairQuestionRounds, Answers
from .dashboard_cache import selective_cache, _team_process_cache, invalidate_team_caches
from .dashboard_statistics import (
    compute_team_hashes, compute_correlation_matrix, compute_success_metrics,
    _calculate_team_statistics, _calculate_success_statistics
)

# Configure logging
logger = logging.getLogger(__name__)

# Throttling constants
REFRESH_DELAY_QUICK = 1.0  # seconds - maximum refresh rate for team updates and data fetching
REFRESH_DELAY_FULL = 3.0  # seconds - maximum refresh rate for expensive full dashboard updates

# Global throttling state for get_all_teams function
_last_refresh_time = 0
_cached_teams_result: Optional[List[Dict[str, Any]]] = None

# Global throttling state for dashboard update functions with differentiated timing
_last_team_update_time = 0
_last_full_update_time = 0
_cached_team_metrics: Optional[Dict[str, int]] = None
_cached_full_metrics: Optional[Dict[str, int]] = None

def reset_throttling_state() -> None:
    """Reset global throttling state. Used by cache clearing operations."""
    global _last_refresh_time, _cached_teams_result
    global _last_team_update_time, _last_full_update_time
    global _cached_team_metrics, _cached_full_metrics
    
    _last_refresh_time = 0
    _cached_teams_result = None
    _last_team_update_time = 0
    _last_full_update_time = 0
    _cached_team_metrics = None
    _cached_full_metrics = None

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

@selective_cache(_team_process_cache)
def _process_single_team(team_id: int, team_name: str, is_active: bool, created_at: Optional[str], 
                        current_round: int, player1_sid: Optional[str], player2_sid: Optional[str]) -> Optional[Dict[str, Any]]:
    """Process a single team and compute all its metrics."""
    try:
        # Get basic team info
        team_info = state.active_teams.get(team_name) if is_active else None
        members = team_info['players'] if team_info else []
        
        # Get team statistics based on current game mode
        if state.game_mode == 'classic':
            stats = _calculate_team_statistics(team_name)
        else:  # new mode
            stats = _calculate_success_statistics(team_name)
        
        # Get hashes for data consistency
        hash1, hash2 = compute_team_hashes(team_name)
        
        # Get correlation or success matrix data based on mode
        if state.game_mode == 'classic':
            matrix_data = compute_correlation_matrix(team_name)
            (matrix, item_values, balance_avg, balance_dict, 
             responses_dict, correlation_sums, pair_counts) = matrix_data
        else:
            matrix_data = compute_success_metrics(team_name)
            (matrix, item_values, success_rate, normalized_score,
             success_counts, pair_counts, player_responses) = matrix_data
        
        team_data = {
            'team_id': team_id,
            'team_name': team_name,
            'is_active': is_active,
            'created_at': created_at,
            'current_round': current_round,
            'members': members,
            'player_count': len(members),
            'hash1': hash1,
            'hash2': hash2,
            'stats': stats,
            'matrix': matrix,
            'item_values': item_values
        }
        
        # Add mode-specific data
        if state.game_mode == 'classic':
            team_data.update({
                'balance_avg': balance_avg,
                'balance_dict': balance_dict,
                'responses_dict': responses_dict,
                'correlation_sums': correlation_sums,
                'pair_counts': pair_counts
            })
        else:
            team_data.update({
                'success_rate': success_rate,
                'normalized_score': normalized_score,
                'success_counts': success_counts,
                'pair_counts': pair_counts,
                'player_responses': player_responses
            })
        
        return team_data
        
    except Exception as e:
        logger.error(f"Error processing team {team_name}: {str(e)}", exc_info=True)
        return None

def get_all_teams() -> List[Dict[str, Any]]:
    """
    Get all teams with throttling to prevent excessive database queries.
    Uses global caching and throttling to maintain performance.
    """
    global _last_refresh_time, _cached_teams_result
    
    current_time = time.time()
    
    # Check if we can use cached result (throttling)
    if (current_time - _last_refresh_time < REFRESH_DELAY_QUICK and 
        _cached_teams_result is not None):
        return _cached_teams_result
    
    try:
        # Eager load all related data in a single query to minimize database hits
        teams_query = Teams.query.options(
            joinedload(Teams.rounds),
            joinedload(Teams.answers)
        ).all()
        
        teams_data = []
        
        for team in teams_query:
            try:
                # Process team data
                team_data = _process_single_team(
                    team.team_id,
                    team.team_name,
                    team.is_active,
                    team.created_at.isoformat() if team.created_at else None,
                    team.current_round_number or 0,
                    team.player1_session_id,
                    team.player2_session_id
                )
                
                if team_data:
                    teams_data.append(team_data)
                    
            except Exception as e:
                logger.error(f"Error processing team {team.team_name}: {str(e)}", exc_info=True)
                continue
        
        # Update cache and throttling state
        _cached_teams_result = teams_data
        _last_refresh_time = current_time
        
        return teams_data
        
    except Exception as e:
        logger.error(f"Error in get_all_teams: {str(e)}", exc_info=True)
        return _cached_teams_result or []

def emit_dashboard_team_update() -> None:
    """
    Emit team status updates to dashboard clients with throttling.
    Sends metrics to all clients and full data to streaming-enabled clients only.
    """
    global _last_team_update_time, _cached_team_metrics
    
    from .dashboard_handlers import dashboard_teams_streaming
    
    try:
        # Get dashboard clients
        dashboard_clients = list(state.dashboard_clients)
        if not dashboard_clients:
            return
        
        current_time = time.time()
        
        # Calculate metrics (always needed, less expensive)
        if (current_time - _last_team_update_time >= REFRESH_DELAY_QUICK or 
            _cached_team_metrics is None):
            
            # Count metrics without full team processing
            active_teams_count = len([t for t in state.active_teams.values() if len(t['players']) == 2])
            ready_players_count = active_teams_count * 2
            
            metrics = {
                'connected_players_count': len(state.connected_players),
                'active_teams_count': active_teams_count,
                'ready_players_count': ready_players_count
            }
            
            _cached_team_metrics = metrics
            _last_team_update_time = current_time
        else:
            metrics = _cached_team_metrics
        
        # Send metrics to all dashboard clients
        socketio.emit('team_status_changed_for_dashboard', metrics)
        
        # Get streaming-enabled clients
        streaming_clients = [sid for sid in dashboard_clients 
                           if dashboard_teams_streaming.get(sid, False)]
        
        if streaming_clients:
            # Get full teams data for streaming clients
            teams_data = get_all_teams()
            full_update = dict(metrics)
            full_update['teams'] = teams_data
            
            # Send full data only to streaming clients
            for sid in streaming_clients:
                socketio.emit('team_status_changed_for_dashboard', full_update, to=sid)
        
    except Exception as e:
        logger.error(f"Error in emit_dashboard_team_update: {str(e)}", exc_info=True)

def emit_dashboard_full_update(client_sid: Optional[str] = None, exclude_sid: Optional[str] = None) -> None:
    """
    Emit full dashboard update with all teams data and metrics.
    
    Args:
        client_sid: If specified, send only to this client
        exclude_sid: If specified, exclude this client from broadcast
    """
    global _last_full_update_time, _cached_full_metrics
    
    try:
        current_time = time.time()
        
        # Calculate full metrics with throttling
        if (current_time - _last_full_update_time >= REFRESH_DELAY_FULL or 
            _cached_full_metrics is None):
            
            teams_data = get_all_teams()
            
            metrics = {
                'teams': teams_data,
                'connected_players_count': len(state.connected_players),
                'active_teams_count': len([t for t in teams_data if t.get('is_active', False) and len(t.get('members', [])) == 2]),
                'ready_players_count': sum(2 for t in teams_data if t.get('is_active', False) and len(t.get('members', [])) == 2)
            }
            
            _cached_full_metrics = metrics
            _last_full_update_time = current_time
        else:
            metrics = _cached_full_metrics
        
        # Send to specific client or broadcast
        if client_sid:
            socketio.emit('dashboard_full_update', metrics, to=client_sid)
        else:
            # Get all dashboard clients except excluded one
            target_clients = [sid for sid in state.dashboard_clients if sid != exclude_sid]
            for sid in target_clients:
                socketio.emit('dashboard_full_update', metrics, to=sid)
        
    except Exception as e:
        logger.error(f"Error in emit_dashboard_full_update: {str(e)}", exc_info=True)

@app.route('/api/dashboard/data', methods=['GET'])
def get_dashboard_data():
    """API endpoint to get dashboard data."""
    try:
        teams_data = get_all_teams()
        
        return jsonify({
            'teams': teams_data,
            'connected_players_count': len(state.connected_players),
            'active_teams_count': len([t for t in teams_data if t.get('is_active', False) and len(t.get('members', [])) == 2]),
            'ready_players_count': sum(2 for t in teams_data if t.get('is_active', False) and len(t.get('members', [])) == 2),
            'game_started': state.game_started,
            'game_paused': state.game_paused,
            'game_mode': state.game_mode,
            'answer_stream_enabled': state.answer_stream_enabled
        })
    except Exception as e:
        logger.error(f"Error in get_dashboard_data: {str(e)}", exc_info=True)
        return jsonify({'error': 'An error occurred'}), 500

@app.route('/download', methods=['GET'])
def download_csv():
    """Download all game data as CSV."""
    try:
        # Query all data
        teams = Teams.query.all()
        rounds = PairQuestionRounds.query.order_by(PairQuestionRounds.timestamp_initiated).all()
        answers = Answers.query.order_by(Answers.timestamp).all()
        
        # Create CSV content
        output = io.StringIO()
        writer = csv.writer(output)
        
        # Write teams data
        writer.writerow(['=== TEAMS ==='])
        writer.writerow(['Team ID', 'Team Name', 'Is Active', 'Created At', 'Player 1 SID', 'Player 2 SID'])
        for team in teams:
            writer.writerow([
                team.team_id,
                team.team_name,
                team.is_active,
                team.created_at,
                team.player1_session_id,
                team.player2_session_id
            ])
        
        writer.writerow([])  # Empty row separator
        
        # Write rounds data
        writer.writerow(['=== ROUNDS ==='])
        writer.writerow(['Round ID', 'Team ID', 'Round Number', 'Player 1 Item', 'Player 2 Item', 'Timestamp'])
        for round_obj in rounds:
            writer.writerow([
                round_obj.round_id,
                round_obj.team_id,
                round_obj.round_number_for_team,
                round_obj.player1_item.value if round_obj.player1_item else None,
                round_obj.player2_item.value if round_obj.player2_item else None,
                round_obj.timestamp_initiated
            ])
        
        writer.writerow([])  # Empty row separator
        
        # Write answers data
        writer.writerow(['=== ANSWERS ==='])
        writer.writerow(['Answer ID', 'Team ID', 'Round ID', 'Assigned Item', 'Response', 'Timestamp'])
        for answer in answers:
            writer.writerow([
                answer.answer_id,
                answer.team_id,
                answer.question_round_id,
                answer.assigned_item.value,
                answer.response_value,
                answer.timestamp
            ])
        
        # Prepare response
        csv_content = output.getvalue()
        output.close()
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"chsh_game_data_{timestamp}.csv"
        
        return Response(
            csv_content,
            mimetype='text/csv',
            headers={'Content-Disposition': f'attachment; filename={filename}'}
        )
        
    except Exception as e:
        logger.error(f"Error in download_csv: {str(e)}", exc_info=True)
        return jsonify({'error': 'An error occurred while generating CSV'}), 500

# Import time at the end to avoid circular imports
import time

# Export functions that are used by other modules
__all__ = [
    'get_all_teams',
    'emit_dashboard_team_update',
    'emit_dashboard_full_update',
    'get_dashboard_data',
    'download_csv',
    'reset_throttling_state'
]