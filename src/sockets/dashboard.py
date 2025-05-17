from flask import jsonify
from src.config import app, socketio
from src.state import state
from src.models.quiz_models import Teams, Answers
from flask_socketio import emit
from src.game_logic import start_new_round_for_pair

def get_serialized_active_teams():
    try:
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
                if team_info.get('participant2_sid'):  # Only notify full teams
                    socketio.emit('game_start', {'game_started': True}, room=team_name)
            
            # Notify dashboard
            for dashboard_sid in state.dashboard_clients:
                socketio.emit('game_started', room=dashboard_sid)
                
            # Notify all clients about game state change
            socketio.emit('game_state_changed', {'game_started': True})
                
            # Start first round for all full teams
            for team_name, team_info in state.active_teams.items():
                if team_info.get('participant2_sid'): # If team is full
                    start_new_round_for_pair(team_name)
    except Exception as e:
        print(f"Error in on_start_game: {str(e)}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': f'Error starting game: {str(e)}'})

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
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500