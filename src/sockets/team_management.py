from datetime import datetime
from flask import request
from flask_socketio import emit, join_room, leave_room
from src.config import socketio, db
from src.state import state
from src.models.quiz_models import Teams, PairQuestionRounds, Answers
from src.sockets.dashboard import emit_dashboard_team_update, emit_dashboard_full_update
from src.game_logic import start_new_round_for_pair

def get_available_teams_list():
    try:
        return [{'team_name': name, 'team_id': info['team_id']}
                for name, info in state.active_teams.items() if len(info['participants']) < 2]
    except Exception as e:
        print(f"Error in get_available_teams_list: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def get_team_members(team_name):
    try:
        team_info = state.active_teams.get(team_name)
        if not team_info: return []
        return team_info['participants']
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
                    # Remove participant from team
                    if sid in team_info['participants']:
                        team_info['participants'].remove(sid)
                        
                        # Update the database
                        if db_team.participant1_session_id == sid:
                            db_team.participant1_session_id = None
                        elif db_team.participant2_session_id == sid:
                            db_team.participant2_session_id = None
                            
                        # Notify remaining participants
                        remaining_participants = team_info['participants']
                        if remaining_participants:
                            emit('partner_left', {'message': 'A team member has disconnected.'}, room=team_name)
                            # Keep team active with remaining participant
                            emit('team_status_update', {
                                'team_name': team_name,
                                'status': 'waiting_for_partner',
                                'members': remaining_participants,
                                'game_started': state.game_started
                            }, room=team_name)
                        else:
                            # If no participants left, mark team as inactive
                            existing_inactive = Teams.query.filter_by(team_name=team_name, is_active=False).first()
                            if existing_inactive:
                                db_team.team_name = f"{team_name}_{db_team.team_id}"
                            db_team.is_active = False
                            del state.active_teams[team_name]
                            if team_info['team_id'] in state.team_id_to_name:
                                del state.team_id_to_name[team_info['team_id']]
                        
                        db.session.commit()
                        
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
            'participants': [sid],
            'team_id': new_team_db.team_id,
            'current_round_number': 0,
            'combo_tracker': {},
            'answered_current_round': {}
        }
        state.participant_to_team[sid] = team_name
        state.team_id_to_name[new_team_db.team_id] = team_name
        join_room(team_name)
        
        emit('team_created', {
            'team_name': team_name,
            'team_id': new_team_db.team_id,
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
        if len(team_info['participants']) >= 2:
            emit('error', {'message': 'Team is already full'}); return
        if sid in team_info['participants']:
            emit('error', {'message': 'You are already in this team'}); return

        team_info['participants'].append(sid)
        state.participant_to_team[sid] = team_name
        join_room(team_name)
        
        db_team = Teams.query.get(team_info['team_id'])
        if db_team:
            if not db_team.participant1_session_id:
                db_team.participant1_session_id = sid
            else:
                db_team.participant2_session_id = sid
            db.session.commit()

        emit('team_joined', {
            'team_name': team_name,
            'message': f'You joined team {team_name}.',
            'game_started': state.game_started
        }, room=sid)
        
        # Notify all team members
        emit('partner_joined', {
            'team_name': team_name,
            'message': f'A new participant joined your team!',
            'game_started': state.game_started
        }, room=team_name)
        
        socketio.emit('teams_updated', {
            'teams': get_available_teams_list(),
            'game_started': state.game_started
        })
        
        emit('team_status_update', {
            'team_name': team_name,
            'status': 'full' if len(team_info['participants']) == 2 else 'waiting_for_partner',
            'members': get_team_members(team_name),
            'game_started': state.game_started
        }, room=team_name)
        
        emit_dashboard_team_update()
        
        if state.game_started and len(team_info['participants']) == 2:
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
        if sid in team_info['participants']:
            team_info['participants'].remove(sid)
            
            # Update database
            if db_team:
                if db_team.participant1_session_id == sid:
                    db_team.participant1_session_id = None
                elif db_team.participant2_session_id == sid:
                    db_team.participant2_session_id = None

            # Handle team state
            if len(team_info['participants']) > 0:
                # Team still has participants
                emit('partner_left', {'message': 'A team member has left.'}, room=team_name)
                emit('team_status_update', {
                    'team_name': team_name,
                    'status': 'waiting_for_partner',
                    'members': get_team_members(team_name),
                    'game_started': state.game_started
                }, room=team_name)
            else:
                # No participants left
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