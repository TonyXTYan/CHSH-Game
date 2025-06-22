from datetime import datetime
from flask import request
from flask_socketio import emit, join_room, leave_room
from src.config import socketio, db
from src.state import state
from src.models.quiz_models import Teams, PairQuestionRounds, Answers, ItemEnum
from src.sockets.dashboard import emit_dashboard_team_update, emit_dashboard_full_update, clear_team_caches
from src.game_logic import start_new_round_for_pair

@socketio.on('submit_answer')
def on_submit_answer(data):
    try:
        sid = request.sid
        if sid not in state.player_to_team:
            emit('error', {'message': 'You are not in a team or session expired.'}); return
            
        if state.game_paused:
            emit('error', {'message': 'Game is currently paused.'}); return
        team_name = state.player_to_team[sid]
        team_info = state.active_teams.get(team_name)
        if not team_info or len(team_info['players']) != 2:
            emit('error', {'message': 'Team not valid or other player missing.'}); return

        round_id = data.get('round_id')
        assigned_item_str = data.get('item')
        response_bool = data.get('answer')

        if round_id != team_info.get('current_db_round_id') or assigned_item_str is None or response_bool is None:
            emit('error', {'message': 'Invalid answer submission data.'}); return

        try:
            assigned_item_enum = ItemEnum(assigned_item_str)
        except ValueError:
            emit('error', {'message': 'Invalid item in answer.'}); return

        player_idx = team_info['players'].index(sid)
        if team_info['answered_current_round'].get(sid):
            emit('error', {'message': 'You have already answered this round.'}); return

        new_answer_db = Answers(
            team_id=team_info['team_id'],
            player_session_id=sid,
            question_round_id=round_id,
            assigned_item=assigned_item_enum,
            response_value=response_bool,
            timestamp=datetime.utcnow()
        )
        db.session.add(new_answer_db)

        round_db_entry = PairQuestionRounds.query.get(round_id)
        if not round_db_entry:
            emit('error', {'message': 'Round not found in DB.'})
            db.session.rollback()
            return

        team_info['answered_current_round'][sid] = True
        if player_idx == 0:
            round_db_entry.p1_answered_at = datetime.utcnow()
        else:
            round_db_entry.p2_answered_at = datetime.utcnow()

        db.session.commit()
        # Clear caches after database commit
        clear_team_caches()
        emit('answer_confirmed', {'message': f'Round {team_info["current_round_number"]} answer received'}, room=sid)

        # Emit to dashboard
        answer_for_dash = {
            'timestamp': new_answer_db.timestamp.isoformat(),
            'team_name': team_name,
            'team_id': team_info['team_id'],
            'player_session_id': sid,
            'question_round_id': round_id,
            'assigned_item': assigned_item_str,
            'response_value': response_bool
        }
        for dash_sid in state.dashboard_clients:
            socketio.emit('new_answer_for_dashboard', answer_for_dash, room=dash_sid)
        
        # Only emit team update, not full dashboard refresh
        emit_dashboard_team_update()

        if len(team_info['answered_current_round']) == 2:
            # print(f"Both players in team {team_name} answered round {team_info['current_round_number']}.")
            socketio.emit('round_complete', {
                'team_name': team_name,
                'round_number': team_info['current_round_number']
            }, room=team_name)
            
            # Only auto-start new round if not in test mode
            # Test mode is indicated by a flag in team_info
            if not team_info.get('test_mode', False):
                start_new_round_for_pair(team_name)
    except Exception as e:
        print(f"Error in on_submit_answer: {str(e)}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': f'Error submitting answer: {str(e)}'})
