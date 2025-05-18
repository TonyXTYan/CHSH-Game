from flask import jsonify
from src.config import app, socketio, db
from src.state import state
from src.models.quiz_models import Teams, Answers, PairQuestionRounds
from flask_socketio import emit
from src.game_logic import start_new_round_for_pair
from time import time
import hashlib

# Store last activity time for each dashboard client
dashboard_last_activity = {}

@socketio.on('keep_alive')
def on_keep_alive():
    try:
        from flask import request
        sid = request.sid
        if sid in state.dashboard_clients:
            dashboard_last_activity[sid] = time()
            emit('keep_alive_ack', room=sid)
    except Exception as e:
        print(f"Error in on_keep_alive: {str(e)}")
        import traceback
        traceback.print_exc()

def compute_team_hashes(team_id):
    try:
        # Get all rounds and answers for this team in chronological order
        rounds = PairQuestionRounds.query.filter_by(team_id=team_id).order_by(PairQuestionRounds.timestamp_initiated).all()
        answers = Answers.query.filter_by(team_id=team_id).order_by(Answers.timestamp).all()

        # Create history string containing both questions and answers
        history = []
        for round in rounds:
            history.append(f"P1:{round.player1_item.value if round.player1_item else 'None'}")
            history.append(f"P2:{round.player2_item.value if round.player2_item else 'None'}")
        for answer in answers:
            history.append(f"A:{answer.assigned_item.value}:{answer.response_value}")
        
        history_str = "|".join(history)
        
        # Generate two different hashes
        hash1 = hashlib.sha256(history_str.encode()).hexdigest()[:8]
        hash2 = hashlib.md5(history_str.encode()).hexdigest()[:8]
        
        return hash1, hash2
    except Exception as e:
        print(f"Error computing team hashes: {str(e)}")
        return "ERROR", "ERROR"

def get_serialized_active_teams():
    try:
        teams_list = []
        for name, info in state.active_teams.items():
            players = info['players']
            # Compute hashes for the team
            hash1, hash2 = compute_team_hashes(info['team_id'])
            teams_list.append({
                'team_name': name,
                'team_id': info['team_id'],
                'player1_sid': players[0] if len(players) > 0 else None,
                'player2_sid': players[1] if len(players) > 1 else None,
                'current_round_number': info.get('current_round_number', 0),
                'history_hash1': hash1,
                'history_hash2': hash2
            })
        return teams_list
    except Exception as e:
        print(f"Error in get_serialized_active_teams: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def emit_dashboard_team_update():
    try:
        serialized_teams = get_serialized_active_teams()
        for sid in state.dashboard_clients:
            socketio.emit('team_status_changed_for_dashboard', serialized_teams, room=sid)
    except Exception as e:
        print(f"Error in emit_dashboard_team_update: {str(e)}")
        import traceback
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
        import traceback
        traceback.print_exc()

@socketio.on('dashboard_join')
def on_dashboard_join():
    try:
        from flask import request
        sid = request.sid
        state.dashboard_clients.add(sid)
        print(f"Dashboard client connected: {sid}")
        dashboard_last_activity[sid] = time()
        emit_dashboard_full_update(client_sid=sid)
    except Exception as e:
        print(f"Error in on_dashboard_join: {str(e)}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': f'Error joining dashboard: {str(e)}'})

@socketio.on('start_game')
def on_start_game():
    try:
        from flask import request
        if request.sid in state.dashboard_clients:
            state.game_started = True
            # Notify teams and dashboard that game has started
            for team_name, team_info in state.active_teams.items():
                if len(team_info['players']) == 2:  # Only notify paired teams
                    socketio.emit('game_start', {'game_started': True}, room=team_name)
            
            # Notify dashboard
            for dashboard_sid in state.dashboard_clients:
                socketio.emit('game_started', room=dashboard_sid)
                
            # Notify all clients about game state change
            socketio.emit('game_state_changed', {'game_started': True})
                
            # Start first round for all paired teams
            for team_name, team_info in state.active_teams.items():
                if len(team_info['players']) == 2: # If team is paired
                    start_new_round_for_pair(team_name)
    except Exception as e:
        print(f"Error in on_start_game: {str(e)}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': f'Error starting game: {str(e)}'})

@socketio.on('disconnect')
def on_disconnect():
    try:
        from flask import request
        sid = request.sid
        if sid in state.dashboard_clients:
            state.dashboard_clients.remove(sid)
            if sid in dashboard_last_activity:
                del dashboard_last_activity[sid]
    except Exception as e:
        print(f"Error in on_disconnect: {str(e)}")
        import traceback
        traceback.print_exc()

@socketio.on('restart_game')
def on_restart_game():
    try:
        from flask import request
        if request.sid not in state.dashboard_clients:
            emit('error', {'message': 'Unauthorized: Not a dashboard client'})
            emit('game_reset_complete', room=request.sid)
            return

        # First update game state to prevent new answers during reset
        state.game_started = False
        
        # Even if there are no active teams, clear the database
        try:
            # Clear database entries within a transaction
            db.session.begin_nested()  # Create savepoint
            PairQuestionRounds.query.delete()
            Answers.query.delete()
            db.session.commit()
        except Exception as db_error:
            db.session.rollback()
            print(f"Database error during game reset: {str(db_error)}")
            import traceback
            traceback.print_exc()
            emit('error', {'message': 'Database error during reset'})
            emit('game_reset_complete', room=request.sid)
            return

        # If no active teams, still complete the reset successfully
        if not state.active_teams:
            emit('game_state_changed', {'game_started': False})
            emit_dashboard_full_update()
            emit('game_reset_complete', room=request.sid)
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
            socketio.emit('game_reset', room=team_name)
        
        # Ensure all clients are notified of the state change
        socketio.emit('game_state_changed', {'game_started': False})
        
        # Update dashboard with reset state
        emit_dashboard_full_update()

        # Notify dashboard clients that reset is complete
        for dash_sid in state.dashboard_clients:
            socketio.emit('game_reset_complete', room=dash_sid)
            
    except Exception as e:
        print(f"Error in on_restart_game: {str(e)}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': f'Error restarting game: {str(e)}'})

@app.route('/api/dashboard/data', methods=['GET'])
def get_dashboard_data():
    try:
        all_answers = Answers.query.order_by(Answers.timestamp.asc()).all()
        answers_data = [
            {
                'answer_id': ans.answer_id,
                'team_id': ans.team_id,
                'team_name': Teams.query.get(ans.team_id).team_name if Teams.query.get(ans.team_id) else 'N/A',
                'player_session_id': ans.player_session_id,
                'question_round_id': ans.question_round_id,
                'assigned_item': ans.assigned_item.value,
                'response_value': ans.response_value,
                'timestamp': ans.timestamp.isoformat()
            } for ans in all_answers
        ]
        return jsonify({'answers': answers_data}), 200
    except Exception as e:
        print(f"Error in get_dashboard_data: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
