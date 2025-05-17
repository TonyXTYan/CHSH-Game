# First define the class for application state
class AppState:
    def __init__(self):
        self.active_teams = {}  # {team_name: {'creator_sid': sid, 'participant2_sid': None, 'team_id': db_team_id, 'current_round_number': 0, 'combo_tracker': {}, 'current_db_round_id': None, 'p1_answered_current_round': False, 'p2_answered_current_round': False}}
        self.participant_to_team = {}  # {sid: team_name}
        self.dashboard_clients = set() # Stores SIDs of connected dashboard clients
        self.game_started = False # Track if game has started
        # Store previous session mappings for reconnection
        self.previous_sessions = {} # {previous_sid: current_sid}

    def reset(self):
        self.active_teams.clear()
        self.participant_to_team.clear()
        self.dashboard_clients.clear()
        self.previous_sessions.clear()
        self.game_started = False

# Create singleton instance for state
state = AppState()

# Then, the rest of the file...
import eventlet
eventlet.monkey_patch()

import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, jsonify, request
from flask_socketio import SocketIO, emit, join_room, leave_room
from src.models.quiz_models import db, Teams, Answers, PairQuestionRounds, ItemEnum
import random
from datetime import datetime
import traceback

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'asdf#FGSgvasgf$5$WGT')

# Fix for SQLite URL format in render.com
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'quiz_app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', ping_timeout=60, ping_interval=25)

with app.app_context():
    db.create_all()
    # Reset all teams to inactive and clear all data on server start
    try:
        # Delete all answers first to avoid foreign key constraints
        Answers.query.delete()
        # Delete all question rounds
        PairQuestionRounds.query.delete()
        # Now handle teams
        active_teams_query = Teams.query.filter_by(is_active=True)
        teams = active_teams_query.all()
        for team in teams:
            # First check if there's already an inactive team with same name
            existing_inactive = Teams.query.filter_by(team_name=team.team_name, is_active=False).first()
            if existing_inactive:
                # If exists, we need to give this team a unique name before deactivating
                team.team_name = f"{team.team_name}_{team.team_id}"
            team.is_active = False
            db.session.flush()  # Flush changes for each team individually
        db.session.commit()
    except Exception as e:
        print(f"Error resetting data: {str(e)}")
        db.session.rollback()
    # Clear memory state
    state.reset()

@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    static_folder_path = app.static_folder
    if path == "dashboard": # Specific route for dashboard.html
        return send_from_directory(static_folder_path, 'dashboard.html')
    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

def get_serialized_active_teams():
    teams_list = []
    for name, info in state.active_teams.items():
        teams_list.append({
            'team_name': name,
            'team_id': info['team_id'],
            'participant1_sid': info['creator_sid'],
            'participant2_sid': info.get('participant2_sid'),
            'current_round_number': info.get('current_round_number', 0)
        })
    return teams_list

def emit_dashboard_team_update():
    try:
        serialized_teams = get_serialized_active_teams()
        for sid in state.dashboard_clients:
            socketio.emit('team_status_changed_for_dashboard', serialized_teams, room=sid)
    except Exception as e:
        print(f"Error in emit_dashboard_team_update: {str(e)}")
        traceback.print_exc()

def emit_dashboard_full_update(client_sid=None):
    try:
        with app.app_context():
            total_answers = Answers.query.count()
        update_data = {
            'active_teams': get_serialized_active_teams(),
            'total_answers_count': total_answers,
            'game_state': {
                'started': state.game_started
            }
        }
        if client_sid:
            socketio.emit('dashboard_update', update_data, room=client_sid)
        else:
            for dash_sid in state.dashboard_clients:
                socketio.emit('dashboard_update', update_data, room=dash_sid)
    except Exception as e:
        print(f"Error in emit_dashboard_full_update: {str(e)}")
        traceback.print_exc()

