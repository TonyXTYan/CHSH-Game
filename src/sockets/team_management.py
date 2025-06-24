from datetime import datetime
from flask import request, has_app_context
from flask_socketio import emit, join_room, leave_room
from sqlalchemy import func
from src.config import app, socketio, db
from src.state import state
from src.models.quiz_models import Teams, PairQuestionRounds, Answers
from src.sockets.dashboard import emit_dashboard_team_update, emit_dashboard_full_update, clear_team_caches
from src.game_logic import start_new_round_for_pair
import logging
from typing import Dict, Any, List, Optional

# Configure logging
logger = logging.getLogger(__name__)

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
        # Dashboard client handling
        if sid in state.dashboard_clients:
            state.dashboard_clients.remove(sid)
            logger.info(f"Dashboard client disconnected: {sid}")

        # Remove from connected players list regardless of team status
        if sid in state.connected_players:
            state.connected_players.remove(sid)
            # Force immediate cache invalidation for mass disconnections
            clear_team_caches()
            emit_dashboard_full_update()  # Update dashboard with new player count

        # Handle team-related disconnection with better error handling
        if sid in state.player_to_team:
            team_name = state.player_to_team[sid]
            team_info = state.active_teams.get(team_name)
            
            if team_info:
                try:
                    # Begin database transaction
                    db.session.begin()
                    
                    # Using Session.get() instead of Query.get()
                    db_team = db.session.get(Teams, team_info['team_id'])
                    if db_team:
                        # Check if the team was full before this player disconnected
                        was_full_team = len(team_info['players']) == 2

                        # Remove player from team state immediately
                        if sid in team_info['players']:
                            team_info['players'].remove(sid)
                            logger.debug(f"Removed player {sid} from team {team_name}, {len(team_info['players'])} players remaining")
                            
                            # If the team was full and now has one player, update status
                            if was_full_team and len(team_info['players']) == 1:
                                team_info['status'] = 'waiting_pair'
                            
                            # Update the database
                            if db_team.player1_session_id == sid:
                                db_team.player1_session_id = None
                            elif db_team.player2_session_id == sid:
                                db_team.player2_session_id = None
                                
                            # Handle remaining players
                            remaining_players = team_info['players']
                            if remaining_players:
                                # Keep team active with remaining player
                                try:
                                    emit('player_left', {'message': 'A team member has disconnected.'}, to=team_name)  # type: ignore
                                    emit('team_status_update', {
                                        'team_name': team_name,
                                        'status': 'waiting_pair',
                                        'members': remaining_players,
                                        'game_started': state.game_started
                                    }, to=team_name)  # type: ignore
                                except Exception as emit_error:
                                    logger.warning(f"Failed to emit to remaining players in team {team_name}: {emit_error}")
                            else:
                                # No players left, mark team as inactive
                                existing_inactive = Teams.query.filter_by(team_name=team_name, is_active=False).first()
                                if existing_inactive:
                                    db_team.team_name = f"{team_name}_{db_team.team_id}"
                                db_team.is_active = False
                                
                                # Remove from active_teams state
                                if team_name in state.active_teams:
                                    del state.active_teams[team_name]
                                if team_info['team_id'] in state.team_id_to_name:
                                    del state.team_id_to_name[team_info['team_id']]
                                
                                logger.debug(f"Team {team_name} marked as inactive (no players remaining)")
                            
                            # Commit database changes
                            db.session.commit()
                            
                            # Force immediate cache invalidation and dashboard update
                            clear_team_caches()
                            emit_dashboard_team_update()
                            socketio.emit('teams_updated', {
                                'teams': get_available_teams_list(),
                                'game_started': state.game_started
                            })  # type: ignore
                            
                except Exception as db_error:
                    logger.error(f"Database error during disconnect for player {sid}: {db_error}")
                    db.session.rollback()
                finally:
                    # Always clean up player mapping and room membership
                    try:
                        leave_room(team_name, sid=sid)
                    except Exception as room_error:
                        logger.warning(f"Error leaving room {team_name} for player {sid}: {room_error}")
                    
                    if sid in state.player_to_team:
                        del state.player_to_team[sid]
            else:
                # Team info not found, clean up orphaned player mapping
                logger.warning(f"Player {sid} was in team {team_name} but team info not found in state")
                if sid in state.player_to_team:
                    del state.player_to_team[sid]
                
    except Exception as e:
        logger.error(f"Disconnect handler error for {sid}: {str(e)}", exc_info=True)
        # Emergency cleanup - ensure player is removed from all mappings
        try:
            if sid in state.player_to_team:
                del state.player_to_team[sid]
            if sid in state.connected_players:
                state.connected_players.remove(sid)
        except Exception as cleanup_error:
            logger.error(f"Emergency cleanup failed for {sid}: {cleanup_error}")

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
            clear_team_caches()

        team_is_now_full = len(team_info['players']) == 2
        current_team_status_for_clients = 'full' if team_is_now_full else 'waiting_pair'
        
        if team_is_now_full:
            team_info['status'] = 'active' # Internal state status
        else:
            team_info['status'] = 'waiting_pair' # Internal state status

        # Notify the player who just joined
        emit('team_joined', {
            'team_name': team_name,
            'message': f'You joined team {team_name}.',
            'game_started': state.game_started,
            'team_status': current_team_status_for_clients # Let P2 know if team is full now
        }, to=sid)  # type: ignore
        
        # Notify all team members (including the one who just joined) about the team's current state
        # This replaces the separate 'player_joined' and multiple 'team_status_update' emits
        emit('team_status_update', {
            'team_name': team_name,
            'status': current_team_status_for_clients,
            'members': get_team_members(team_name),
            'game_started': state.game_started
        }, to=team_name)  # type: ignore
        
        # Update all clients about the list of available teams
        socketio.emit('teams_updated', {
            'teams': get_available_teams_list(),
            'game_started': state.game_started
        })  # type: ignore
        
        # Update dashboard
        emit_dashboard_team_update()
        
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
            
            emit_dashboard_team_update()
            
    except Exception as e:
        logger.error(f"Error in on_reactivate_team: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while reactivating the team'})  # type: ignore

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
            team_info['players'].remove(sid)
            
            if db_team:
                if db_team.player1_session_id == sid:
                    db_team.player1_session_id = None
                elif db_team.player2_session_id == sid:
                    db_team.player2_session_id = None

            if len(team_info['players']) > 0:
                team_info['status'] = 'waiting_pair'
                emit('player_left', {'message': 'A team member has left.'}, to=team_name)  # type: ignore
                emit('team_status_update', {
                    'team_name': team_name,
                    'status': 'waiting_pair', 
                    'members': get_team_members(team_name),
                    'game_started': state.game_started
                }, to=team_name)  # type: ignore
            else:
                # No players left, team becomes inactive
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
            emit_dashboard_team_update()
    except Exception as e:
        logger.error(f"Error in on_leave_team: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while leaving the team'})  # type: ignore
