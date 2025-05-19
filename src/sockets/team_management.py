from datetime import datetime
from flask import request
from flask_socketio import emit, join_room, leave_room
from src.config import app, socketio, db
from src.state import state
from src.models.quiz_models import Teams, PairQuestionRounds, Answers
from src.sockets.dashboard import emit_dashboard_team_update, emit_dashboard_full_update
from src.game_logic import start_new_round_for_pair

def _update_team_active_status_and_state(team_name, team_info, db_team):
    """
    Updates in-memory and DB state for a team after a player leaves/disconnects.
    Ensures consistency between DB and memory state, and proper active/inactive status.
    """
    # Get current DB player state
    p1_sid = db_team.player1_session_id
    p2_sid = db_team.player2_session_id
    
    # If both slots are empty, team becomes inactive
    if p1_sid is None and p2_sid is None:
        db_team.is_active = False
        if team_name in state.active_teams:
            del state.active_teams[team_name]
        if team_info and team_info['team_id'] in state.team_id_to_name:
            del state.team_id_to_name[team_info['team_id']]
        print(f"Team {team_name} marked inactive as it's empty")
    else:
        # At least one player remains
        db_team.is_active = True
        if team_info:
            # Reconstruct players list from DB state
            team_info['players'] = []
            if p1_sid:
                team_info['players'].append(p1_sid)
            if p2_sid and p2_sid != p1_sid:  # Ensure no duplicate SIDs
                team_info['players'].append(p2_sid)
            
            team_info['status'] = 'waiting_pair'
            
            # Ensure team is properly tracked in active_teams
            if team_name not in state.active_teams and db_team.is_active:
                state.active_teams[team_name] = team_info
                state.team_id_to_name[db_team.team_id] = team_name

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
        
        if sid not in state.dashboard_clients:
            state.connected_players.add(sid)
            emit_dashboard_full_update()
        
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
            return

        # Remove from connected players
        if sid in state.connected_players:
            state.connected_players.remove(sid)
            emit_dashboard_full_update()

        # Handle team-related disconnection
        if sid in state.player_to_team:
            team_name = state.player_to_team[sid]
            team_info = state.active_teams.get(team_name)
            
            if team_info and (db_team := Teams.query.get(team_info['team_id'])):
                # Record original slot before clearing it
                original_slot = None
                if db_team.player1_session_id == sid:
                    original_slot = 0
                    db_team.player1_session_id = None
                elif db_team.player2_session_id == sid:
                    original_slot = 1
                    db_team.player2_session_id = None
                
                if original_slot is not None:
                    # Store disconnection info for potential rejoin
                    state.recently_disconnected_sids[sid] = {
                        'team_id': db_team.team_id,
                        'original_slot': original_slot,
                        'timestamp': datetime.utcnow()
                    }
                    print(f"Recorded disconnect for SID {sid} from team {team_name}, slot {original_slot}")
                
                if sid in team_info['players']:
                    team_info['players'].remove(sid)
                
                # Update team state
                _update_team_active_status_and_state(team_name, team_info, db_team)
                db.session.commit()
                
                # Clean up player mapping
                del state.player_to_team[sid]
                
                # Update clients
                emit_dashboard_team_update()
                socketio.emit('teams_updated', {
                    'teams': get_available_teams_list(),
                    'game_started': state.game_started
                })
                
                # Leave the room
                try:
                    leave_room(team_name, sid=sid)
                except Exception as e:
                    print(f"Error leaving room: {str(e)}")
                
                # Notify remaining players if any
                if team_info['players']:
                    emit('player_left', {'message': 'A team member has disconnected.'}, room=team_name)
                    emit('team_status_update', {
                        'team_name': team_name,
                        'status': 'waiting_pair',
                        'members': team_info['players'],
                        'game_started': state.game_started
                    }, room=team_name)
    
    except Exception as e:
        print(f"Disconnect handler error: {str(e)}")
        import traceback
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
        import traceback
        traceback.print_exc()
        emit('error', {'message': f'Error creating team: {str(e)}'})