@socketio.on('dashboard_join')
def on_dashboard_join():
    try:
        sid = request.sid
        state.dashboard_clients.add(sid)
        print(f"Dashboard client connected: {sid}")
        emit_dashboard_full_update(client_sid=sid)
    except Exception as e:
        print(f"Error in on_dashboard_join: {str(e)}")
        traceback.print_exc()
        emit('error', {'message': f'Error joining dashboard: {str(e)}'})

@socketio.on('connect')
def handle_connect():
    try:
        print(f'Client connected: {request.sid}')
        emit('available_teams', get_available_teams_list())
    except Exception as e:
        print(f"Error in handle_connect: {str(e)}")
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
                                emit('partner_left', {'message': 'Your partner (creator) has disconnected.'}, room=team_info['participant2_sid'])
                                leave_room(team_name, sid=team_info['participant2_sid'])
                                del state.participant_to_team[team_info['participant2_sid']]
                            except Exception as e:
                                print(f"Error notifying partner of creator disconnect: {str(e)}")
                        
                        del state.active_teams[team_name]
                        # Check if there's already an inactive team with same name
                        existing_inactive = Teams.query.filter_by(team_name=team_name, is_active=False).first()
                        if existing_inactive:
                            # If exists, we need to give this team a unique name before deactivating
                            db_team.team_name = f"{team_name}_{db_team.team_id}"
                        db_team.is_active = False
                        print(f"Team {team_name} deactivated as creator disconnected.")
                    
                    elif partner_left:
                        try:
                            emit('partner_left', {'message': 'Your partner has disconnected.'}, room=team_info['creator_sid'])
                        except Exception as e:
                            print(f"Error notifying creator of partner disconnect: {str(e)}")
                        team_info['participant2_sid'] = None
                        db_team.participant2_session_id = None
                        print(f"Participant 2 left team {team_name}.")
                    
                    if creator_left or partner_left:
                        db.session.commit()
                        try:
                            emit_dashboard_team_update()
                            emit('teams_updated', get_available_teams_list(), broadcast=True)
                            if not creator_left and team_info.get('creator_sid'):
                                emit('team_status_update', 
                                    {'team_name': team_name, 'status': 'waiting_for_partner', 'members': get_team_members(team_name)}, 
                                    room=team_info['creator_sid'])
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

def get_available_teams_list():
    try:
        return [{'team_name': name, 'creator_sid': info['creator_sid'], 'team_id': info['team_id']} 
                for name, info in state.active_teams.items() if not info.get('participant2_sid')]
    except Exception as e:
        print(f"Error in get_available_teams_list: {str(e)}")
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
        traceback.print_exc()
        return []

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
        db.session.add(new_team_db); db.session.commit()
        state.active_teams[team_name] = {'creator_sid': sid, 'participant2_sid': None, 'team_id': new_team_db.team_id, 'current_round_number': 0, 'combo_tracker': {}, 'p1_answered_current_round': False, 'p2_answered_current_round': False}
        state.participant_to_team[sid] = team_name
        join_room(team_name)
        emit('team_created', {'team_name': team_name, 'team_id': new_team_db.team_id, 'creator_sid': sid, 'message': 'Team created. Waiting for partner.'})
        emit('teams_updated', get_available_teams_list(), broadcast=True)
        emit_dashboard_team_update()
    except Exception as e:
        print(f"Error in on_create_team: {str(e)}")
        traceback.print_exc()
        emit('error', {'message': f'Error creating team: {str(e)}'})

