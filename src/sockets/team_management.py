from datetime import datetime
from flask import request, has_app_context
from flask_socketio import emit, join_room, leave_room
from sqlalchemy import func
from src.config import app, socketio, db
from src.state import state
from src.models.quiz_models import Teams, PairQuestionRounds, Answers
from src.game_logic import start_new_round_for_pair
import logging
import time
from typing import Dict, Any, List, Optional

# Configure logging
logger = logging.getLogger(__name__)

def _get_player_slot_in_team(team_info: Dict[str, Any], sid: str) -> Optional[int]:
    """Get which player slot (1 or 2) a session ID occupies in a team"""
    try:
        player_index = team_info['players'].index(sid)
        return player_index + 1
    except (ValueError, KeyError):
        return None

def _track_disconnected_player(team_name: str, sid: str, team_info: Dict[str, Any]) -> None:
    """Track a disconnected player for potential reconnection"""
    player_slot = _get_player_slot_in_team(team_info, sid)
    if player_slot:
        state.disconnected_players[team_name] = {
            'player_session_id': sid,
            'player_slot': player_slot,
            'disconnect_time': time.time()
        }
        logger.info(f"Tracking disconnected player {sid} from team {team_name} (slot {player_slot})")

def _clear_disconnected_player_tracking(team_name: str) -> None:
    """Clear tracking for a disconnected player"""
    if team_name in state.disconnected_players:
        del state.disconnected_players[team_name]

def _can_rejoin_team(team_name: str) -> bool:
    """Check if a player can rejoin a team based on disconnection tracking"""
    if team_name not in state.disconnected_players:
        return False
    
    team_info = state.active_teams.get(team_name)
    if not team_info:
        return False
    
    # Team must be waiting for a player and have exactly one player
    return len(team_info['players']) == 1 and team_info.get('status') == 'waiting_pair'

def _import_dashboard_functions():
    """Import dashboard functions to avoid circular import"""
    from src.sockets.dashboard import emit_dashboard_team_update, emit_dashboard_full_update, clear_team_caches, handle_dashboard_disconnect
    return emit_dashboard_team_update, emit_dashboard_full_update, clear_team_caches, handle_dashboard_disconnect

def get_available_teams_list() -> List[Dict[str, Any]]:
    try:
        # Get active teams that aren't full
        active_teams = [{'team_name': name, 'team_id': info['team_id'], 'is_active': True}
                       for name, info in state.active_teams.items() if len(info['players']) < 2]
        
        # Get inactive teams from database (only if we have an app context)
        inactive_teams_list = []
        try:
            # Check if we're already in an app context, if not, create one
            if has_app_context():
                inactive_teams = Teams.query.filter_by(is_active=False).all()
                inactive_teams_list = [{'team_name': team.team_name, 'team_id': team.team_id, 'is_active': False}
                                     for team in inactive_teams]
            else:
                with app.app_context():
                    inactive_teams = Teams.query.filter_by(is_active=False).all()
                    inactive_teams_list = [{'team_name': team.team_name, 'team_id': team.team_id, 'is_active': False}
                                         for team in inactive_teams]
        except Exception as db_error:
            logger.warning(f"Could not fetch inactive teams: {str(db_error)}")
            inactive_teams_list = []
        
        # Combine and return all teams
        return active_teams + inactive_teams_list
    except Exception as e:
        logger.error(f"Error in get_available_teams_list: {str(e)}", exc_info=True)
        return []

def get_team_members(team_name: str) -> List[str]:
    try:
        team_info = state.active_teams.get(team_name)
        if not team_info: return []
        return team_info['players']
    except Exception as e:
        logger.error(f"Error in get_team_members: {str(e)}", exc_info=True)
        return []

@socketio.on('connect')
def handle_connect() -> None:
    try:
        sid = request.sid  # type: ignore
        logger.info(f'Client connected: {sid}')
        
        # By default, treat all non-dashboard connections as players
        if sid not in state.dashboard_clients:
            state.connected_players.add(sid)
            _, emit_dashboard_full_update, _, _ = _import_dashboard_functions()
            emit_dashboard_full_update()  # Use full update to refresh player count
        
        emit('connection_established', {
            'game_started': state.game_started,
            'available_teams': get_available_teams_list()
        })  # type: ignore
    except Exception as e:
        logger.error(f"Error in handle_connect: {str(e)}", exc_info=True)

