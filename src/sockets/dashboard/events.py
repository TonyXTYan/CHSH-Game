import logging
from typing import Dict, Any, Optional
from time import time
from flask import request, Response
from flask_socketio import emit
from src.config import app, socketio, db
from src.state import state
from src.models.quiz_models import Teams, Answers, PairQuestionRounds
from src.game_logic import start_new_round_for_pair
from .cache_management import (
    dashboard_last_activity, dashboard_teams_streaming, _atomic_client_update,
    force_clear_all_caches
)
from .team_processing import get_all_teams, emit_dashboard_full_update

# Configure logging
logger = logging.getLogger(__name__)

@socketio.on('keep_alive')
def on_keep_alive() -> None:
    """Handle dashboard client keep-alive ping to maintain connection tracking."""
    try:
        sid = request.sid  # type: ignore
        if sid in state.dashboard_clients:
            _atomic_client_update(sid, activity_time=time())
            emit('keep_alive_ack', to=sid)  # type: ignore
    except Exception as e:
        logger.error(f"Error in on_keep_alive: {str(e)}", exc_info=True)

@socketio.on('set_teams_streaming')
def on_set_teams_streaming(data: Dict[str, Any]) -> None:
    """Handle dashboard client preference for teams data streaming on/off."""
    try:
        sid = request.sid  # type: ignore
        if sid in state.dashboard_clients:
            enabled = data.get('enabled', False)
            _atomic_client_update(sid, streaming_enabled=enabled)
            logger.info(f"Dashboard client {sid} set teams streaming to: {enabled}")
    except Exception as e:
        logger.error(f"Error in on_set_teams_streaming: {str(e)}", exc_info=True)

@socketio.on('request_teams_update')
def on_request_teams_update() -> None:
    """Handle explicit request for teams data from streaming-enabled clients."""
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

def handle_dashboard_disconnect(sid: str) -> None:
    """Handle disconnect logic for dashboard clients with proper cleanup and error handling"""
    try:
        if sid in state.dashboard_clients:
            state.dashboard_clients.remove(sid)
            
        # Clean up all dashboard client tracking data atomically
        _atomic_client_update(sid, remove=True)
        
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