@socketio.on('join_team')
def on_join_team(data):
    try:
        team_name = data.get('team_name'); sid = request.sid
        if not team_name or team_name not in state.active_teams:
            emit('error', {'message': 'Team not found or invalid team name'}); return
        team_info = state.active_teams[team_name]
        if team_info.get('participant2_sid'):
            emit('error', {'message': 'Team is already full'}); return
        if team_info['creator_sid'] == sid:
            emit('error', {'message': 'You cannot join your own team as a second participant'}); return

        team_info['participant2_sid'] = sid
        state.participant_to_team[sid] = team_name
        join_room(team_name)
        db_team = Teams.query.get(team_info['team_id'])
        if db_team: db_team.participant2_session_id = sid; db.session.commit()

        emit('team_joined', {'team_name': team_name, 'message': f'You joined team {team_name}.'}, room=sid)
        emit('partner_joined', {'team_name': team_name, 'partner_sid': sid, 'message': f'A partner ({sid}) joined your team!'}, room=team_info['creator_sid'])
        emit('teams_updated', get_available_teams_list(), broadcast=True)
        emit('team_status_update', {'team_name': team_name, 'status': 'full', 'members': get_team_members(team_name)}, room=team_name)
        emit_dashboard_team_update()
    except Exception as e:
        print(f"Error in on_join_team: {str(e)}")
        traceback.print_exc()
        emit('error', {'message': f'Error joining team: {str(e)}'})

@socketio.on('verify_team_membership')
def on_verify_team_membership(data):
    try:
        team_name = data.get('team_name')
        previous_sid = data.get('previous_sid')
        current_sid = request.sid
        
        if not team_name or not previous_sid:
            emit('rejoin_team_failed', {'message': 'Missing team name or previous session ID'}); return
            
        # Check if team exists and is active
        team_info = state.active_teams.get(team_name)
        if not team_info:
            emit('rejoin_team_failed', {'message': 'Team not found or no longer active'}); return
            
        # Check if previous_sid matches creator or participant2
        is_creator = team_info['creator_sid'] == previous_sid
        is_participant2 = team_info.get('participant2_sid') == previous_sid
        
        if not is_creator and not is_participant2:
            emit('rejoin_team_failed', {'message': 'You were not a member of this team'}); return
            
        # Update session mapping
        state.previous_sessions[previous_sid] = current_sid
        
        # Update team info with new sid
        if is_creator:
            team_info['creator_sid'] = current_sid
            # Update in database
            db_team = Teams.query.get(team_info['team_id'])
            if db_team: 
                db_team.participant1_session_id = current_sid
                db.session.commit()
        elif is_participant2:
            team_info['participant2_sid'] = current_sid
            # Update in database
            db_team = Teams.query.get(team_info['team_id'])
            if db_team: 
                db_team.participant2_session_id = current_sid
                db.session.commit()
                
        # Update participant_to_team mapping
        state.participant_to_team[current_sid] = team_name
        if previous_sid in state.participant_to_team:
            del state.participant_to_team[previous_sid]
            
        # Join the room
        join_room(team_name)
        
        # Prepare current round info if exists
        current_round_data = None
        already_answered = False
        if team_info.get('current_db_round_id'):
            round_db = PairQuestionRounds.query.get(team_info['current_db_round_id'])
            if round_db:
                item = round_db.participant1_item.value if is_creator else round_db.participant2_item.value
                current_round_data = {
                    'round_id': team_info['current_db_round_id'],
                    'round_number': team_info['current_round_number'],
                    'item': item
                }
                # Check if already answered
                if is_creator and team_info.get('p1_answered_current_round'):
                    already_answered = True
                elif not is_creator and team_info.get('p2_answered_current_round'):
                    already_answered = True
        
        # Send success response
        status_message = "Team created! Waiting for a partner." if is_creator else "You have joined the team!"
        if team_info.get('participant2_sid') and is_creator:
            status_message = "Your team is full! Waiting for game to start."
            
        emit('rejoin_team_success', {
            'team_name': team_name,
            'status_message': status_message,
            'is_creator': is_creator,
            'current_round': current_round_data,
            'already_answered': already_answered
        })
        
        # Notify other team member if exists
        other_sid = team_info.get('participant2_sid') if is_creator else team_info['creator_sid']
        if other_sid and other_sid != current_sid:
            emit('partner_reconnected', {
                'message': 'Your partner has reconnected!'
            }, room=other_sid)
            
        # Update dashboard
        emit_dashboard_team_update()
        
    except Exception as e:
        print(f"Error in on_verify_team_membership: {str(e)}")
        traceback.print_exc()
        emit('rejoin_team_failed', {'message': f'Error verifying team membership: {str(e)}'})

