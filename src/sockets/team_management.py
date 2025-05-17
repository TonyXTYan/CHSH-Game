from datetime import datetime
from flask import request
from flask_socketio import emit, join_room, leave_room
from src.config import socketio, db
from src.state import state
from src.models.quiz_models import Teams, PairQuestionRounds, Answers
from src.sockets.dashboard import emit_dashboard_team_update, emit_dashboard_full_update
from src.game_logic import start_new_round_for_pair

def _archive_team(team_name, team_info, db_team):
    """Archive a team when all players are disconnected."""
    if team_name in state.active_teams:
        del state.active_teams[team_name]
    if team_info['team_id'] in state.team_id_to_name:
        del state.team_id_to_name[team_info['team_id']]
    if db_team:
        existing_inactive = Teams.query.filter_by(team_name=team_name, is_active=False).first()
        if existing_inactive:
            db_team.team_name = f"{team_name}_{db_team.team_id}"
        db_team.is_active = False
        db.session.commit()
    print(f"Team {team_name} archived as all players disconnected.")

    # Update dashboard about team archival
    emit_dashboard_team_update()
    socketio.emit('teams_updated', {
        'teams': get_available_teams_list(),
        'game_started': state.game_started
    })

def get_available_teams_list():
    try:
        current_sid = request.sid
        teams = []
        for name, info in state.active_teams.items():
            # Get team from database to check participant1_session_id
            db_team = Teams.query.get(info['team_id'])
            if not db_team:
                continue

            # Include teams without partner
            if not info.get('participant2_sid'):
                teams.append({
                    'team_name': name,
                    'creator_sid': info['creator_sid'],
                    'team_id': info['team_id']
                })
            # Include teams where user was creator (check both current sid and db session id)
            elif (info.get('creator_sid') == current_sid or 
                  db_team.participant1_session_id == current_sid) and not info.get('creator_connected', True):
                teams.append({
                    'team_name': name,
                    'creator_sid': info['creator_sid'],
                    'team_id': info['team_id'],
                    'rejoinable': True
                })
        return teams
    except Exception as e:
        print(f"Error in get_available_teams_list: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def get_team_members(team_name):
    try:
        team_info = state.active_teams.get(team_name)
        if not team_info: return []
        members = [team_info['creator_sid']]
        if team_info.get('participant2_sid'):
            members.append(team_info['participant2_sid'])
        return members
    except Exception as e:
        print(f"Error in get_team_members: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

@socketio.on('connect')
def handle_connect():
    try:
        print(f'Client connected: {request.sid}')
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
    print(f'Client disconnected: {request.sid}')
    try:
        if sid in state.dashboard_clients:
            state.dashboard_clients.remove(sid)
            print(f"Dashboard client disconnected: {sid}")

        if sid in state.participant_to_team:
            team_name = state.participant_to_team[sid]
            team_info = state.active_teams.get(team_name)
            if team_info:
                db_team = Teams.query.get(team_info['team_id'])
                if db_team:
                    creator_left = team_info['creator_sid'] == sid
                    partner_left = team_info.get('participant2_sid') == sid

                    if creator_left:
                        if team_info.get('participant2_sid'):
                            try:
                                emit('partner_left', {'message': 'The team creator has disconnected but you can continue playing. They may rejoin later.'}, room=team_info['participant2_sid'])
                            except Exception as e:
                                print(f"Error notifying partner of creator disconnect: {str(e)}")
                        
                        # Keep team active but mark creator as disconnected
                        team_info['creator_connected'] = False
                        print(f"Creator of team {team_name} disconnected but team remains active.")
                        
                        # Check if both players are now disconnected
                        if not team_info.get('participant2_sid'):
                            _archive_team(team_name, team_info, db_team)
                    
                    elif partner_left:
                        try:
                            emit('partner_left', {'message': 'Your partner has disconnected.'}, room=team_info['creator_sid'])
                        except Exception as e:
                            print(f"Error notifying partner of creator disconnect: {str(e)}")
                        
                        # Check if both players are now disconnected
                        if not team_info.get('creator_connected', True):
                            _archive_team(team_name, team_info, db_team)
                            return  # Exit since team is archived
                        
                        # Only update participant data if team wasn't archived
                        team_info['participant2_sid'] = None
                        db_team.participant2_session_id = None
                        print(f"Participant 2 left team {team_name}.")
                    
                    if creator_left or partner_left:
                        db.session.commit()
                        
                    try:
                        emit_dashboard_team_update()
                        socketio.emit('teams_updated', {
                            'teams': get_available_teams_list(),
                            'game_started': state.game_started
                        })
                        if not creator_left and team_info.get('creator_sid'):
                            emit('team_status_update', {
                                'team_name': team_name, 
                                'status': 'waiting_for_partner', 
                                'members': get_team_members(team_name),
                                'game_started': state.game_started
                            }, room=team_info['creator_sid'])
                    except Exception as e:
                        print(f"Error updating team status: {str(e)}")

                    try:
                        leave_room(team_name, sid=sid)
                    except Exception as e:
                        print(f"Error leaving room: {str(e)}")
                    del state.participant_to_team[sid]
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

        new_team_db = Teams(team_name=team_name, participant1_session_id=sid)
        db.session.add(new_team_db)
        db.session.commit()
        state.active_teams[team_name] = {
            'creator_sid': sid,
            'participant2_sid': None,
            'team_id': new_team_db.team_id,
            'current_round_number': 0,
            'combo_tracker': {},
            'p1_answered_current_round': False,
            'p2_answered_current_round': False,
            'creator_connected': True
        }
        state.participant_to_team[sid] = team_name
        state.team_id_to_name[new_team_db.team_id] = team_name
        join_room(team_name)
        
        emit('team_created', {
            'team_name': team_name, 
            'team_id': new_team_db.team_id, 
            'creator_sid': sid, 
            'message': 'Team created. Waiting for partner.',
            'game_started': state.game_started
        })
        
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
        team_info = state.active_teams[team_name]
        db_team = Teams.query.get(team_info['team_id'])
        if team_info.get('participant2_sid'):
            emit('error', {'message': 'Team is already full'}); return
        # Allow creator to rejoin their team
        # Match user against correct team role
        is_creator = False
        is_partner = False
        
        if db_team:
            if db_team.participant1_session_id == sid:
                # User was creator
                is_creator = True
            elif db_team.participant2_session_id == sid:
                # User was partner
                is_partner = True

        # Handle creator rejoining
        if is_creator and not team_info.get('creator_connected', True):
            # Update creator's session ID
            team_info['creator_sid'] = sid
            if db_team:
                db_team.participant1_session_id = sid
                db.session.commit()
            team_info['creator_connected'] = True
            join_room(team_name)
            state.participant_to_team[sid] = team_name
            emit('team_status_update', {
                'team_name': team_name,
                'status': 'creator_rejoined',
                'members': get_team_members(team_name),
                'game_started': state.game_started
            }, room=team_name)
            if team_info.get('participant2_sid'):
                emit('partner_rejoined', {'message': 'The team creator has rejoined!'}, room=team_info['participant2_sid'])
            return
        elif is_creator:
            emit('error', {'message': 'You cannot join your own team as a second participant'}); return
        
        # Handle partner rejoining
        if is_partner:
            team_info['participant2_sid'] = sid
            db_team.participant2_session_id = sid
            db.session.commit()
            join_room(team_name)
            state.participant_to_team[sid] = team_name
            emit('team_status_update', {
                'team_name': team_name,
                'status': 'partner_rejoined',
                'members': get_team_members(team_name),
                'game_started': state.game_started
            }, room=team_name)
            return

        # New partner joining
        if team_info.get('participant2_sid'):
            emit('error', {'message': 'Team is already full'}); return
            
        team_info['participant2_sid'] = sid
        state.participant_to_team[sid] = team_name
        join_room(team_name)
        db_team = Teams.query.get(team_info['team_id'])
        if db_team:
            db_team.participant2_session_id = sid
            db.session.commit()

        emit('team_joined', {
            'team_name': team_name, 
            'message': f'You joined team {team_name}.',
            'game_started': state.game_started
        }, room=sid)
        
        emit('partner_joined', {
            'team_name': team_name, 
            'partner_sid': sid, 
            'message': f'A partner ({sid}) joined your team!',
            'game_started': state.game_started
        }, room=team_info['creator_sid'])
        
        socketio.emit('teams_updated', {
            'teams': get_available_teams_list(),
            'game_started': state.game_started
        })
        
        emit('team_status_update', {
            'team_name': team_name, 
            'status': 'full', 
            'members': get_team_members(team_name),
            'game_started': state.game_started
        }, room=team_name)
        
        emit_dashboard_team_update()
        
        if state.game_started and team_info.get('participant2_sid'):
            socketio.emit('game_start', {'game_started': True}, room=team_name)
            start_new_round_for_pair(team_name)
    except Exception as e:
        print(f"Error in on_join_team: {str(e)}")
        traceback.print_exc()
        emit('error', {'message': f'Error joining team: {str(e)}'})

@socketio.on('leave_team')
def on_leave_team(data):
    try:
        sid = request.sid
        if sid not in state.participant_to_team:
            emit('error', {'message': 'You are not in a team.'}); return
        team_name = state.participant_to_team[sid]
        team_info = state.active_teams.get(team_name)
        if not team_info:
            del state.participant_to_team[sid]
            emit('error', {'message': 'Team info not found, you have been removed.'}); return

        db_team = Teams.query.get(team_info['team_id'])
        creator_leaving = team_info['creator_sid'] == sid

        if creator_leaving:
            emit('team_status_update', {'message': 'The team creator has left but may rejoin later.'}, room=team_name)
            team_info['creator_connected'] = False
            
            # Check if both players are now disconnected
            if not team_info.get('participant2_sid'):
                _archive_team(team_name, team_info, db_team)
                emit('left_team_success', {'message': 'You have left the team.'}, room=sid)
                return  # Exit since team is archived
        
        elif team_info.get('participant2_sid') == sid:
            # Check if both players are now disconnected
            if not team_info.get('creator_connected', True):
                _archive_team(team_name, team_info, db_team)
                emit('left_team_success', {'message': 'You have left the team.'}, room=sid)
                return  # Exit since team is archived
            
            team_info['participant2_sid'] = None
            if db_team:
                db_team.participant2_session_id = None
            emit('partner_left', {'message': 'Your partner has left the team.'}, room=team_info['creator_sid'])
            emit('team_status_update', {
                'team_name': team_name, 
                'status': 'waiting_for_partner', 
                'members': get_team_members(team_name),
                'game_started': state.game_started
            }, room=team_info['creator_sid'])
            emit('left_team_success', {'message': 'You have left the team.'}, room=sid)
        
        leave_room(team_name, sid=sid)
        del state.participant_to_team[sid]
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
