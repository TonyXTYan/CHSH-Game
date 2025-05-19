from datetime import datetime
import re
from flask import request
from flask_socketio import emit, join_room, leave_room
from sqlalchemy import func
from src.config import app, socketio, db
from src.state import state
from src.models.quiz_models import Teams, PairQuestionRounds, Answers
from src.sockets.dashboard import emit_dashboard_team_update, emit_dashboard_full_update
from src.game_logic import start_new_round_for_pair
import traceback

def sanitize_team_name(name):
    """
    Sanitize team name to prevent injection and ensure valid format.
    
    Args:
        name (str): The team name to sanitize
        
    Returns:
        str: Sanitized team name
    """
    if not name or not isinstance(name, str):
        return None
        
    # Remove any potentially dangerous characters
    sanitized = re.sub(r'[^\w\s-]', '', name)
    # Trim whitespace and ensure reasonable length
    sanitized = sanitized.strip()[:50]
    
    return sanitized if sanitized else None

def get_available_teams_list():
    """
    Get list of available teams for joining.
    
    Returns:
        list: List of team dictionaries with team_name, team_id, and is_active
    """
    try:
        # Get active teams that aren't full
        active_teams = []
        for name, info in state.active_teams.items():
            if len(info['players']) < 2:
                active_teams.append({
                    'team_name': name, 
                    'team_id': info['team_id'], 
                    'is_active': True
                })
        
        # Get inactive teams from database
        with app.app_context():
            inactive_teams = Teams.query.filter_by(is_active=False).all()
            inactive_teams_list = [
                {
                    'team_name': team.team_name, 
                    'team_id': team.team_id, 
                    'is_active': False
                }
                for team in inactive_teams
            ]
        
        # Combine and return all teams
        return active_teams + inactive_teams_list
    except Exception as e:
        print(f"Error in get_available_teams_list: {str(e)}")
        traceback.print_exc()
        return []

def get_team_members(team_name):
    """
    Get list of team members for a given team.
    
    Args:
        team_name (str): Name of the team
        
    Returns:
        list: List of player session IDs
    """
    try:
        team_info = state.get_team_info(team_name)
        if not team_info: 
            return []
        return team_info['players']
    except Exception as e:
        print(f"Error in get_team_members: {str(e)}")
        traceback.print_exc()
        return []