@socketio.on('rejoin_team')
def on_rejoin_team(data):
    try:
        team_name = data.get('team_name')
        previous_sid = data.get('previous_sid')
        current_sid = request.sid
        
        if not team_name or not previous_sid:
            emit('rejoin_team_failed', {'message': 'Missing team name or previous session ID'}); return
            
        # Check if team exists and is active
        team_info = state.active_teams.get(team_name)
        if not team_info:
            emit('rejoin_team_failed', {'message': 'Team not found or no longer active'}); return
            
        # Check if previous_sid matches creator or participant2
        is_creator = team_info['creator_sid'] == previous_sid
        is_participant2 = team_info.get('participant2_sid') == previous_sid
        
        if not is_creator and not is_participant2:
            emit('rejoin_team_failed', {'message': 'You were not a member of this team'}); return
            
        # Update session mapping
        state.previous_sessions[previous_sid] = current_sid
        
        # Update team info with new sid
        if is_creator:
            team_info['creator_sid'] = current_sid
            # Update in database
            db_team = Teams.query.get(team_info['team_id'])
            if db_team: 
                db_team.participant1_session_id = current_sid
                db.session.commit()
        elif is_participant2:
            team_info['participant2_sid'] = current_sid
            # Update in database
            db_team = Teams.query.get(team_info['team_id'])
            if db_team: 
                db_team.participant2_session_id = current_sid
                db.session.commit()
                
        # Update participant_to_team mapping
        state.participant_to_team[current_sid] = team_name
        if previous_sid in state.participant_to_team:
            del state.participant_to_team[previous_sid]
            
        # Join the room
        join_room(team_name)
        
        # Prepare current round info if exists
        current_round_data = None
        already_answered = False
        if team_info.get('current_db_round_id'):
            round_db = PairQuestionRounds.query.get(team_info['current_db_round_id'])
            if round_db:
                item = round_db.participant1_item.value if is_creator else round_db.participant2_item.value
                current_round_data = {
                    'round_id': team_info['current_db_round_id'],
                    'round_number': team_info['current_round_number'],
                    'item': item
                }
                # Check if already answered
                if is_creator and team_info.get('p1_answered_current_round'):
                    already_answered = True
                elif not is_creator and team_info.get('p2_answered_current_round'):
                    already_answered = True
        
        # Send success response
        status_message = "Team created! Waiting for a partner." if is_creator else "You have joined the team!"
        if team_info.get('participant2_sid') and is_creator:
            status_message = "Your team is full! Waiting for game to start."
            
        emit('rejoin_team_success', {
            'team_name': team_name,
            'status_message': status_message,
            'is_creator': is_creator,
            'current_round': current_round_data,
            'already_answered': already_answered
        })
        
        # Notify other team member if exists
        other_sid = team_info.get('participant2_sid') if is_creator else team_info['creator_sid']
        if other_sid and other_sid != current_sid:
            emit('partner_reconnected', {
                'message': 'Your partner has reconnected!'
            }, room=other_sid)
            
        # Update dashboard
        emit_dashboard_team_update()
        
    except Exception as e:
        print(f"Error in on_rejoin_team: {str(e)}")
        traceback.print_exc()
        emit('rejoin_team_failed', {'message': f'Error rejoining team: {str(e)}'})

