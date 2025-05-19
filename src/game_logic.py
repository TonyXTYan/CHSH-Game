import random
from datetime import datetime
from src.config import socketio, db
from src.models.quiz_models import ItemEnum, PairQuestionRounds, Answers
from src.state import state

QUESTION_ITEMS = [ItemEnum.A, ItemEnum.B, ItemEnum.X, ItemEnum.Y]
TARGET_COMBO_REPEATS = 3

def calculate_score(player1_item, player2_item, player1_answer, player2_answer):
    """Calculate the score for a round based on the CHSH game rules.
    
    Args:
        player1_item (ItemEnum): The item assigned to player 1 (A or B)
        player2_item (ItemEnum): The item assigned to player 2 (X or Y)
        player1_answer (bool): Player 1's answer (True/False)
        player2_answer (bool): Player 2's answer (True/False)
        
    Returns:
        int: 1 if the answers satisfy the winning condition, 0 otherwise
        
    The winning condition for CHSH game:
    - If player1 has A: players should give same answers
    - If player1 has B: players should give different answers for Y only
    """
    if not all(isinstance(item, ItemEnum) for item in [player1_item, player2_item]):
        raise ValueError("Items must be ItemEnum values")
    if not all(isinstance(answer, bool) for answer in [player1_answer, player2_answer]):
        raise ValueError("Answers must be boolean values")
    if player1_item not in [ItemEnum.A, ItemEnum.B]:
        raise ValueError("Player 1 must have item A or B")
    if player2_item not in [ItemEnum.X, ItemEnum.Y]:
        raise ValueError("Player 2 must have item X or Y")

    # For A, answers should match
    if player1_item == ItemEnum.A:
        return 1 if player1_answer == player2_answer else 0
    
    # For B and X, answers should match
    if player2_item == ItemEnum.X:
        return 1 if player1_answer == player2_answer else 0
    
    # For B and Y, answers should differ
    return 1 if player1_answer != player2_answer else 0

def start_new_round_for_pair(team_name):
    try:
        team_info = state.active_teams.get(team_name)
        if not team_info or len(team_info['players']) != 2:
            return

        team_info['current_round_number'] += 1
        round_number = team_info['current_round_number']
        combo_tracker = team_info.get('combo_tracker', {})
        all_possible_combos = [(i1, i2) for i1 in QUESTION_ITEMS for i2 in QUESTION_ITEMS]
        round_limit = (TARGET_COMBO_REPEATS + 1) * len(all_possible_combos)
        rounds_remaining = round_limit - team_info['current_round_number']

        if rounds_remaining <= len(all_possible_combos):  # Enter deterministic phase
            # Get combos that still need repeats
            needed_combos = [c for c in all_possible_combos 
                           if combo_tracker.get((c[0].value, c[1].value), 0) < TARGET_COMBO_REPEATS]
            
            # Build and shuffle priority queue
            priority_queue = []
            for combo in needed_combos:
                hits_needed = TARGET_COMBO_REPEATS - combo_tracker.get((combo[0].value, combo[1].value), 0)
                priority_queue.extend([combo] * hits_needed)
            random.shuffle(priority_queue)
            
            chosen_combo = priority_queue[0] if priority_queue else random.choice(all_possible_combos)
        else:
            # Original random selection with preference
            random.shuffle(all_possible_combos)
            chosen_combo = next((c for c in all_possible_combos 
                               if combo_tracker.get((c[0].value, c[1].value), 0) < TARGET_COMBO_REPEATS), 
                               random.choice(all_possible_combos))
        
        p1_item, p2_item = chosen_combo
        combo_key = (p1_item.value, p2_item.value)
        combo_tracker[combo_key] = combo_tracker.get(combo_key, 0) + 1
        team_info['combo_tracker'] = combo_tracker

        new_round_db = PairQuestionRounds(team_id=team_info['team_id'], round_number_for_team=round_number, player1_item=p1_item, player2_item=p2_item)
        db.session.add(new_round_db)
        db.session.commit()

        team_info['current_db_round_id'] = new_round_db.round_id
        team_info['answered_current_round'] = {}

        # Send questions to players
        player1, player2 = team_info['players']
        socketio.emit('new_question', {'round_id': new_round_db.round_id, 'round_number': round_number, 'item': p1_item.value}, room=player1)
        socketio.emit('new_question', {'round_id': new_round_db.round_id, 'round_number': round_number, 'item': p2_item.value}, room=player2)
        # print(f"Team {team_name} round {round_number}: P1({player1}) gets {p1_item.value}, P2({player2}) gets {p2_item.value}")
        from src.sockets.dashboard import emit_dashboard_team_update
        emit_dashboard_team_update()
    except Exception as e:
        print(f"Error in start_new_round_for_pair: {str(e)}")
        import traceback
        traceback.print_exc()