@socketio.on('connect')
def handle_connect():
    """Handle client connection to socket server."""
    try:
        sid = request.sid
        if not sid:
            print("Warning: Client connected without valid session ID")
            return
            
        print(f'Client connected: {sid}')
        
        # By default, treat all non-dashboard connections as players
        if sid not in state.dashboard_clients:
            state.add_connected_player(sid)
            emit_dashboard_full_update()  # Use full update to refresh player count
        
        emit('connection_established', {
            'game_started': state.is_game_started(),
            'available_teams': get_available_teams_list()
        })
    except Exception as e:
        print(f"Error in handle_connect: {str(e)}")
        traceback.print_exc()

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection from socket server."""
    sid = request.sid
    if not sid:
        print("Warning: Client disconnected without valid session ID")
        return
        
    print(f'Client disconnected: {sid}')
    
    try:
        # Handle dashboard client disconnection
        if sid in state.dashboard_clients:
            state.remove_dashboard_client(sid)
            print(f"Dashboard client disconnected: {sid}")

        # Remove from connected players list regardless of team status
        if sid in state.connected_players:
            state.remove_connected_player(sid)
            emit_dashboard_full_update()  # Update dashboard with new player count

        # Handle team-related disconnection
        team_name = state.get_player_team(sid)
        if team_name:
            team_info = state.get_team_info(team_name)
            if team_info:
                # Start database transaction
                db.session.begin()
                
                try:
                    db_team = Teams.query.get(team_info['team_id'])
                    if db_team:
                        # Check if the team was full before this player disconnected
                        was_full_team = len(team_info['players']) == 2

                        # Remove player from team and get remaining count
                        team_name, remaining_count = state.remove_player_from_team(sid)
                        
                        # Update the database
                        if db_team.player1_session_id == sid:
                            db_team.player1_session_id = None
                        elif db_team.player2_session_id == sid:
                            db_team.player2_session_id = None
                            
                        # Handle remaining players
                        if remaining_count > 0:
                            # If the team was full and now has one player, update status
                            if was_full_team:
                                team_info['status'] = 'waiting_pair'
                                
                            # Notify remaining players
                            emit('player_left', {
                                'message': 'A team member has disconnected.'
                            }, room=team_name)
                            
                            # Keep team active with remaining player
                            emit('team_status_update', {
                                'team_name': team_name,
                                'status': 'waiting_pair',
                                'members': get_team_members(team_name),
                                'game_started': state.is_game_started()
                            }, room=team_name)
                        else:
                            # If no players left, mark team as inactive
                            existing_inactive = Teams.query.filter_by(
                                team_name=team_name, 
                                is_active=False
                            ).first()
                            
                            if existing_inactive:
                                # Avoid name conflicts with existing inactive teams
                                db_team.team_name = f"{team_name}_{db_team.team_id}"
                                
                            db_team.is_active = False
                            
                            # Remove from active_teams state
                            state.remove_team(team_name)
                        
                        # Commit database changes
                        db.session.commit()
                        
                        # Update all clients
                        emit_dashboard_team_update() 
                        socketio.emit('teams_updated', {
                            'teams': get_available_teams_list(),
                            'game_started': state.is_game_started()
                        })
                        
                        # Leave the room
                        try:
                            leave_room(team_name, sid=sid)
                        except Exception as e:
                            print(f"Error leaving room: {str(e)}")
                            
                except Exception as inner_e:
                    db.session.rollback()
                    print(f"Error in team disconnection handling: {str(inner_e)}")
                    traceback.print_exc()
                    
    except Exception as e:
        print(f"Disconnect handler error: {str(e)}")
        traceback.print_exc()
        
        # Ensure database transaction is rolled back on error
        try:
            db.session.rollback()
        except:
            pass

@socketio.on('create_team')
def on_create_team(data):
    """
    Handle team creation request.
    
    Args:
        data (dict): Contains team_name
    """
    try:
        # Validate input
        if not isinstance(data, dict):
            emit('error', {'message': 'Invalid request format'}); return
            
        team_name = data.get('team_name')
        sid = request.sid
        
        # Sanitize and validate team name
        team_name = sanitize_team_name(team_name)
        if not team_name:
            emit('error', {'message': 'Team name is required and must contain valid characters'}); return
            
        # Check for existing team with same name
        if team_name in state.active_teams:
            emit('error', {'message': 'Team name already exists'}); return
            
        # Check database for active team with same name
        existing_team = Teams.query.filter_by(team_name=team_name, is_active=True).first()
        if existing_team:
            emit('error', {'message': 'Team name already exists in database'}); return

        # Start database transaction
        db.session.begin()
        
        try:
            # Create new team in database
            new_team_db = Teams(team_name=team_name, player1_session_id=sid)
            db.session.add(new_team_db)
            db.session.flush()  # Get ID without committing
            
            # Create team in state
            success = state.create_team(team_name, new_team_db.team_id)
            if not success:
                db.session.rollback()
                emit('error', {'message': 'Failed to create team in application state'}); return
                
            # Add player to team
            success = state.add_player_to_team(sid, team_name)
            if not success:
                db.session.rollback()
                emit('error', {'message': 'Failed to add player to team'}); return
                
            # Commit database changes
            db.session.commit()
            
            # Join socket room
            join_room(team_name)
            
            # Notify client
            emit('team_created', {
                'team_name': team_name,
                'team_id': new_team_db.team_id,
                'message': 'Team created. Waiting for another player.',
                'game_started': state.is_game_started()
            })
            
            # Update team status for creator
            emit('team_status_update', {'status': 'created'}, room=request.sid) 
            
            # Update all clients
            socketio.emit('teams_updated', {
                'teams': get_available_teams_list(),
                'game_started': state.is_game_started()
            })
            
            # Update dashboard
            emit_dashboard_team_update()
            
        except Exception as db_error:
            db.session.rollback()
            print(f"Database error in on_create_team: {str(db_error)}")
            traceback.print_exc()
            emit('error', {'message': 'Database error creating team'})
            
    except Exception as e:
        print(f"Error in on_create_team: {str(e)}")
        traceback.print_exc()
        emit('error', {'message': 'Server error creating team'})
        
        # Ensure transaction is rolled back
        try:
            db.session.rollback()
        except:
            pass
