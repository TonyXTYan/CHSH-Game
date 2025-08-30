from datetime import datetime
from flask import request
from flask_socketio import emit, join_room, leave_room
from src.config import socketio, db
from src.state import state
from src.models.quiz_models import Teams, PairQuestionRounds, Answers, ItemEnum
from src.game_logic import start_new_round_for_pair, recommend_answers
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
        if not team_info:
            emit('error', {'message': 'Team not valid.'})  # type: ignore
            return
        
        cheat_type = team_info.get('cheat_type', 'none')
        
        # Relaxed validation for single-player tony/kevin teams
        if cheat_type in ['tony', 'kevin']:
            # Allow single-player submission for tony/kevin teams
            if len(team_info['players']) < 1:
                emit('error', {'message': 'No players in team.'})  # type: ignore
                return
            # Allow submission when waiting_pair or active
            if team_info.get('status') not in ['waiting_pair', 'active']:
                emit('error', {'message': 'Team is not in a valid state for submission.'})  # type: ignore
                return
        else:
            # Standard validation for non-cheat teams
            if len(team_info['players']) != 2:
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

        # Handle cheat functionality after answer is confirmed
        cheat_type = team_info.get('cheat_type', 'none')
        if cheat_type in ['com', 'hint']:
            # Emit partner choice to teammate
            teammate_sid = None
            for player_sid in team_info['players']:
                if player_sid != sid:
                    teammate_sid = player_sid
                    break
            
            if teammate_sid:
                partner_choice_data = {
                    'partnerChoice': response_bool,
                    'at': new_answer_db.timestamp.isoformat()
                }
                socketio.emit('cheat:partner_choice', partner_choice_data, room=teammate_sid)  # type: ignore
                logger.debug(f"Emitted partner choice to {teammate_sid}: {response_bool}")
                
                # For cheat-hint, emit updated hint after first answer (but not in AQM Joe mode)
                if cheat_type == 'hint' and state.game_mode != 'aqmjoe':
                    # Get the current round parity (cached during round start)
                    parity = team_info.get('current_round_parity')
                    if parity:
                        # Import here to avoid circular import
                        from src.game_logic import recommend_answers as rec_answers
                        
                        # Determine which player submitted and compute new recommendation
                        round_db_entry = PairQuestionRounds.query.get(round_id)
                        if round_db_entry:
                            db_team = Teams.query.get(team_info['team_id'])
                            if db_team:
                                # Determine if submitter is player1 or player2
                                is_submitter_p1 = (sid == db_team.player1_session_id)
                                is_teammate_p1 = not is_submitter_p1
                                
                                # Get recommended answer for teammate given submitter's answer
                                if is_submitter_p1:
                                    _, teammate_recommendation = rec_answers(parity, response_bool, None)
                                else:
                                    teammate_recommendation, _ = rec_answers(parity, None, response_bool)
                                
                                # Emit updated hint to teammate
                                updated_hint_data = {
                                    'recommended': teammate_recommendation,
                                    'parity': parity,
                                    'reason': f"Updated hint: partner answered {response_bool}, optimal strategy requires {parity} answers",
                                    'at': datetime.utcnow().isoformat()
                                }
                                socketio.emit('cheat:hint', updated_hint_data, room=teammate_sid)  # type: ignore
                                logger.debug(f"Emitted updated hint to {teammate_sid}: {teammate_recommendation}")

        # Handle auto-fill for single-player tony/kevin teams
        if cheat_type in ['tony', 'kevin'] and len(team_info['players']) == 1:
            # Use database transaction to prevent race conditions
            try:
                # Begin transaction for atomic auto-fill operation
                db.session.begin()
                
                # Get round details for parity calculation (single query)
                round_db_entry = PairQuestionRounds.query.get(round_id)
                if not round_db_entry:
                    logger.error(f"Round {round_id} not found for auto-fill")
                    db.session.rollback()
                    return
                
                # Get database team to determine player slots (single query)
                db_team = Teams.query.get(team_info['team_id'])
                if not db_team:
                    logger.error(f"Team {team_info['team_id']} not found for auto-fill")
                    db.session.rollback()
                    return
                
                # Check for existing partner answer atomically to prevent double-insert
                existing_partner_answer = Answers.query.filter_by(
                    question_round_id=round_id,
                    team_id=team_info['team_id']
                ).filter(Answers.player_session_id != sid).with_for_update().first()
                
                if existing_partner_answer:
                    logger.warning(f"Partner answer already exists for round {round_id}, skipping auto-fill")
                    db.session.rollback()
                    return
                
                # Import parity helpers
                from src.game_logic import get_required_parity, recommend_answers as rec_answers
                
                # Calculate required parity
                parity = get_required_parity(round_db_entry.player1_item, round_db_entry.player2_item)
                
                # Determine if submitter is player1 or player2
                is_submitter_p1 = (sid == db_team.player1_session_id)
                
                # Calculate partner answer based on cheat type
                if is_submitter_p1:
                    # Submitter is P1, auto-fill P2
                    if cheat_type == 'tony':
                        # Tony wins: get answer that makes team win
                        _, partner_answer = rec_answers(parity, response_bool, None)
                    else:  # kevin
                        # Kevin loses: compute losing strategy directly based on parity
                        if parity == "same":
                            # For same parity, losing means answering differently
                            partner_answer = not response_bool
                        else:  # different parity
                            # For different parity, losing means answering the same
                            partner_answer = response_bool
                    
                    partner_sid_slot = 2
                    partner_item = round_db_entry.player2_item
                    # Use team_id and round_id for unique synthetic ID
                    partner_sid = f"auto_{cheat_type}_{team_info['team_id']}_{round_id}_p2"
                else:
                    # Submitter is P2, auto-fill P1
                    if cheat_type == 'tony':
                        # Tony wins: get answer that makes team win
                        partner_answer, _ = rec_answers(parity, None, response_bool)
                    else:  # kevin
                        # Kevin loses: compute losing strategy directly based on parity
                        if parity == "same":
                            # For same parity, losing means answering differently
                            partner_answer = not response_bool
                        else:  # different parity
                            # For different parity, losing means answering the same
                            partner_answer = response_bool
                    
                    partner_sid_slot = 1
                    partner_item = round_db_entry.player1_item
                    # Use team_id and round_id for unique synthetic ID
                    partner_sid = f"auto_{cheat_type}_{team_info['team_id']}_{round_id}_p1"
                
                # Create auto-filled answer
                partner_answer_db = Answers(
                    team_id=team_info['team_id'],
                    player_session_id=partner_sid,
                    question_round_id=round_id,
                    assigned_item=partner_item,
                    response_value=partner_answer,
                    timestamp=datetime.utcnow()
                )
                
                # Insert the auto-filled answer
                db.session.add(partner_answer_db)
                
                # Update round timestamps
                if partner_sid_slot == 1:
                    round_db_entry.p1_answered_at = datetime.utcnow()
                else:
                    round_db_entry.p2_answered_at = datetime.utcnow()
                
                # Mark partner as answered in team state
                team_info['answered_current_round'][partner_sid] = True
                
                # Commit the transaction
                db.session.commit()
                
                logger.info(f"Auto-filled partner answer for {cheat_type} team {team_name}: {partner_answer} (parity: {parity}, submitter_answer: {response_bool})")
                
            except Exception as e:
                logger.error(f"Error in auto-fill for {cheat_type} team {team_name}: {str(e)}")
                db.session.rollback()
                emit('error', {'message': 'Error processing auto-fill'}, to=sid)  # type: ignore
                return

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
            # Use cached round_db_entry and db_team from auto-fill if available
            if 'round_db_entry' not in locals():
                round_db_entry = PairQuestionRounds.query.get(round_id)
            if 'db_team' not in locals():
                db_team = Teams.query.get(team_info['team_id'])
                
            if round_db_entry and db_team:
                # Get both players' answers for this round
                round_answers = Answers.query.filter_by(question_round_id=round_id).all()
                
                # Verify we have exactly 2 answers
                if len(round_answers) == 2:
                    # Organize the answer data by player position using session IDs
                    p1_answer = None
                    p2_answer = None
                    p1_item = round_db_entry.player1_item.value if round_db_entry.player1_item else None
                    p2_item = round_db_entry.player2_item.value if round_db_entry.player2_item else None
                    
                    for answer in round_answers:
                        # Match answers by session ID with improved synthetic ID handling
                        # For real players, match exact session ID
                        # For auto-filled answers, match by synthetic ID pattern
                        if answer.player_session_id == db_team.player1_session_id:
                            p1_answer = answer.response_value
                        elif answer.player_session_id == db_team.player2_session_id:
                            p2_answer = answer.response_value
                        elif answer.player_session_id.startswith("auto_") and f"_{round_id}_p1" in answer.player_session_id:
                            p1_answer = answer.response_value
                        elif answer.player_session_id.startswith("auto_") and f"_{round_id}_p2" in answer.player_session_id:
                            p2_answer = answer.response_value
                        else:
                            logger.warning(f"Unmatched answer session ID: {answer.player_session_id} for team {team_name}")
                    
                    # Ensure we have both answers before proceeding
                    if p1_answer is None or p2_answer is None:
                        logger.error(f"Missing answers for round completion: p1={p1_answer}, p2={p2_answer}")
                        # Emit basic round complete without success calculation
                        socketio.emit('round_complete', {
                            'team_name': team_name,
                            'round_number': team_info['current_round_number'],
                            'success': False,
                            'error': 'Missing player answers'
                        }, to=team_name)  # type: ignore
                        start_new_round_for_pair(team_name)
                        return
                    
                    # Calculate success for this round
                    success = False
                    if p1_answer is not None and p2_answer is not None:
                        # Apply CHSH success rules
                        is_by_combination = (p1_item == 'B' and p2_item == 'Y') or (p1_item == 'Y' and p2_item == 'B')
                        players_answered_differently = p1_answer != p2_answer
                        
                        if state.game_mode == 'aqmjoe':
                            # Import AQM Joe success logic if needed
                            try:
                                from src.sockets.dashboard import _is_aqmjoe_success
                                success = _is_aqmjoe_success(p1_item, p2_item, p1_answer, p2_answer)
                            except ImportError:
                                # Fallback to standard logic
                                success = players_answered_differently if is_by_combination else not players_answered_differently
                        else:
                            if is_by_combination:
                                # B,Y combination: players should answer differently
                                success = players_answered_differently
                            else:
                                # All other combinations: players should answer the same
                                success = not players_answered_differently
                    
                    # Emit enhanced round_complete event with detailed results
                    # Note: Client safely handles None values in answers via generateLastRoundMessage()
                    socketio.emit('round_complete', {
                        'team_name': team_name,
                        'round_number': team_info['current_round_number'],
                        'success': success,
                        'last_round_details': {
                            'p1_item': p1_item,
                            'p2_item': p2_item,
                            'p1_answer': p1_answer,  # May be None if session ID mismatch
                            'p2_answer': p2_answer   # May be None if session ID mismatch
                        }
                    }, to=team_name)  # type: ignore
                else:
                    # Insufficient answers for round completion
                    logger.error(f"Round {round_id} has {len(round_answers)} answers, expected 2")
                    socketio.emit('round_complete', {
                        'team_name': team_name,
                        'round_number': team_info['current_round_number'],
                        'success': False,
                        'error': 'Insufficient answers for round completion'
                    }, to=team_name)  # type: ignore
            else:
                # Missing round or team data
                logger.error(f"Missing data for round completion: round_entry={round_db_entry is not None}, team={db_team is not None}")
                socketio.emit('round_complete', {
                    'team_name': team_name,
                    'round_number': team_info['current_round_number'],
                    'success': False,
                    'error': 'Missing round or team data'
                }, to=team_name)  # type: ignore
            start_new_round_for_pair(team_name)
    except Exception as e:
        logger.error(f"Error in on_submit_answer: {str(e)}", exc_info=True)
        emit('error', {'message': 'An error occurred while submitting your answer'})  # type: ignore