@socketio.on('leave_team')
def on_leave_team(data):
    try:
        sid = request.sid
        if sid not in state.participant_to_team: emit('error', {'message': 'You are not in a team.'}); return
        team_name = state.participant_to_team[sid]
        team_info = state.active_teams.get(team_name)
        if not team_info: del state.participant_to_team[sid]; emit('error', {'message': 'Team info not found, you have been removed.'}); return

        db_team = Teams.query.get(team_info['team_id'])
        creator_leaving = team_info['creator_sid'] == sid

        if creator_leaving:
            emit('team_disbanded', {'message': 'The team creator has left. The team is disbanded.'}, room=team_name)
            if team_info.get('participant2_sid'):
                leave_room(team_name, sid=team_info['participant2_sid'])
                del state.participant_to_team[team_info['participant2_sid']]
            del state.active_teams[team_name]
            if db_team:
                # Check if there's already an inactive team with same name
                existing_inactive = Teams.query.filter_by(team_name=team_name, is_active=False).first()
                if existing_inactive:
                    # If exists, we need to give this team a unique name before deactivating
                    db_team.team_name = f"{team_name}_{db_team.team_id}"
                db_team.is_active = False
        elif team_info.get('participant2_sid') == sid:
            team_info['participant2_sid'] = None
            if db_team: db_team.participant2_session_id = None
            emit('partner_left', {'message': 'Your partner has left the team.'}, room=team_info['creator_sid'])
            emit('team_status_update', {'team_name': team_name, 'status': 'waiting_for_partner', 'members': get_team_members(team_name)}, room=team_info['creator_sid'])
            emit('left_team_success', {'message': 'You have left the team.'}, room=sid)
        
        leave_room(team_name, sid=sid)
        del state.participant_to_team[sid]
        if db_team: db.session.commit()
        emit('teams_updated', get_available_teams_list(), broadcast=True)
        emit_dashboard_team_update()
    except Exception as e:
        print(f"Error in on_leave_team: {str(e)}")
        traceback.print_exc()
        emit('error', {'message': f'Error leaving team: {str(e)}'})

QUESTION_ITEMS = [ItemEnum.A, ItemEnum.B, ItemEnum.C, ItemEnum.D]
TARGET_COMBO_REPEATS = 3

def start_new_round_for_pair(team_name):
    try:
        team_info = state.active_teams.get(team_name)
        if not team_info or not team_info.get('participant2_sid'): return

        team_info['current_round_number'] += 1
        round_number = team_info['current_round_number']
        combo_tracker = team_info.get('combo_tracker', {})
        all_possible_combos = [(i1, i2) for i1 in QUESTION_ITEMS for i2 in QUESTION_ITEMS]
        random.shuffle(all_possible_combos)
        chosen_combo = next((c for c in all_possible_combos if combo_tracker.get((c[0].value, c[1].value), 0) < TARGET_COMBO_REPEATS), random.choice(all_possible_combos))
        
        p1_item, p2_item = chosen_combo
        combo_key = (p1_item.value, p2_item.value)
        combo_tracker[combo_key] = combo_tracker.get(combo_key, 0) + 1
        team_info['combo_tracker'] = combo_tracker

        new_round_db = PairQuestionRounds(team_id=team_info['team_id'], round_number_for_team=round_number, participant1_item=p1_item, participant2_item=p2_item)
        db.session.add(new_round_db); db.session.commit()

        team_info['current_db_round_id'] = new_round_db.round_id
        team_info['p1_answered_current_round'] = False
        team_info['p2_answered_current_round'] = False

        socketio.emit('new_question', {'round_id': new_round_db.round_id, 'round_number': round_number, 'item': p1_item.value}, room=team_info['creator_sid'])
        socketio.emit('new_question', {'round_id': new_round_db.round_id, 'round_number': round_number, 'item': p2_item.value}, room=team_info.get('participant2_sid'))
        print(f"Team {team_name} round {round_number}: P1 gets {p1_item.value}, P2 gets {p2_item.value}")
        emit_dashboard_team_update()
    except Exception as e:
        print(f"Error in start_new_round_for_pair: {str(e)}")
        traceback.print_exc()

