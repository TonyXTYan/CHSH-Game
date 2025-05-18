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
        print(f"DEBUG: get_available_teams_list called. Current state.active_teams: {state.active_teams}") # Log current state
        # Get active teams that aren't full
        active_teams_data = [{'team_name': name, 'team_id': info['team_id'], 'is_active': True, 'players_count': len(info['players']), 'status': info.get('status')}
                       for name, info in state.active_teams.items() if len(info['players']) < 2]
        print(f"DEBUG: active_teams_data (joinable from state.active_teams): {active_teams_data}")
        
        # Get inactive teams from database
        inactive_teams_list = [] # Initialize to ensure it's a list
        with app.app_context():
            inactive_teams_db = Teams.query.filter_by(is_active=False).all()
            inactive_teams_list = [{'team_name': team.team_name, 'team_id': team.team_id, 'is_active': False}
                                 for team in inactive_teams_db]
        print(f"DEBUG: inactive_teams_list (from DB): {inactive_teams_list}")
        
        combined_list = active_teams_data + inactive_teams_list
        print(f"DEBUG: get_available_teams_list returning: {combined_list}") # Log returned list
        return combined_list
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
    team_name_affected = None
    team_info_affected = None # Use a different name to avoid conflict with team_info from loop

    try:
        if sid in state.dashboard_clients:
            state.dashboard_clients.remove(sid)
            print(f"Dashboard client disconnected: {sid}")
            # No further team list updates needed if it was just a dashboard client

        if sid in state.connected_players:
            state.connected_players.remove(sid)
            # This might trigger a full dashboard update if player counts are global

        if sid in state.player_to_team:
            team_name = state.player_to_team.pop(sid) # Remove mapping
            team_name_affected = team_name
            current_team_info = state.active_teams.get(team_name) # Use current_team_info

            if current_team_info: # Check if current_team_info exists
                team_info_affected = current_team_info # For logging outside
                db_team = Teams.query.get(current_team_info['team_id'])

                if sid in current_team_info['players']:
                    current_team_info['players'].remove(sid)

                if db_team:
                    if db_team.player1_session_id == sid:
                        db_team.player1_session_id = None
                    elif db_team.player2_session_id == sid:
                        db_team.player2_session_id = None
                    # No commit yet, will do it after state update

                if not current_team_info['players']:  # No players left in the team
                    print(f"Team {team_name} is now empty. Marking inactive.")
                    if team_name in state.active_teams:
                        del state.active_teams[team_name]
                    if current_team_info['team_id'] in state.team_id_to_name:
                        del state.team_id_to_name[current_team_info['team_id']]
                    if db_team:
                        db_team.is_active = False
                else:  # One player remains
                    print(f"Team {team_name} has one player remaining. Status: waiting_pair.")
                    current_team_info['status'] = 'waiting_pair' # Explicitly update server state
                    if db_team:
                        db_team.is_active = True # Ensure DB reflects it's active but waiting

                    # Notify the remaining player in the team
                    emit('player_left', {'message': 'The other player has disconnected.'}, room=team_name)
                    emit('team_status_update', {
                        'team_name': team_name,
                        'status': 'waiting_pair',
                        'members': current_team_info['players'],
                        'game_started': state.game_started
                    }, room=team_name)
                
                if db_team:
                    db.session.commit()
            
            try:
                leave_room(team_name, sid=sid)
            except Exception as e: # pragma: no cover
                print(f"Error leaving room {team_name} for sid {sid}: {str(e)}")

        # Always emit updates that refresh lists for all clients,
        # as a team's availability might have changed.
        # These functions should correctly fetch the current state.
        print(f"DEBUG: Disconnect affecting team: {team_name_affected}, info from disconnect: {team_info_affected}")
        print(f"DEBUG: state.active_teams before final emits (in disconnect): {state.active_teams}")
        
        current_available_teams = get_available_teams_list() # Call it once
        print(f"DEBUG: Teams list generated by get_available_teams_list for 'teams_updated' event: {current_available_teams}")

        emit_dashboard_full_update() # Ensures dashboard has the latest overall state
        socketio.emit('teams_updated', {
            'teams': current_available_teams, # Use the fetched list
            'game_started': state.game_started
        })

    except Exception as e: # pragma: no cover
        print(f"Error in handle_disconnect for SID {sid}: {str(e)}")
        import traceback
        traceback.print_exc()
        # Attempt to emit updates even if there was an error partway through
        try:
            emit_dashboard_full_update()
            socketio.emit('teams_updated', {
                'teams': get_available_teams_list(),
                'game_started': state.game_started
            })
        except Exception as e_final:
            print(f"Error during final emit in disconnect handler: {str(e_final)}")

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
            emit('error', {'message': 'Team not found or invalid team name.'})
            return
        team_info = state.active_teams[team_name]
        if len(team_info['players']) >= 2:
            emit('error', {'message': 'Team is already full.'})
            return
        if sid in team_info['players']:
            emit('error', {'message': 'You are already in this team.'})
            return

        team_info['players'].append(sid)
        state.player_to_team[sid] = team_name
        join_room(team_name)
        
        db_team = Teams.query.get(team_info['team_id'])
        if db_team:
            if not db_team.player1_session_id:
                db_team.player1_session_id = sid
            elif not db_team.player2_session_id:
                db_team.player2_session_id = sid
            db_team.is_active = True # Ensure team is marked active in DB
            db.session.commit()

        # Update team status if now full
        if len(team_info['players']) == 2:
            team_info['status'] = 'active'
            # Potentially start the first round if game has started and team is ready
            # This logic might be elsewhere or need to be added if auto-start is desired
            # For now, just updating status for dashboard
            if state.game_started:
                start_new_round_for_pair(team_name, team_info)


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
        
        emit('team_status_update', {
            'team_name': team_name,
            'status': 'full' if len(team_info['players']) == 2 else 'waiting_pair',
            'members': get_team_members(team_name),
            'game_started': state.game_started
        }, room=team_name)
        if len(team_info['players']) == 2:
            emit('team_status_update', {'status': 'paired'}, room=team_name)
        
        emit_dashboard_team_update()
        
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
            
            # Set up team state
            state.active_teams[team_name] = {
                'players': [sid],
                'team_id': team.team_id,
                'current_round_number': 0,
                'combo_tracker': {},
                'answered_current_round': {},
                'status': 'waiting_pair'  # Ensure this is waiting_pair
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
            team_info['players'].remove(sid)
            
            # Update database
            if db_team:
                if db_team.player1_session_id == sid:
                    db_team.player1_session_id = None
                elif db_team.player2_session_id == sid:
                    db_team.player2_session_id = None

            # Handle team state
            if len(team_info['players']) > 0:
                # Team still has players
                emit('player_left', {'message': 'A team member has left.'}, room=team_name)
                emit('team_status_update', {
                    'team_name': team_name,
                    'status': 'waiting_pair', # Changed from waiting_for_player
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
                
            socketio.emit('teams_updated', {
                'teams': get_available_teams_list(),
                'game_started': state.game_started
            })
            emit_dashboard_team_update()
    except Exception as e:
        print(f"Error in on_leave_team: {str(e)}")
        traceback.print_exc()
        emit('error', {'message': f'Error leaving team: {str(e)}'})