@socketio.on('disconnect')
def handle_disconnect() -> None:
    sid = request.sid  # type: ignore
    logger.info(f'Client disconnected: {sid}')
    try:
        # Handle dashboard client disconnection
        _, emit_dashboard_full_update, _, handle_dashboard_disconnect = _import_dashboard_functions()
        handle_dashboard_disconnect(sid)

        # Remove from connected players list regardless of team status
        if sid in state.connected_players:
            state.connected_players.remove(sid)
            emit_dashboard_full_update()  # Update dashboard with new player count

        # Handle team-related disconnection
        if sid in state.player_to_team:
            team_name = state.player_to_team[sid]
            team_info = state.active_teams.get(team_name)
            if team_info:
                # Using Session.get() instead of Query.get()
                db_team = db.session.get(Teams, team_info['team_id'])
                if db_team:
                    # Check if the team was full before this player disconnected
                    was_full_team = len(team_info['players']) == 2

                    # Remove player from team
                    if sid in team_info['players']:
                        # Track disconnected player for potential reconnection
                        if was_full_team:
                            _track_disconnected_player(team_name, sid, team_info)
                        
                        team_info['players'].remove(sid)
                        
                        # Update the database
                        if db_team.player1_session_id == sid:
                            db_team.player1_session_id = None
                        elif db_team.player2_session_id == sid:
                            db_team.player2_session_id = None
                            
                        # Leave the team room BEFORE emitting to the team
                        try:
                            leave_room(team_name, sid=sid)
                        except Exception as e:
                            logger.error(f"Error leaving room: {str(e)}")
                            
                        # Notify remaining players and update team status
                        remaining_players = team_info['players']
                        if remaining_players:
                            # Always update status to waiting_pair when there's only one player
                            team_info['status'] = 'waiting_pair'
                            
                            emit('player_left', {'message': 'A team member has disconnected.'}, to=team_name)  # type: ignore
                            # Keep team active with remaining player, but disable response input
                            emit('team_status_update', {
                                'team_name': team_name,
                                'status': 'waiting_pair',
                                'members': remaining_players,
                                'game_started': state.game_started,
                                'disable_input': True  # Disable response input when team is incomplete
                            }, to=team_name)  # type: ignore
                        else:
                            # If no players left, mark team as inactive and clear tracking
                            _clear_disconnected_player_tracking(team_name)
                            existing_inactive = Teams.query.filter_by(team_name=team_name, is_active=False).first()
                            if existing_inactive:
                                db_team.team_name = f"{team_name}_{db_team.team_id}"
                            db_team.is_active = False
                            # Remove from active_teams state only if it exists
                            if team_name in state.active_teams:
                                del state.active_teams[team_name]
                            if team_info['team_id'] in state.team_id_to_name:
                                del state.team_id_to_name[team_info['team_id']]
                        
                        db.session.commit()
                        # Clear caches after team state change
                        _, _, clear_team_caches, _ = _import_dashboard_functions()
                        clear_team_caches()
                        
                        del state.player_to_team[sid]
                        
                        # Update all clients - this should happen regardless of whether team becomes inactive
                        # Move dashboard update to end to ensure all state changes are committed
                        # Force refresh for critical team state changes like disconnections
                        emit_dashboard_team_update, _, _, _ = _import_dashboard_functions()
                        emit_dashboard_team_update(force_refresh=True)
                        socketio.emit('teams_updated', {
                            'teams': get_available_teams_list(),
                            'game_started': state.game_started
                        })  # type: ignore
    except Exception as e:
        logger.error(f"Disconnect handler error: {str(e)}", exc_info=True)