@socketio.on('submit_answer')
def on_submit_answer(data):
    try:
        sid = request.sid
        if sid not in state.participant_to_team: emit('error', {'message': 'You are not in a team or session expired.'}); return
        team_name = state.participant_to_team[sid]
        team_info = state.active_teams.get(team_name)
        if not team_info or not team_info.get('participant2_sid'): emit('error', {'message': 'Team not valid or partner missing.'}); return

        round_id = data.get('round_id'); assigned_item_str = data.get('item'); response_bool = data.get('answer')
        if round_id != team_info.get('current_db_round_id') or assigned_item_str is None or response_bool is None:
            emit('error', {'message': 'Invalid answer submission data.'}); return
        try: assigned_item_enum = ItemEnum(assigned_item_str)
        except ValueError: emit('error', {'message': 'Invalid item in answer.'}); return

        is_p1 = team_info['creator_sid'] == sid
        if (is_p1 and team_info.get('p1_answered_current_round')) or (not is_p1 and team_info.get('p2_answered_current_round')):
            emit('error', {'message': 'You have already answered this round.'}); return

        new_answer_db = Answers(team_id=team_info['team_id'], participant_session_id=sid, question_round_id=round_id, assigned_item=assigned_item_enum, response_value=response_bool, timestamp=datetime.utcnow())
        db.session.add(new_answer_db)
        round_db_entry = PairQuestionRounds.query.get(round_id)
        if not round_db_entry: emit('error', {'message': 'Round not found in DB.'}); db.session.rollback(); return

        if is_p1: team_info['p1_answered_current_round'] = True; round_db_entry.p1_answered_at = datetime.utcnow()
        else: team_info['p2_answered_current_round'] = True; round_db_entry.p2_answered_at = datetime.utcnow()
        db.session.commit()
        emit('answer_confirmed', {'message': 'Answer received.'}, room=sid)

        # Emit to dashboard
        answer_for_dash = {
            'timestamp': new_answer_db.timestamp.isoformat(),
            'team_name': team_name,
            'team_id': team_info['team_id'],
            'participant_session_id': sid,
            'question_round_id': round_id,
            'assigned_item': assigned_item_str,
            'response_value': response_bool
        }
        for dash_sid in state.dashboard_clients:
            socketio.emit('new_answer_for_dashboard', answer_for_dash, room=dash_sid)
        emit_dashboard_full_update()

        if team_info.get('p1_answered_current_round') and team_info.get('p2_answered_current_round'):
            print(f"Both participants in team {team_name} answered round {team_info['current_round_number']}.")
            socketio.emit('round_complete', {'team_name': team_name, 'round_number': team_info['current_round_number']}, room=team_name)
            start_new_round_for_pair(team_name)
    except Exception as e:
        print(f"Error in on_submit_answer: {str(e)}")
        traceback.print_exc()
        emit('error', {'message': f'Error submitting answer: {str(e)}'})

@app.route('/api/dashboard/data', methods=['GET'])
def get_dashboard_data():
    try:
        all_answers = Answers.query.order_by(Answers.timestamp.asc()).all()
        answers_data = [
            {
                'answer_id': ans.answer_id,
                'team_id': ans.team_id,
                'team_name': Teams.query.get(ans.team_id).team_name if Teams.query.get(ans.team_id) else 'N/A',
                'participant_session_id': ans.participant_session_id,
                'question_round_id': ans.question_round_id,
                'assigned_item': ans.assigned_item.value,
                'response_value': ans.response_value,
                'timestamp': ans.timestamp.isoformat()
            } for ans in all_answers
        ]
        return jsonify({'answers': answers_data}), 200
    except Exception as e:
        print(f"Error in get_dashboard_data: {str(e)}")
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@socketio.on('start_game')
def on_start_game():
    try:
        if request.sid in state.dashboard_clients:
            state.game_started = True
            # Notify teams and dashboard that game has started
            for team_name, team_info in state.active_teams.items():
                if team_info.get('participant2_sid'):  # Only notify full teams
                    socketio.emit('game_start', room=team_name)
            
            # Notify dashboard
            for dashboard_sid in state.dashboard_clients:
                socketio.emit('game_started', room=dashboard_sid)
            # Start first round for all full teams
            for team_name, team_info in state.active_teams.items():
                if team_info.get('participant2_sid'): # If team is full
                    start_new_round_for_pair(team_name)
    except Exception as e:
        print(f"Error in on_start_game: {str(e)}")
        traceback.print_exc()
        emit('error', {'message': f'Error starting game: {str(e)}'})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)
