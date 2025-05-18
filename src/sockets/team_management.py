from datetime import datetime
from flask import request
from flask_socketio import emit, join_room, leave_room
from src.config import app, socketio, db
from src.state import state
from src.models.quiz_models import Teams, PairQuestionRounds, Answers
from src.sockets.dashboard import emit_dashboard_team_update, emit_dashboard_full_update
from src.game_logic import start_new_round_for_pair

def get_available_teams_list():
    try:
        # Get active teams that aren't full
        active_teams = [{'team_name': name, 'team_id': info['team_id'], 'is_active': True}
                       for name, info in state.active_teams.items() if len(info['players']) < 2]
        
        # Get inactive teams from database
        with app.app_context():
            inactive_teams = Teams.query.filter_by(is_active=False).all()
            inactive_teams_list = [{'team_name': team.team_name, 'team_id': team.team_id, 'is_active': False}
                                 for team in inactive_teams]
        
        # Combine and return all teams
        return active_teams + inactive_teams_list
    except Exception as e:
        print(f"Error in get_available_teams_list: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def get_team_members(team_name):
    try:
        team_info = state.active_teams.get(team_name)
        if not team_info: return []
        return team_info['players']
    except Exception as e:
        print(f"Error in get_team_members: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

@socketio.on('connect')
def handle_connect():
    try:
        sid = request.sid
        print(f'Client connected: {sid}')
        
        # By default, treat all non-dashboard connections as players
        if sid not in state.dashboard_clients:
            state.connected_players.add(sid)
            emit_dashboard_full_update()  # Use full update to refresh player count
        
        emit('connection_established', {
            'game_started': state.game_started,
            'available_teams': get_available_teams_list()
        })
    except Exception as e:
        print(f"Error in handle_connect: {str(e)}")
        import traceback
        traceback.print_exc()

@socketio.on('disconnect')
def handle_disconnect():
    sid = request.sid
    print(f'Client disconnected: {sid}')
    try:
        if sid in state.dashboard_clients:
            state.dashboard_clients.remove(sid)
            print(f"Dashboard client disconnected: {sid}")

        # Remove from connected players list regardless of team status
        if sid in state.connected_players:
            state.connected_players.remove(sid)
            emit_dashboard_full_update()  # Update dashboard with new player count

        # Handle team-related disconnection
        if sid in state.player_to_team:
            team_name = state.player_to_team[sid]
            team_info = state.active_teams.get(team_name)
            if team_info:
                db_team = Teams.query.get(team_info['team_id'])
                if db_team:
                    # Remove player from team
                    if sid in team_info['players']:
                        # Get the player's index BEFORE removing them from the array
                        player_index = team_info['players'].index(sid)
                        print(f"Player {sid} was at index {player_index} in team {team_name}")
                        
                        # Update the database based on their position
                        if player_index == 0:
                            # Only clear if the SID matches what we're removing
                            if db_team.player1_session_id == sid:
                                db_team.player1_session_id = None
                                print(f"Removed player1 session ID: {sid}")
                            else:
                                print(f"Warning: player1_session_id {db_team.player1_session_id} doesn't match disconnected SID {sid}")
                        elif player_index == 1:
                            # Only clear if the SID matches what we're removing
                            if db_team.player2_session_id == sid:
                                db_team.player2_session_id = None
                                print(f"Removed player2 session ID: {sid}")
                            else:
                                print(f"Warning: player2_session_id {db_team.player2_session_id} doesn't match disconnected SID {sid}")
                        
                        # Now remove the player from the team's players list
                        team_info['players'].remove(sid)
                            
                        # Notify remaining players
                        remaining_players = team_info['players']
                        if remaining_players:
                            emit('player_left', {'message': 'A team member has disconnected.'}, room=team_name)
                            # Keep team active with remaining player
                            # Update team status and notify all clients
                            team_info['status'] = 'waiting_pair'
                            emit('team_status_update', {
                                'team_name': team_name,
                                'status': 'waiting_for_player',
                                'members': remaining_players,
                                'game_started': state.game_started
                            }, room=team_name)
                            emit_dashboard_team_update()  # Force immediate dashboard update
                        else:
                            # If no players left, mark team as inactive
                            existing_inactive = Teams.query.filter_by(team_name=team_name, is_active=False).first()
                            if existing_inactive:
                                db_team.team_name = f"{team_name}_{db_team.team_id}"
                            db_team.is_active = False
                            del state.active_teams[team_name]
                            if team_info['team_id'] in state.team_id_to_name:
                                del state.team_id_to_name[team_info['team_id']]
                        
                        db.session.commit()
                        
                        # Ensure database and memory are consistent
                        if team_name in state.active_teams:
                            try:
                                from src.sockets.game import validate_team_sessions, sync_team_state
                                # First validate to fix any duplicate SIDs
                                validate_team_sessions(team_name)
                                # Then sync to ensure consistency
                                sync_team_state(team_name)
                            except ImportError:
                                print("Warning: Could not import sync_team_state function")
                        
                        # Update all clients
                        emit_dashboard_team_update()
                        socketio.emit('teams_updated', {
                            'teams': get_available_teams_list(),
                            'game_started': state.game_started
                        })
                        
                        try:
                            leave_room(team_name, sid=sid)
                        except Exception as e:
                            print(f"Error leaving room: {str(e)}")
                        del state.player_to_team[sid]
    except Exception as e:
        print(f"Disconnect handler error: {str(e)}")
        traceback.print_exc()

@socketio.on('create_team')
def on_create_team(data):
    try:
        team_name = data.get('team_name')
        sid = request.sid
        if not team_name:
            emit('error', {'message': 'Team name is required'}); return
        if team_name in state.active_teams or Teams.query.filter_by(team_name=team_name, is_active=True).first():
            emit('error', {'message': 'Team name already exists or is active'}); return

        new_team_db = Teams(team_name=team_name, player1_session_id=sid)
        db.session.add(new_team_db)
        db.session.commit()
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
        join_room(team_name)
        
        emit('team_created', {
            'team_name': team_name,
            'team_id': new_team_db.team_id,
            'message': 'Team created. Waiting for another player.',
            'game_started': state.game_started
        })
        emit('team_status_update', {'status': 'created'}, room=request.sid)
        
        socketio.emit('teams_updated', {
            'teams': get_available_teams_list(),
            'game_started': state.game_started
        })
        
        emit_dashboard_team_update()
    except Exception as e:
        print(f"Error in on_create_team: {str(e)}")
        traceback.print_exc()
        emit('error', {'message': f'Error creating team: {str(e)}'})

@socketio.on('join_team')
def on_join_team(data):
    try:
        team_name = data.get('team_name')
        sid = request.sid
        if not team_name or team_name not in state.active_teams:
            emit('error', {'message': 'Team not found or invalid team name'}); return
        
        # Pre-validate team state before joining to ensure integrity
        try:
            from src.sockets.team_validation import validate_all_teams
            validate_all_teams()
        except ImportError:
            # If validation module not available, try to directly validate just this team
            try:
                from src.sockets.game import validate_team_sessions
                validate_team_sessions(team_name)
            except ImportError:
                print("Warning: Team validation functions not available")
        
        # Get fresh team info after validation
        if team_name not in state.active_teams:
            emit('error', {'message': 'Team not found after validation'}); return
            
        team_info = state.active_teams[team_name]
        if len(team_info['players']) >= 2:
            emit('error', {'message': 'Team is already full'}); return
        if sid in team_info['players']:
            emit('error', {'message': 'You are already in this team'}); return

        team_info['players'].append(sid)
        state.player_to_team[sid] = team_name
        join_room(team_name)
        
        db_team = Teams.query.get(team_info['team_id'])
        if db_team:
            # Clean up the players array to remove any None values
            team_info['players'] = [p for p in team_info['players'] if p is not None]
            
            # Verify the player is actually in the array before proceeding
            if sid not in team_info['players']:
                print(f"Warning: Player {sid} not found in players array, adding them")
                team_info['players'].append(sid)
            
            # Ensure the player is assigned to the correct position corresponding to the players array
            player_index = team_info['players'].index(sid)
            print(f"New player {sid} joined at index {player_index} in team {team_name}")
            
            # First check if both positions have the same SID (a previous error condition)
            if db_team.player1_session_id is not None and db_team.player1_session_id == db_team.player2_session_id:
                print(f"ERROR: Same SID {db_team.player1_session_id} found in both player positions in database")
                # Clear both to be safe, we'll set the correct one next
                db_team.player1_session_id = None
                db_team.player2_session_id = None
            
            # Check if this SID is already used in either position and clear it to avoid duplicates
            if db_team.player1_session_id == sid:
                if player_index != 0:  # Only clear if we're not supposed to be in this position
                    print(f"Clearing duplicate player1_session_id {sid}")
                    db_team.player1_session_id = None
                    
            if db_team.player2_session_id == sid:
                if player_index != 1:  # Only clear if we're not supposed to be in this position
                    print(f"Clearing duplicate player2_session_id {sid}")
                    db_team.player2_session_id = None
            
            # Make sure we don't assign the same SID to both positions
            if player_index == 0:
                if db_team.player2_session_id == sid:
                    print(f"Clearing player2_session_id {sid} to avoid duplicate")
                    db_team.player2_session_id = None
                db_team.player1_session_id = sid
                print(f"Set player1_session_id to {sid}")
            elif player_index == 1:
                if db_team.player1_session_id == sid:
                    print(f"Clearing player1_session_id {sid} to avoid duplicate")
                    db_team.player1_session_id = None
                db_team.player2_session_id = sid
                print(f"Set player2_session_id to {sid}")
            
            db.session.commit()
            
            # Double-check that we don't have the same SID in both positions
            if db_team.player1_session_id is not None and db_team.player1_session_id == db_team.player2_session_id:
                print(f"CRITICAL ERROR: Same SID still in both positions after update. Fixing...")
                # Clear player2 as a last resort
                db_team.player2_session_id = None
                db.session.commit()

        emit('team_joined', {
            'team_name': team_name,
            'message': f'You joined team {team_name}.',
            'game_started': state.game_started
        }, room=sid)
        
        # Notify all team members
        emit('player_joined', {
            'team_name': team_name,
            'message': f'A new player joined your team!',
            'game_started': state.game_started
        }, room=team_name)
        
        socketio.emit('teams_updated', {
            'teams': get_available_teams_list(),
            'game_started': state.game_started
        })
        
        # Update the team status
        if len(team_info['players']) < 2:
            team_info['status'] = 'waiting_pair'
        
        emit('team_status_update', {
            'team_name': team_name,
            'status': 'full' if len(team_info['players']) == 2 else 'waiting_for_player',
            'members': get_team_members(team_name),
            'game_started': state.game_started
        }, room=team_name)
        if len(team_info['players']) == 2:
            team_info['status'] = 'paired'
            emit('team_status_update', {
                'team_name': team_name,
                'status': 'paired',
                'members': get_team_members(team_name),
                'game_started': state.game_started
            }, room=team_name)
            emit_dashboard_team_update()  # Force immediate dashboard update
        
        emit_dashboard_team_update()
        
        # Ensure database and memory are consistent
        try:
            from src.sockets.game import validate_team_sessions, sync_team_state
            # First validate to fix any duplicate SIDs
            validate_team_sessions(team_name)
            # Then sync to ensure consistency
            sync_team_state(team_name)
        except ImportError:
            print("Warning: Could not import sync_team_state function")
        
        if state.game_started and len(team_info['players']) == 2:
            socketio.emit('game_start', {'game_started': True}, room=team_name)
            start_new_round_for_pair(team_name)
    except Exception as e:
        print(f"Error in on_join_team: {str(e)}")
        traceback.print_exc()
        emit('error', {'message': f'Error joining team: {str(e)}'})

@socketio.on('reactivate_team')
def on_reactivate_team(data):
    try:
        team_name = data.get('team_name')
        sid = request.sid
        
        if not team_name:
            emit('error', {'message': 'Team name is required'}); return
            
        # Find the inactive team in the database
        with app.app_context():
            team = Teams.query.filter_by(team_name=team_name, is_active=False).first()
            if not team:
                emit('error', {'message': 'Team not found or is already active'}); return
                
            # Check if team name would conflict with any active team
            if team_name in state.active_teams:
                emit('error', {'message': 'An active team with this name already exists'}); return
                
            # Reactivate the team
            team.is_active = True
            team.player1_session_id = sid
            db.session.commit()
            
            # Set up team state with proper game initialization
            state.active_teams[team_name] = {
                'players': [sid],
                'team_id': team.team_id,
                'current_round_number': 0,
                'current_db_round_id': None,
                'combo_tracker': {},
                'answered_current_round': {},
                'status': 'waiting_pair'
            }
            state.player_to_team[sid] = team_name
            state.team_id_to_name[team.team_id] = team_name
            
            # Join the socket room
            join_room(team_name)
            
            # Notify client
            emit('team_created', {
                'team_name': team_name,
                'team_id': team.team_id,
                'message': 'Team reactivated successfully. Waiting for another player.',
                'game_started': state.game_started
            })
            
            # Update all clients about available teams
            socketio.emit('teams_updated', {
                'teams': get_available_teams_list(),
                'game_started': state.game_started
            })
            
            # Ensure team state is valid
            try:
                from src.sockets.game import validate_team_sessions, sync_team_state
                validate_team_sessions(team_name)
                sync_team_state(team_name)
            except ImportError:
                print("Warning: Could not import validation functions")
                
            # Update dashboard
            emit_dashboard_team_update()
            
    except Exception as e:
        print(f"Error in on_reactivate_team: {str(e)}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': f'Error reactivating team: {str(e)}'})

@socketio.on('leave_team')
def on_leave_team(data):
    try:
        sid = request.sid
        if sid not in state.player_to_team:
            emit('error', {'message': 'You are not in a team.'}); return
        team_name = state.player_to_team[sid]
        team_info = state.active_teams.get(team_name)
        if not team_info:
            del state.player_to_team[sid]
            emit('error', {'message': 'Team info not found, you have been removed.'}); return

        db_team = Teams.query.get(team_info['team_id'])
        if sid in team_info['players']:
            # Get the player's index BEFORE removing them from the array
            player_index = team_info['players'].index(sid)
            print(f"Player {sid} was at index {player_index} in team {team_name}")
            
            # Update database based on player position
            if db_team:
                if player_index == 0:
                    # Only clear if the SID matches what we're removing
                    if db_team.player1_session_id == sid:
                        db_team.player1_session_id = None
                        print(f"Removed player1 session ID: {sid}")
                    else:
                        print(f"Warning: player1_session_id {db_team.player1_session_id} doesn't match leaving SID {sid}")
                elif player_index == 1:
                    # Only clear if the SID matches what we're removing
                    if db_team.player2_session_id == sid:
                        db_team.player2_session_id = None
                        print(f"Removed player2 session ID: {sid}")
                    else:
                        print(f"Warning: player2_session_id {db_team.player2_session_id} doesn't match leaving SID {sid}")
            
            # Now remove the player from the team's players list
            team_info['players'].remove(sid)

            # Handle team state
            if len(team_info['players']) > 0:
                # Team still has players
                team_info['status'] = 'waiting_pair'
                emit('player_left', {'message': 'A team member has left.'}, room=team_name)
                emit('team_status_update', {
                    'team_name': team_name,
                    'status': 'waiting_for_player',
                    'members': get_team_members(team_name),
                    'game_started': state.game_started
                }, room=team_name)
            else:
                # No players left
                del state.active_teams[team_name]
                if team_info['team_id'] in state.team_id_to_name:
                    del state.team_id_to_name[team_info['team_id']]
                if db_team:
                    existing_inactive = Teams.query.filter_by(team_name=team_name, is_active=False).first()
                    if existing_inactive:
                        db_team.team_name = f"{team_name}_{db_team.team_id}"
                    db_team.is_active = False

            emit('left_team_success', {'message': 'You have left the team.'}, room=sid)
            leave_room(team_name, sid=sid)
            del state.player_to_team[sid]
            
            if db_team:
                db.session.commit()
                
            # Ensure database and memory are consistent if team still exists
            if team_name in state.active_teams:
                try:
                    from src.sockets.game import validate_team_sessions, sync_team_state
                    # First validate to fix any duplicate SIDs
                    validate_team_sessions(team_name)
                    # Then sync to ensure consistency
                    sync_team_state(team_name)
                except ImportError:
                    print("Warning: Could not import sync_team_state function")
                
            socketio.emit('teams_updated', {
                'teams': get_available_teams_list(),
                'game_started': state.game_started
            })
            emit_dashboard_team_update()
    except Exception as e:
        print(f"Error in on_leave_team: {str(e)}")
        traceback.print_exc()
        emit('error', {'message': f'Error leaving team: {str(e)}'})
