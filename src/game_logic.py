import random
from datetime import datetime
from src.config import socketio, db
from src.models.quiz_models import ItemEnum, PairQuestionRounds, Answers
from src.state import state

QUESTION_ITEMS = [ItemEnum.A, ItemEnum.B, ItemEnum.C, ItemEnum.D]
TARGET_COMBO_REPEATS = 3

def start_new_round_for_pair(team_name):
    try:
        team_info = state.active_teams.get(team_name)
        if not team_info or not team_info.get('participant2_sid'): 
            return

        team_info['current_round_number'] += 1
        round_number = team_info['current_round_number']
        combo_tracker = team_info.get('combo_tracker', {})
        all_possible_combos = [(i1, i2) for i1 in QUESTION_ITEMS for i2 in QUESTION_ITEMS]
        random.shuffle(all_possible_combos)
        chosen_combo = next((c for c in all_possible_combos if combo_tracker.get((c[0].value, c[1].value), 0) < TARGET_COMBO_REPEATS), random.choice(all_possible_combos))
        
        p1_item, p2_item = chosen_combo
        combo_key = (p1_item.value, p2_item.value)
        combo_tracker[combo_key] = combo_tracker.get(combo_key, 0) + 1
        team_info['combo_tracker'] = combo_tracker

        new_round_db = PairQuestionRounds(team_id=team_info['team_id'], round_number_for_team=round_number, participant1_item=p1_item, participant2_item=p2_item)
        db.session.add(new_round_db)
        db.session.commit()

        team_info['current_db_round_id'] = new_round_db.round_id
        team_info['p1_answered_current_round'] = False
        team_info['p2_answered_current_round'] = False

        socketio.emit('new_question', {'round_id': new_round_db.round_id, 'round_number': round_number, 'item': p1_item.value}, room=team_info['creator_sid'])
        socketio.emit('new_question', {'round_id': new_round_db.round_id, 'round_number': round_number, 'item': p2_item.value}, room=team_info.get('participant2_sid'))
        print(f"Team {team_name} round {round_number}: P1 gets {p1_item.value}, P2 gets {p2_item.value}")
        from src.sockets.dashboard import emit_dashboard_team_update
        emit_dashboard_team_update()
    except Exception as e:
        print(f"Error in start_new_round_for_pair: {str(e)}")
        import traceback
        traceback.print_exc()