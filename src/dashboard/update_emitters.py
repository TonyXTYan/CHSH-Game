"""
Update emitters module for dashboard functionality.
Contains functions for emitting dashboard updates with throttling.
"""

import logging
from typing import Optional, Dict, Any, List
from time import time

from src.config import app, socketio
from src.state import state
from src.models.quiz_models import Answers

from .client_management import _safe_dashboard_operation, dashboard_teams_streaming
from .team_processing import get_all_teams

# Configure logging
logger = logging.getLogger(__name__)

# Cache configuration and throttling constants
REFRESH_DELAY_QUICK = 1.0  # seconds - maximum refresh rate for team updates and data fetching
REFRESH_DELAY_FULL = 3.0  # seconds - maximum refresh rate for expensive full dashboard updates

# Global throttling state for dashboard update functions with differentiated timing
_last_team_update_time = 0
_last_full_update_time = 0
_cached_team_metrics: Optional[Dict[str, Any]] = None
_cached_full_metrics: Optional[Dict[str, Any]] = None


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
    Send complete dashboard data to clients with throttled expensive operations.
    Supports targeting specific clients or excluding clients to prevent duplicates.
    Uses REFRESH_DELAY_FULL for expensive operations like database queries.
    Thread-safe with proper error handling.
    """
    global _last_full_update_time, _cached_full_metrics
    
    try:
        # Check if there are any dashboard clients to send updates to
        if not state.dashboard_clients:
            return  # No dashboard clients at all
        
        # Always calculate connected_players_count fresh since it changes frequently
        connected_players_count = len(state.connected_players)
        
        with _safe_dashboard_operation():
            # Determine which clients need teams data
            if client_sid:
                clients_needing_teams = [client_sid] if dashboard_teams_streaming.get(client_sid, False) else []
            else:
                clients_needing_teams = [sid for sid in state.dashboard_clients 
                                       if dashboard_teams_streaming.get(sid, False) and sid != exclude_sid]
            
            # Throttle full updates with longer delay due to expensive operations
            current_time = time()
            time_since_last_update = current_time - _last_full_update_time
            
            # Only compute expensive teams data if clients need it
            if clients_needing_teams:
                if time_since_last_update < REFRESH_DELAY_FULL and _cached_full_metrics is not None:
                    # Use cached data to avoid expensive operations
                    all_teams_for_metrics = _cached_full_metrics.get('cached_teams', [])
                    total_answers = _cached_full_metrics.get('total_answers', 0)
                    active_teams_count = _cached_full_metrics.get('active_teams_count', 0)
                    ready_players_count = _cached_full_metrics.get('ready_players_count', 0)
                    logger.debug("Using cached team data and full metrics for dashboard update")
                else:
                    # Calculate fresh data with expensive database query AND team computation
                    all_teams_for_metrics = get_all_teams()
                    
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
                    
                    # Cache the expensive-to-calculate data including teams
                    _cached_full_metrics = {
                        'cached_teams': all_teams_for_metrics,
                        'total_answers': total_answers,
                        'active_teams_count': active_teams_count,
                        'ready_players_count': ready_players_count,
                    }
                    _last_full_update_time = current_time
                    logger.debug("Computed fresh team data and full metrics for dashboard update")
            else:
                # No clients need teams data - compute lightweight metrics only
                all_teams_for_metrics = []
                if time_since_last_update < REFRESH_DELAY_FULL and _cached_full_metrics is not None:
                    total_answers = _cached_full_metrics.get('total_answers', 0)
                    active_teams_count = _cached_full_metrics.get('active_teams_count', 0)
                    ready_players_count = _cached_full_metrics.get('ready_players_count', 0)
                    logger.debug("Using cached metrics for non-streaming dashboard update")
                else:
                    # Calculate lightweight metrics and database query only
                    with app.app_context():
                        total_answers = Answers.query.count()
                    
                    # Calculate lightweight metrics from state without expensive team processing
                    active_teams = [team_info for team_info in state.active_teams.values() 
                                  if team_info.get('status') in ['active', 'waiting_pair']]
                    active_teams_count = len(active_teams)
                    ready_players_count = sum(len(team_info.get('players', [])) for team_info in active_teams)
                    
                    # Cache just the lightweight metrics
                    _cached_full_metrics = {
                        'cached_teams': [],  # No teams data cached for non-streaming updates
                        'total_answers': total_answers,
                        'active_teams_count': active_teams_count,
                        'ready_players_count': ready_players_count,
                    }
                    _last_full_update_time = current_time
                    logger.debug("Computed lightweight metrics for non-streaming dashboard update")

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

        # Send updates outside the lock to prevent blocking
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