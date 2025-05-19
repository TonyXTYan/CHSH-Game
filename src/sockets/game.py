from datetime import datetime
from flask import request
from flask_socketio import emit, join_room, leave_room
from src.config import socketio, db
from src.state import state
from src.models.quiz_models import Teams, PairQuestionRounds, Answers, ItemEnum
from src.sockets.dashboard import emit_dashboard_team_update, emit_dashboard_full_update
from src.game_logic import start_new_round_for_pair

@socketio.on('submit_answer')
def on_submit_answer(data):
    """
    Handle player answer submission.
    
    Args:
        data (dict): Contains round_id, item, and answer
    """
    sid = request.sid
    
    # Validate session and game state
    if not sid:
        emit('error', {'message': 'Invalid session.'}); return
        
    team_name = state.get_player_team(sid)
    if not team_name:
        emit('error', {'message': 'You are not in a team or session expired.'}); return
        
    if state.is_game_paused():
        emit('error', {'message': 'Game is currently paused.'}); return
    
    # Get team info
    team_info = state.get_team_info(team_name)
    if not team_info or len(team_info['players']) != 2:
        emit('error', {'message': 'Team not valid or other player missing.'}); return

    # Validate input data
    try:
        round_id = data.get('round_id')
        assigned_item_str = data.get('item')
        response_bool = data.get('answer')

        if not isinstance(round_id, int):
            emit('error', {'message': 'Invalid round ID format.'}); return
            
        if not isinstance(assigned_item_str, str) or assigned_item_str not in ['A', 'B', 'X', 'Y']:
            emit('error', {'message': 'Invalid item format.'}); return
            
        if not isinstance(response_bool, bool):
            emit('error', {'message': 'Answer must be true or false.'}); return

        if round_id != team_info.get('current_db_round_id'):
            emit('error', {'message': 'Round ID does not match current round.'}); return
    except (TypeError, ValueError) as e:
        emit('error', {'message': f'Invalid data format: {str(e)}'}); return

    # Check if player already answered
    if sid in team_info['answered_current_round']:
        emit('error', {'message': 'You have already answered this round.'}); return

    # Convert item string to enum
    try:
        assigned_item_enum = ItemEnum(assigned_item_str)
    except ValueError:
        emit('error', {'message': 'Invalid item value.'}); return

    # Find player index
    try:
        player_idx = team_info['players'].index(sid)
    except ValueError:
        emit('error', {'message': 'Player not found in team.'}); return

    # Start database transaction
    try:
        db.session.begin()
        
        # Create new answer record
        new_answer_db = Answers(
            team_id=team_info['team_id'],
            player_session_id=sid,
            question_round_id=round_id,
            assigned_item=assigned_item_enum,
            response_value=response_bool,
            timestamp=datetime.utcnow()
        )
        db.session.add(new_answer_db)

        # Get and update round record
        round_db_entry = PairQuestionRounds.query.get(round_id)
        if not round_db_entry:
            emit('error', {'message': 'Round not found in database.'})
            db.session.rollback()
            return

        # Update round with answer timestamp
        if player_idx == 0:
            round_db_entry.p1_answered_at = datetime.utcnow()
        else:
            round_db_entry.p2_answered_at = datetime.utcnow()

        # Mark player as answered in state
        players_answered = state.mark_player_answered(team_name, sid)
        
        # Commit transaction
        db.session.commit()
        
        # Confirm answer to player
        emit('answer_confirmed', {
            'message': f'Round {team_info["current_round_number"]} answer received'
        }, room=sid)

        # Prepare dashboard update
        answer_for_dash = {
            'timestamp': new_answer_db.timestamp.isoformat(),
            'team_name': team_name,
            'team_id': team_info['team_id'],
            'player_session_id': sid,
            'question_round_id': round_id,
            'assigned_item': assigned_item_str,
            'response_value': response_bool
        }
        
        # Send update to dashboard clients
        for dash_sid in state.dashboard_clients:
            socketio.emit('new_answer_for_dashboard', answer_for_dash, room=dash_sid)
        
        # Update dashboard team view
        emit_dashboard_team_update()

        # If both players answered, complete round and start new one
        if players_answered == 2:
            socketio.emit('round_complete', {
                'team_name': team_name,
                'round_number': team_info['current_round_number']
            }, room=team_name)
            
            # Start new round
            success = start_new_round_for_pair(team_name)
            if not success:
                socketio.emit('error', {
                    'message': 'Failed to start new round. Please wait for administrator assistance.'
                }, room=team_name)
                
    except Exception as e:
        # Rollback transaction on error
        try:
            db.session.rollback()
        except:
            pass
            
        print(f"Error in on_submit_answer: {str(e)}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': 'Server error processing your answer. Please try again.'})
