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
            # print(f"Both players in team {team_name} answered round {team_info['current_round_number']}.")
            
            # Get the completed round data for result evaluation
            completed_round_data = None
            try:
                round_db_entry = PairQuestionRounds.query.get(round_id)
                if round_db_entry:
                    # Get both player answers for this round
                    round_answers = Answers.query.filter_by(question_round_id=round_id).all()
                    
                    if len(round_answers) == 2:
                        # Determine which player is which based on database slots
                        team_db = Teams.query.get(team_info['team_id'])
                        if team_db:
                            p1_item = round_db_entry.player1_item.value if round_db_entry.player1_item else None
                            p2_item = round_db_entry.player2_item.value if round_db_entry.player2_item else None
                            
                            # Map answers to correct players
                            p1_answer = None
                            p2_answer = None
                            
                            for answer in round_answers:
                                if answer.player_session_id == team_db.player1_session_id:
                                    p1_answer = answer.response_value
                                elif answer.player_session_id == team_db.player2_session_id:
                                    p2_answer = answer.response_value
                            
                            if p1_item and p2_item and p1_answer is not None and p2_answer is not None:
                                # Evaluate success using the same logic as compute_success_metrics
                                is_by_combination = (p1_item == 'B' and p2_item == 'Y') or (p1_item == 'Y' and p2_item == 'B')
                                players_answered_differently = p1_answer != p2_answer
                                
                                if is_by_combination:
                                    # B,Y combination: players should answer differently
                                    is_successful = players_answered_differently
                                else:
                                    # All other combinations: players should answer the same
                                    is_successful = not players_answered_differently
                                
                                completed_round_data = {
                                    'p1_item': p1_item,
                                    'p2_item': p2_item,
                                    'p1_answer': p1_answer,
                                    'p2_answer': p2_answer,
                                    'is_successful': is_successful
                                }
            except Exception as e:
                logger.error(f"Error getting completed round data: {str(e)}")
                completed_round_data = None
            
            # Emit round complete with optional previous round data
            round_complete_data = {
                'team_name': team_name,
                'round_number': team_info['current_round_number']
            }
            if completed_round_data:
                round_complete_data['previous_round'] = completed_round_data
                
            socketio.emit('round_complete', round_complete_data, to=team_name)  # type: ignore
            start_new_round_for_pair(team_name)
    except Exception as e:
        logger.error(f"Error in on_submit_answer: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while submitting your answer'})  # type: ignore
