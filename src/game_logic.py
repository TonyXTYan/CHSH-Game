import random
import logging
from datetime import datetime
from src.config import socketio, db
from src.models.quiz_models import ItemEnum, PairQuestionRounds, Answers, Teams

logger = logging.getLogger(__name__)

QUESTION_ITEMS = [ItemEnum.A, ItemEnum.B, ItemEnum.X, ItemEnum.Y]
TARGET_COMBO_REPEATS = 2

def start_new_round_for_pair(team_name):
    try:
        from src.state import state  # Import inside function to avoid circular import
        
        team_info = state.active_teams.get(team_name)
        if not team_info or len(team_info['players']) != 2:
            return

        # Get the database team to determine actual player slots
        db_team = db.session.get(Teams, team_info['team_id'])
        if not db_team:
            logger.error(f"Database team not found for team_id: {team_info['team_id']}")
            return
        
        # Map session IDs to their database player slots
        player1_sid = db_team.player1_session_id
        player2_sid = db_team.player2_session_id
        
        if not player1_sid or not player2_sid:
            logger.error(f"Team {team_name} missing player session IDs in database")
            return
        
        # Verify both players are actually connected
        if player1_sid not in team_info['players'] or player2_sid not in team_info['players']:
            logger.error(f"Team {team_name} player session IDs don't match connected players")
            return

        team_info['current_round_number'] += 1
        round_number = team_info['current_round_number']
        combo_tracker = team_info.get('combo_tracker', {})
        
        # Mode-specific question assignment logic
        if state.game_mode == 'new':
            # New mode: Player 1 gets A,B only; Player 2 gets X,Y only
            player1_items = [ItemEnum.A, ItemEnum.B]
            player2_items = [ItemEnum.X, ItemEnum.Y]
            all_possible_combos = [(i1, i2) for i1 in player1_items for i2 in player2_items]
        else:
            # Classic mode: Original logic with all combinations
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
        
        # Clear caches after database commit
        from src.dashboard import clear_team_caches
        clear_team_caches()

        team_info['current_db_round_id'] = new_round_db.round_id
        team_info['answered_current_round'] = {}

        # Send questions to players using actual database player slots
        # Player 1 (from database) gets p1_item, Player 2 (from database) gets p2_item
        socketio.emit('new_question', {'round_id': new_round_db.round_id, 'round_number': round_number, 'item': p1_item.value}, room=player1_sid)
        socketio.emit('new_question', {'round_id': new_round_db.round_id, 'round_number': round_number, 'item': p2_item.value}, room=player2_sid)
        
        logger.debug(f"Team {team_name} round {round_number}: Player1({player1_sid}) gets {p1_item.value}, Player2({player2_sid}) gets {p2_item.value}")
        
        from src.dashboard import emit_dashboard_team_update
        emit_dashboard_team_update()
    except Exception as e:
        logger.error(f"Error in start_new_round_for_pair: {str(e)}", exc_info=True)
