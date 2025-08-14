"""
Socket event handlers and dashboard update functions.

Contains socket event handlers for game control and dashboard update emission functions.
"""

import logging
from time import time
from typing import Dict, Any, Optional
from flask import request
from flask_socketio import emit

from src.config import socketio, app, db
from src.state import state
from src.models.quiz_models import Teams, Answers, PairQuestionRounds
from src.game_logic import start_new_round_for_pair
from .cache_system import (
    force_clear_all_caches, _safe_dashboard_operation, REFRESH_DELAY_QUICK, REFRESH_DELAY_FULL,
    _last_team_update_time, _last_full_update_time, _cached_team_metrics, _cached_full_metrics
)
from .client_management import dashboard_teams_streaming, _atomic_client_update, dashboard_last_activity
from .team_processing import get_all_teams

logger = logging.getLogger(__name__)

@socketio.on('toggle_game_mode')
def on_toggle_game_mode() -> None:
    """Toggle between 'classic' and 'new' game modes with cache invalidation."""
    try:
        sid = request.sid  # type: ignore
        if sid not in state.dashboard_clients:
            emit('error', {'message': 'Unauthorized: Not a dashboard client'})  # type: ignore
            return

        # Toggle the mode
        new_mode = 'new' if state.game_mode == 'classic' else 'classic'
        state.game_mode = new_mode
        logger.info(f"Game mode toggled to: {new_mode}")
        
        # Clear caches to recalculate with new mode - use force clear since mode affects all calculations
        force_clear_all_caches()
        
        # Notify all clients (players and dashboards) about the mode change
        socketio.emit('game_mode_changed', {'mode': new_mode})
        
        # Trigger dashboard update to recalculate metrics immediately
        emit_dashboard_full_update()
        
    except Exception as e:
        logger.error(f"Error in on_toggle_game_mode: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while toggling game mode'})  # type: ignore

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
            
        # Only get expensive teams data if this client has streaming enabled
        if dashboard_teams_streaming.get(sid, False):
            all_teams_for_metrics = get_all_teams()
            # Calculate metrics from the teams data we just fetched
            active_teams = [team for team in all_teams_for_metrics if team.get('is_active', False) or team.get('status') == 'waiting_pair']
            active_teams_count = len(active_teams)
            ready_players_count = sum(
                (1 if team.get('player1_sid') else 0) + (1 if team.get('player2_sid') else 0)
                for team in active_teams
            )
        else:
            # Calculate lightweight metrics from state without expensive team processing
            all_teams_for_metrics = []
            active_teams = [team_info for team_info in state.active_teams.values() 
                          if team_info.get('status') in ['active', 'waiting_pair']]
            active_teams_count = len(active_teams)
            ready_players_count = sum(len(team_info.get('players', [])) for team_info in active_teams)
        
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
            # Force clear all caches after successful database commit since this is a complete reset
            force_clear_all_caches()
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