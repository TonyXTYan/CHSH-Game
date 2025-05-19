import random
from datetime import datetime
from src.config import socketio, db
from src.models.quiz_models import ItemEnum, PairQuestionRounds, Answers
from src.state import state

QUESTION_ITEMS = [ItemEnum.A, ItemEnum.B, ItemEnum.X, ItemEnum.Y]
TARGET_COMBO_REPEATS = 3

def start_new_round_for_pair(team_name):
    """
    Start a new round for a team pair, selecting items and updating database.
    
    Args:
        team_name (str): The name of the team to start a new round for
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        # Get team info using thread-safe method
        team_info = state.get_team_info(team_name)
        if not team_info or len(team_info['players']) != 2:
            print(f"Cannot start round: Team {team_name} not found or doesn't have exactly 2 players")
            return False

        # Start database transaction
        db.session.begin()
        
        # Update round number
        team_info['current_round_number'] += 1
        round_number = team_info['current_round_number']
        combo_tracker = team_info.get('combo_tracker', {})
        all_possible_combos = [(i1, i2) for i1 in QUESTION_ITEMS for i2 in QUESTION_ITEMS]
        round_limit = (TARGET_COMBO_REPEATS + 1) * len(all_possible_combos)
        rounds_remaining = round_limit - team_info['current_round_number']

        # Select combo based on phase (deterministic or random)
        if rounds_remaining <= len(all_possible_combos):  # Enter deterministic phase
            # Get combos that still need repeats
            needed_combos = [c for c in all_possible_combos 
                           if combo_tracker.get((c[0].value, c[1].value), 0) < TARGET_COMBO_REPEATS]
            
            # Build and shuffle priority queue
            priority_queue = []
            for combo in needed_combos:
                hits_needed = TARGET_COMBO_REPEATS - combo_tracker.get((combo[0].value, combo[1].value), 0)
                priority_queue.extend([combo] * hits_needed)
                
            # Ensure priority_queue is not empty before accessing
            if priority_queue:
                random.shuffle(priority_queue)
                chosen_combo = priority_queue[0]
            else:
                chosen_combo = random.choice(all_possible_combos)
        else:
            # Original random selection with preference
            random.shuffle(all_possible_combos)
            chosen_combo = next((c for c in all_possible_combos 
                               if combo_tracker.get((c[0].value, c[1].value), 0) < TARGET_COMBO_REPEATS), 
                               random.choice(all_possible_combos))
        
        # Update combo tracker
        p1_item, p2_item = chosen_combo
        combo_key = (p1_item.value, p2_item.value)
        combo_tracker[combo_key] = combo_tracker.get(combo_key, 0) + 1
        team_info['combo_tracker'] = combo_tracker

        # Create new round in database
        try:
            new_round_db = PairQuestionRounds(
                team_id=team_info['team_id'], 
                round_number_for_team=round_number, 
                player1_item=p1_item, 
                player2_item=p2_item,
                timestamp_initiated=datetime.utcnow()
            )
            db.session.add(new_round_db)
            db.session.flush()  # Get the ID without committing
            
            # Update team state with new round ID
            state.update_team_round(team_name, new_round_db.round_id)
            
            # Commit transaction
            db.session.commit()
        except Exception as db_error:
            db.session.rollback()
            print(f"Database error in start_new_round_for_pair: {str(db_error)}")
            import traceback
            traceback.print_exc()
            return False

        # Send questions to players
        try:
            player1, player2 = team_info['players']
            socketio.emit('new_question', {
                'round_id': new_round_db.round_id, 
                'round_number': round_number, 
                'item': p1_item.value
            }, room=player1)
            
            socketio.emit('new_question', {
                'round_id': new_round_db.round_id, 
                'round_number': round_number, 
                'item': p2_item.value
            }, room=player2)
            
            # Update dashboard
            from src.sockets.dashboard import emit_dashboard_team_update
            emit_dashboard_team_update()
            
            return True
        except Exception as socket_error:
            print(f"Socket error in start_new_round_for_pair: {str(socket_error)}")
            import traceback
            traceback.print_exc()
            return False
            
    except Exception as e:
        print(f"Error in start_new_round_for_pair: {str(e)}")
        import traceback
        traceback.print_exc()
        
        # Ensure transaction is rolled back on error
        try:
            db.session.rollback()
        except:
            pass
            
        return False
