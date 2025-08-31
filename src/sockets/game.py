from datetime import datetime
from flask import request
from flask_socketio import emit, join_room, leave_room
from src.config import socketio, db
from src.state import state
from src.models.quiz_models import Teams, PairQuestionRounds, Answers, ItemEnum
from src.game_logic import start_new_round_for_pair
import logging
from typing import Dict, Any, Optional

# Configure logging
logger = logging.getLogger(__name__)

def _import_dashboard_functions():
    """Import dashboard functions to avoid circular import"""
    from src.sockets.dashboard import emit_dashboard_team_update, emit_dashboard_full_update, clear_team_caches, handle_dashboard_disconnect, invalidate_team_caches
    return emit_dashboard_team_update, emit_dashboard_full_update, clear_team_caches, handle_dashboard_disconnect, invalidate_team_caches

@socketio.on('submit_answer')
def on_submit_answer(data: Dict[str, Any]) -> None:
    try:
        sid = request.sid  # type: ignore
        if sid not in state.player_to_team:
            emit('error', {'message': 'You are not in a team or session expired.'})  # type: ignore
            return
            
        if state.game_paused:
            emit('error', {'message': 'Game is currently paused.'})  # type: ignore
            return
        team_name = state.player_to_team[sid]
        team_info = state.active_teams.get(team_name)
        if not team_info or len(team_info['players']) != 2:
            emit('error', {'message': 'Team not valid or other player missing.'})  # type: ignore
            return
        
        # Check if team is in proper active state (both players connected)
        if team_info.get('status') != 'active':
            emit('error', {'message': 'Team is not active. Waiting for all players to connect.'})  # type: ignore
            return

        round_id = data.get('round_id')
        assigned_item_str = data.get('item')
        response_bool = data.get('answer')

        if round_id != team_info.get('current_db_round_id') or assigned_item_str is None or response_bool is None:
            emit('error', {'message': 'Invalid answer submission data.'})  # type: ignore
            return

        try:
            assigned_item_enum = ItemEnum(assigned_item_str)
        except ValueError:
            emit('error', {'message': 'Invalid item in answer.'})  # type: ignore
            return

        player_idx = team_info['players'].index(sid)
        if team_info['answered_current_round'].get(sid):
            emit('error', {'message': 'You have already answered this round.'})  # type: ignore
            return

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
            emit('error', {'message': 'Round not found in DB.'})  # type: ignore
            db.session.rollback()
            return

        team_info['answered_current_round'][sid] = True
        if player_idx == 0:
            round_db_entry.p1_answered_at = datetime.utcnow()
        else:
            round_db_entry.p2_answered_at = datetime.utcnow()

        db.session.commit()
        # Selectively invalidate caches for the affected team only
        _, _, _, _, invalidate_team_caches = _import_dashboard_functions()
        invalidate_team_caches(team_name)
        emit('answer_confirmed', {'message': f'Round {team_info["current_round_number"]} answer received'}, to=sid)  # type: ignore
        
        # Handle cheat-com and cheat-hint: emit partner's choice
        cheat_type = team_info.get('cheat_type', 'none')
        if cheat_type in ('com', 'hint'):
            # Find the partner's SID
            partner_sid = None
            for player_sid in team_info['players']:
                if player_sid != sid:
                    partner_sid = player_sid
                    break
            
            if partner_sid:
                # Emit the partner's choice to the teammate
                socketio.emit('cheat:partner_choice', {
                    'partnerChoice': response_bool,
                    'at': datetime.utcnow().isoformat()
                }, to=partner_sid)  # type: ignore
                logger.info(f"Emitted partner choice for {cheat_type} team {team_name}: {response_bool} to {partner_sid}")
        
        # Handle cheat-hint: emit updated hint after first answer
        if cheat_type == 'hint' and len(team_info['answered_current_round']) == 1:
            # Don't emit hints in AQM Joe mode
            from src.state import state
            if state.game_mode != 'aqmjoe':
                # Get the current round info
                round_db = PairQuestionRounds.query.get(round_id)
                if round_db and partner_sid:
                    # Import helper functions
                    from src.game_logic import get_required_parity, get_parity_reason, recommend_answers
                    
                    # Calculate parity
                    parity = get_required_parity(round_db.player1_item, round_db.player2_item)
                    reason = get_parity_reason(round_db.player1_item, round_db.player2_item)
                    
                    # Determine which player answered (p1 or p2) based on database slots
                    db_team = Teams.query.get(team_info['team_id'])
                    if db_team:
                        if sid == db_team.player1_session_id:
                            # Player 1 answered, calculate recommendation for player 2
                            _, p2_rec = recommend_answers(parity, response_bool, None)
                            socketio.emit('cheat:hint', {
                                'recommended': p2_rec,
                                'parity': parity,
                                'reason': reason,
                                'at': datetime.utcnow().isoformat()
                            }, to=partner_sid)  # type: ignore
                            logger.info(f"Emitted updated hint for team {team_name} to player 2: {p2_rec}")
                        elif sid == db_team.player2_session_id:
                            # Player 2 answered, calculate recommendation for player 1
                            p1_rec, _ = recommend_answers(parity, None, response_bool)
                            socketio.emit('cheat:hint', {
                                'recommended': p1_rec,
                                'parity': parity,
                                'reason': reason,
                                'at': datetime.utcnow().isoformat()
                            }, to=partner_sid)  # type: ignore
                            logger.info(f"Emitted updated hint for team {team_name} to player 1: {p1_rec}")

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
            socketio.emit('new_answer_for_dashboard', answer_for_dash, to=dash_sid)  # type: ignore
        
        # Only emit team update, not full dashboard refresh
        emit_dashboard_team_update, _, _, _, _ = _import_dashboard_functions()
        emit_dashboard_team_update()

        if len(team_info['answered_current_round']) == 2:
            # Get the completed round details from database
            round_db_entry = PairQuestionRounds.query.get(round_id)
            if round_db_entry:
                # Get team info to map session IDs to player positions
                db_team = Teams.query.get(team_info['team_id'])
                if db_team and db_team.player1_session_id and db_team.player2_session_id:
                    # Get both players' answers for this round
                    round_answers = Answers.query.filter_by(question_round_id=round_id).all()
                    
                    # Organize the answer data by player position using session IDs
                    p1_answer = None
                    p2_answer = None
                    p1_item = round_db_entry.player1_item.value if round_db_entry.player1_item else None
                    p2_item = round_db_entry.player2_item.value if round_db_entry.player2_item else None
                    
                    for answer in round_answers:
                        # CRITICAL: Match answers by session ID, not item value, to handle duplicate items
                        # (e.g., when both players receive the same item like "A" or "X")
                        if answer.player_session_id == db_team.player1_session_id:
                            p1_answer = answer.response_value
                        elif answer.player_session_id == db_team.player2_session_id:
                            p2_answer = answer.response_value
                    
                    # Emit enhanced round_complete event with detailed results
                    # Note: Client safely handles None values in answers via generateLastRoundMessage()
                    socketio.emit('round_complete', {
                        'team_name': team_name,
                        'round_number': team_info['current_round_number'],
                        'last_round_details': {
                            'p1_item': p1_item,
                            'p2_item': p2_item,
                            'p1_answer': p1_answer,  # May be None if session ID mismatch
                            'p2_answer': p2_answer   # May be None if session ID mismatch
                        }
                    }, to=team_name)  # type: ignore
                else:
                    # Fallback if team data is incomplete
                    socketio.emit('round_complete', {
                        'team_name': team_name,
                        'round_number': team_info['current_round_number']
                    }, to=team_name)  # type: ignore
            else:
                # Fallback to basic round_complete event
                socketio.emit('round_complete', {
                    'team_name': team_name,
                    'round_number': team_info['current_round_number']
                }, to=team_name)  # type: ignore
            start_new_round_for_pair(team_name)
    except Exception as e:
        logger.error(f"Error in on_submit_answer: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while submitting your answer'})  # type: ignore