@socketio.on('join_team')
def on_join_team(data):
    try:
        team_name = data.get('team_name')
        sid = request.sid
        if not team_name or team_name not in state.active_teams:
            emit('error', {'message': 'Team not found or invalid team name.'}); return
            
        team_info = state.active_teams[team_name]
        if len(team_info['players']) >= 2:
            emit('error', {'message': 'Team is already full.'}); return
        if sid in team_info['players']:
            emit('error', {'message': 'You are already in this team.'}); return

        db_team = Teams.query.get(team_info['team_id'])
        if not db_team:
            emit('error', {'message': 'Database consistency error: Team not found.'}); return

        # Robustness: Check for SID conflicts
        if db_team.player1_session_id == sid or db_team.player2_session_id == sid:
            emit('error', {'message': 'You are already a member of this team.'}); return
            
        # Add player to empty slot
        if not db_team.player1_session_id:
            db_team.player1_session_id = sid
        elif not db_team.player2_session_id:
            if db_team.player1_session_id == sid:
                emit('error', {'message': 'Cannot join as both players in the team.'}); return
            db_team.player2_session_id = sid
        
        team_info['players'].append(sid)
        state.player_to_team[sid] = team_name
        join_room(team_name)
        
        # Update team status
        db_team.is_active = True
        if len(team_info['players']) == 2:
            team_info['status'] = 'active'
            if db_team.player1_session_id == db_team.player2_session_id:
                print(f"CRITICAL ERROR: Team {team_name} has identical SIDs for P1 and P2: {db_team.player1_session_id}")
        else:
            team_info['status'] = 'waiting_pair'
            
        db.session.commit()

        emit('team_joined', {
            'team_name': team_name,
            'message': f'You joined team {team_name}.',
            'game_started': state.game_started
        }, room=sid)
        
        emit('player_joined', {
            'team_name': team_name,
            'message': 'A new player joined your team!',
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
        import traceback
        traceback.print_exc()
        emit('error', {'message': f'Error joining team: {str(e)}'})

@socketio.on('reactivate_team')
def on_reactivate_team(data):
    try:
        team_name = data.get('team_name')
        sid = request.sid
        
        if not team_name:
            emit('error', {'message': 'Team name is required'}); return
            
        with app.app_context():
            team = Teams.query.filter_by(team_name=team_name, is_active=False).first()
            if not team:
                emit('error', {'message': 'Team not found or is already active'}); return
                
            if team_name in state.active_teams:
                emit('error', {'message': 'An active team with this name already exists'}); return
                
            team.is_active = True
            team.player1_session_id = sid
            db.session.commit()
            
            state.active_teams[team_name] = {
                'players': [sid],
                'team_id': team.team_id,
                'current_round_number': 0,
                'combo_tracker': {},
                'answered_current_round': {},
                'status': 'waiting_pair'
            }
            state.player_to_team[sid] = team_name
            state.team_id_to_name[team.team_id] = team_name
            
            join_room(team_name)
            
            emit('team_created', {
                'team_name': team_name,
                'team_id': team.team_id,
                'message': 'Team reactivated successfully. Waiting for another player.',
                'game_started': state.game_started
            })
            
            socketio.emit('teams_updated', {
                'teams': get_available_teams_list(),
                'game_started': state.game_started
            })
            
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
        if not db_team:
            emit('error', {'message': 'Database team not found.'}); return
            
        if sid in team_info['players']:
            team_info['players'].remove(sid)
            
            # Update database
            if db_team.player1_session_id == sid:
                db_team.player1_session_id = None
            elif db_team.player2_session_id == sid:
                db_team.player2_session_id = None

            # Update team state
            _update_team_active_status_and_state(team_name, team_info, db_team)
            
            emit('left_team_success', {'message': 'You have left the team.'}, room=sid)
            leave_room(team_name, sid=sid)
            del state.player_to_team[sid]
            
            db.session.commit()
                
            socketio.emit('teams_updated', {
                'teams': get_available_teams_list(),
                'game_started': state.game_started
            })
            emit_dashboard_team_update()
            
            # Notify remaining players if any
            if team_info['players']:
                emit('player_left', {'message': 'A team member has left.'}, room=team_name)
                emit('team_status_update', {
                    'team_name': team_name,
                    'status': 'waiting_pair',
                    'members': get_team_members(team_name),
                    'game_started': state.game_started
                }, room=team_name)
    except Exception as e:
        print(f"Error in on_leave_team: {str(e)}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': f'Error leaving team: {str(e)}'})