@socketio.on('create_team')
def on_create_team(data: Dict[str, Any]) -> None:
    try:
        team_name = data.get('team_name')
        sid = request.sid  # type: ignore
        if not team_name:
            emit('error', {'message': 'Team name is required'})  # type: ignore
            return
        if team_name in state.active_teams or Teams.query.filter_by(team_name=team_name, is_active=True).first():
            emit('error', {'message': 'Team name already exists or is active'})  # type: ignore
            return

        new_team_db = Teams(
            team_name=team_name,
            player1_session_id=sid
        )
        db.session.add(new_team_db)
        db.session.commit()
        # Clear caches after team state change
        _, _, clear_team_caches, _ = _import_dashboard_functions()
        clear_team_caches()
        state.active_teams[team_name] = {
            'players': [sid],
            'team_id': new_team_db.team_id,
            'current_round_number': 0,
            'combo_tracker': {},
            'answered_current_round': {},
            'status': 'waiting_pair'
        }
        state.player_to_team[sid] = team_name
        state.team_id_to_name[new_team_db.team_id] = team_name
        join_room(team_name, sid=sid)  # type: ignore
        
        emit('team_created', {
            'team_name': team_name,
            'team_id': new_team_db.team_id,
            'message': 'Team created. Waiting for another player.',
            'game_started': state.game_started
        })  # type: ignore
        # This team_status_update for 'created' seems specific to the creator,
        # and might be redundant if 'team_created' already conveys enough.
        # Consider if this is still needed or if 'team_created' is sufficient.
        # For now, keeping it as it was.
        emit('team_status_update', {'status': 'created'}, to=request.sid)  # type: ignore
        
        socketio.emit('teams_updated', {
            'teams': get_available_teams_list(),
            'game_started': state.game_started
        })  # type: ignore
        
        emit_dashboard_team_update, _, _, _ = _import_dashboard_functions()
        emit_dashboard_team_update()
    except Exception as e:
        logger.error(f"Error in on_create_team: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while creating the team'})  # type: ignore

@socketio.on('join_team')
def on_join_team(data: Dict[str, Any]) -> None:
    try:
        team_name = data.get('team_name')
        sid = request.sid  # type: ignore
        if not team_name or team_name not in state.active_teams:
            emit('error', {'message': 'Team not found or invalid team name.'})  # type: ignore
            return
        team_info = state.active_teams[team_name]
        if len(team_info['players']) >= 2:
            emit('error', {'message': 'Team is already full.'})  # type: ignore
            return
        if sid in team_info['players']:
            emit('error', {'message': 'You are already in this team.'})  # type: ignore
            return

        # Always treat joining a waiting_pair team as a normal join
        # Clear any existing disconnection tracking when team becomes full
        was_tracked_team = team_name in state.disconnected_players
        
        team_info['players'].append(sid)
        state.player_to_team[sid] = team_name
        join_room(team_name, sid=sid)  # type: ignore
        
        # Using Session.get() instead of Query.get()
        db_team = db.session.get(Teams, team_info['team_id'])
        if db_team:
            if not db_team.player1_session_id:
                db_team.player1_session_id = sid
            elif not db_team.player2_session_id:
                db_team.player2_session_id = sid
            db_team.is_active = True
            db.session.commit()
            # Clear caches after team state change
            _, _, clear_team_caches, _ = _import_dashboard_functions()
            clear_team_caches()

        team_is_now_full = len(team_info['players']) == 2
        current_team_status_for_clients = 'full' if team_is_now_full else 'waiting_pair'
        
        if team_is_now_full:
            team_info['status'] = 'active' # Internal state status
            # Clear disconnection tracking when team becomes full
            if was_tracked_team:
                _clear_disconnected_player_tracking(team_name)
        else:
            team_info['status'] = 'waiting_pair' # Internal state status

        # Notify the player who just joined - always treat as normal join
        join_message = f'You reconnected to team {team_name}.' if was_tracked_team else f'You joined team {team_name}.'
        emit('team_joined', {
            'team_name': team_name,
            'message': join_message,
            'game_started': state.game_started,
            'team_status': current_team_status_for_clients,
            'is_reconnection': was_tracked_team
        }, to=sid)  # type: ignore
        
        # Notify all team members (including the one who just joined) about the team's current state
        # This replaces the separate 'player_joined' and multiple 'team_status_update' emits
        emit('team_status_update', {
            'team_name': team_name,
            'status': current_team_status_for_clients,
            'members': get_team_members(team_name),
            'game_started': state.game_started,
            'disable_input': False if team_is_now_full else True  # Enable input only when team is full
        }, to=team_name)  # type: ignore
        
        # Update all clients about the list of available teams
        socketio.emit('teams_updated', {
            'teams': get_available_teams_list(),
            'game_started': state.game_started
        })  # type: ignore
        
        # Update dashboard
        # Force refresh when team becomes active (critical state change)
        emit_dashboard_team_update, _, _, _ = _import_dashboard_functions()
        emit_dashboard_team_update(force_refresh=team_is_now_full)
        
        # If the game has already started and the team is now full, start a new round for them
        if state.game_started and team_is_now_full:
            start_new_round_for_pair(team_name)
            # No need for a separate 'game_start' emit here,
            # as 'new_question' from start_new_round_for_pair will trigger game UI.
            # The 'game_started': True flag in 'team_status_update' and 'team_joined'
            # should be sufficient for clients to know the game is active.

    except Exception as e:
        logger.error(f"Error in on_join_team: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while joining the team'})  # type: ignore

@socketio.on('reactivate_team')
def on_reactivate_team(data: Dict[str, Any]) -> None:
    try:
        team_name = data.get('team_name')
        sid = request.sid  # type: ignore
        
        if not team_name:
            emit('error', {'message': 'Team name is required'})  # type: ignore
            return
            
        # Find the inactive team in the database
        with app.app_context():
            team = Teams.query.filter_by(team_name=team_name, is_active=False).first()
            if not team:
                emit('error', {'message': 'Team not found or is already active'})  # type: ignore
                return
                
            # Check if team name would conflict with any active team
            if team_name in state.active_teams:
                emit('error', {'message': 'An active team with this name already exists'})  # type: ignore
                return
                
            # Reactivate the team
            team.is_active = True
            team.player1_session_id = sid
            db.session.commit()
            # Clear caches after team state change
            _, _, clear_team_caches, _ = _import_dashboard_functions()
            clear_team_caches()

            # Query for the highest round number previously played by this team
            max_round_obj = db.session.query(func.max(PairQuestionRounds.round_number_for_team)) \
                                        .filter_by(team_id=team.team_id).scalar()
            last_played_round_number = max_round_obj if max_round_obj is not None else 0
            
            # Set up team state
            state.active_teams[team_name] = {
                'players': [sid],
                'team_id': team.team_id,
                'current_round_number': last_played_round_number,
                'combo_tracker': {}, # Consider if this needs reloading too for long-term game fairness
                'answered_current_round': {},
                'status': 'waiting_pair'
            }
            state.player_to_team[sid] = team_name
            state.team_id_to_name[team.team_id] = team_name
            
            join_room(team_name, sid=sid)  # type: ignore
            
            emit('team_created', { # Client treats this like a new team creation
                'team_name': team_name,
                'team_id': team.team_id,
                'message': 'Team reactivated successfully. Waiting for another player.',
                'game_started': state.game_started
            })  # type: ignore
            
            socketio.emit('teams_updated', {
                'teams': get_available_teams_list(),
                'game_started': state.game_started
            })  # type: ignore
            
            emit_dashboard_team_update, _, _, _ = _import_dashboard_functions()
            emit_dashboard_team_update()
            
    except Exception as e:
        logger.error(f"Error in on_reactivate_team: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while reactivating the team'})  # type: ignore

@socketio.on('get_reconnectable_teams')
def on_get_reconnectable_teams(data: Dict[str, Any]) -> None:
    """Get list of teams that a player can reconnect to"""
    try:
        sid = request.sid  # type: ignore
        reconnectable_teams = []
        
        # Find teams that are waiting for a player and have a disconnected player tracked
        for team_name, team_info in state.active_teams.items():
            if (team_name in state.disconnected_players and 
                len(team_info['players']) == 1 and 
                team_info.get('status') == 'waiting_pair'):
                disconnected_info = state.disconnected_players[team_name]
                reconnectable_teams.append({
                    'team_name': team_name,
                    'team_id': team_info['team_id'],
                    'disconnect_time': disconnected_info['disconnect_time'],
                    'player_slot': disconnected_info['player_slot']
                })
        
        emit('reconnectable_teams', {'teams': reconnectable_teams})  # type: ignore
        
    except Exception as e:
        logger.error(f"Error in on_get_reconnectable_teams: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while getting reconnectable teams'})  # type: ignore

@socketio.on('leave_team')
def on_leave_team(data: Dict[str, Any]) -> None:
    try:
        sid = request.sid  # type: ignore
        if sid not in state.player_to_team:
            emit('error', {'message': 'You are not in a team.'})  # type: ignore
            return
        team_name = state.player_to_team[sid]
        team_info = state.active_teams.get(team_name)
        if not team_info:
            if sid in state.player_to_team: # Check before deleting
                 del state.player_to_team[sid]
            emit('error', {'message': 'Team info not found, you have been removed.'})  # type: ignore
            return

        # Using Session.get() instead of Query.get()
        db_team = db.session.get(Teams, team_info['team_id'])
        if sid in team_info['players']:
            # Track disconnected player if this was a full team
            was_full_team = len(team_info['players']) == 2
            if was_full_team:
                _track_disconnected_player(team_name, sid, team_info)
            
            team_info['players'].remove(sid)
            
            if db_team:
                if db_team.player1_session_id == sid:
                    db_team.player1_session_id = None
                elif db_team.player2_session_id == sid:
                    db_team.player2_session_id = None

            if len(team_info['players']) > 0:
                # Always set status to waiting_pair when there's only one player left
                team_info['status'] = 'waiting_pair'
                emit('player_left', {'message': 'A team member has left.'}, to=team_name)  # type: ignore
                emit('team_status_update', {
                    'team_name': team_name,
                    'status': 'waiting_pair', 
                    'members': get_team_members(team_name),
                    'game_started': state.game_started,
                    'disable_input': True  # Disable input when team becomes incomplete
                }, to=team_name)  # type: ignore
            else:
                # No players left, team becomes inactive and clear tracking
                _clear_disconnected_player_tracking(team_name)
                if team_name in state.active_teams:
                    del state.active_teams[team_name]
                if team_info['team_id'] in state.team_id_to_name:
                    del state.team_id_to_name[team_info['team_id']]
                if db_team:
                    # Check for name conflict before marking inactive
                    # This logic might be better placed in a shared utility if used elsewhere
                    existing_inactive_with_same_name = Teams.query.filter(
                        Teams.team_name == team_name, 
                        Teams.is_active == False,
                        Teams.team_id != db_team.team_id # Exclude itself if it was already inactive (should not happen here)
                    ).first()
                    if existing_inactive_with_same_name:
                        db_team.team_name = f"{team_name}_{db_team.team_id}"
                    db_team.is_active = False
            
            if db_team: # Commit changes if db_team was involved
                db.session.commit()
                # Clear caches after team state change
                _, _, clear_team_caches, _ = _import_dashboard_functions()
                clear_team_caches()

            emit('left_team_success', {'message': 'You have left the team.'}, to=sid)  # type: ignore
            try:
                leave_room(team_name, sid=sid)
            except Exception as e: # Catch potential error if room/sid is already gone
                logger.error(f"Error leaving room on leave_team: {str(e)}")

            if sid in state.player_to_team: # Check before deleting
                del state.player_to_team[sid]
            
            socketio.emit('teams_updated', {
                'teams': get_available_teams_list(),
                'game_started': state.game_started
            })  # type: ignore
            # Force refresh for critical team state changes like leaving
            emit_dashboard_team_update, _, _, _ = _import_dashboard_functions()
            emit_dashboard_team_update(force_refresh=True)
    except Exception as e:
        logger.error(f"Error in on_leave_team: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while leaving the team'})  # type: ignore
