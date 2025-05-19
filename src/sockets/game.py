from datetime import datetime
from flask import request
from flask_socketio import emit, join_room, leave_room
from src.config import socketio, db
from src.state import state
from src.models.quiz_models import Teams, PairQuestionRounds, Answers, ItemEnum
from src.sockets.dashboard import emit_dashboard_team_update, emit_dashboard_full_update
from src.game_logic import start_new_round_for_pair
from src.sockets.team_management import _update_team_active_status_and_state

def _get_player_slot_in_team(previous_sid, db_team, team_id=None):
    """Helper to determine a player's slot in a team using various sources."""
    # First check direct DB state
    if db_team.player1_session_id == previous_sid:
        return 0
    if db_team.player2_session_id == previous_sid:
        return 1
        
    # Check recently disconnected players
    disconnected_entry = state.recently_disconnected_sids.get(previous_sid)
    if disconnected_entry and (team_id is None or disconnected_entry['team_id'] == team_id):
        slot = disconnected_entry['original_slot']
        print(f"Found player {previous_sid} in recently_disconnected_sids (slot {slot})")
        del state.recently_disconnected_sids[previous_sid]
        return slot
        
    # Check previous sessions chain
    for old_sid, mapped_sid in state.previous_sessions.items():
        if mapped_sid == previous_sid:
            if db_team.player1_session_id == old_sid:
                return 0
            if db_team.player2_session_id == old_sid:
                return 1
                
    return None

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
        
        emit_dashboard_team_update()

        if len(team_info['answered_current_round']) == 2:
            socketio.emit('round_complete', {
                'team_name': team_name,
                'round_number': team_info['current_round_number']
            }, room=team_name)
            start_new_round_for_pair(team_name)
    except Exception as e:
        print(f"Error in on_submit_answer: {str(e)}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': f'Error submitting answer: {str(e)}'})

@socketio.on('verify_team_membership')
def on_verify_team_membership(data):
    """Handles team membership verification with robust rejoin support."""
    try:
        team_name = data.get('team_name')
        previous_sid = data.get('previous_sid')
        current_sid = request.sid
        team_id = data.get('team_id')
        
        if not team_name or not previous_sid:
            emit('rejoin_team_failed', {'message': 'Missing team name or previous session ID'}); return

        # Find or reconstruct team info
        team_info = state.active_teams.get(team_name)
        db_team = None

        if not team_info and team_id:
            # Try looking up by team_id first
            if team_id in state.team_id_to_name:
                team_name = state.team_id_to_name[team_id]
                team_info = state.active_teams.get(team_name)
            
            if not team_info:  # Still not found, try DB
                db_team = Teams.query.get(team_id)
                if db_team and db_team.is_active:
                    team_name = db_team.team_name
                    team_info = {
                        'players': [],
                        'team_id': db_team.team_id,
                        'current_round_number': 0,
                        'combo_tracker': {},
                        'answered_current_round': {},
                        'status': 'waiting_pair'
                    }
                    print(f"Reconstructing team {team_name} state from database")

        if not team_info:
            emit('rejoin_team_failed', {'message': 'Team not found or no longer active'}); return
            
        if not db_team:
            db_team = Teams.query.get(team_info['team_id'])
            if not db_team:
                emit('rejoin_team_failed', {'message': 'Team database record not found'}); return

        # Find player's slot
        player_idx = _get_player_slot_in_team(previous_sid, db_team, team_info['team_id'])
        if player_idx is None:
            emit('rejoin_team_failed', {'message': 'You were not a member of this team'}); return

        # Check for SID conflicts
        if player_idx == 0 and db_team.player2_session_id == current_sid:
            emit('rejoin_team_failed', {'message': 'Cannot rejoin: SID conflict'}); return
        if player_idx == 1 and db_team.player1_session_id == current_sid:
            emit('rejoin_team_failed', {'message': 'Cannot rejoin: SID conflict'}); return

        # Update session mappings
        state.previous_sessions[previous_sid] = current_sid
        if previous_sid != current_sid and previous_sid in state.player_to_team:
            del state.player_to_team[previous_sid]
        state.player_to_team[current_sid] = team_name

        # Update team state
        if player_idx == 0:
            db_team.player1_session_id = current_sid
        else:
            db_team.player2_session_id = current_sid
            
        db_team.is_active = True
        db.session.commit()

        # Reconstruct team_info players list from DB
        team_info['players'] = []
        if db_team.player1_session_id:
            team_info['players'].append(db_team.player1_session_id)
        if db_team.player2_session_id and db_team.player2_session_id != db_team.player1_session_id:
            team_info['players'].append(db_team.player2_session_id)

        # Update team status
        team_info['status'] = 'active' if len(team_info['players']) == 2 else 'waiting_pair'
        if len(team_info['players']) == 0:  # Should not happen
            print(f"Warning: Team {team_name} has no players after rejoin")
            _update_team_active_status_and_state(team_name, team_info, db_team)
        
        # Join room
        join_room(team_name)
        
        # Prepare current round info
        current_round_data = None
        already_answered = False
        if team_info.get('current_db_round_id'):
            round_db = PairQuestionRounds.query.get(team_info['current_db_round_id'])
            if round_db:
                item = round_db.player1_item.value if player_idx == 0 else round_db.player2_item.value
                current_round_data = {
                    'round_id': team_info['current_db_round_id'],
                    'round_number': team_info['current_round_number'],
                    'item': item
                }
                if team_info['answered_current_round'].get(current_sid):
                    already_answered = True

        # Send success response
        game_status = ""
        if state.game_started:
            game_status = " Game has started!" if not state.game_paused else " Game is paused!"
        else:
            game_status = " Waiting for game to start."
            
        status_message = "Team joined! Waiting for another player." if len(team_info['players']) < 2 else "Team is full!" + game_status
        
        emit('rejoin_team_success', {
            'team_name': team_name,
            'status_message': status_message,
            'player_idx': player_idx,
            'current_round': current_round_data,
            'already_answered': already_answered,
            'game_started': state.game_started
        })
        
        # Notify other team member
        other_sids = [sid for sid in team_info['players'] if sid != current_sid]
        for other_sid in other_sids:
            emit('player_reconnected', {
                'message': 'A team member has reconnected!'
            }, room=other_sid)
            
        emit_dashboard_team_update()
        
    except Exception as e:
        print(f"Error in on_verify_team_membership: {str(e)}")
        import traceback
        traceback.print_exc()
        emit('rejoin_team_failed', {'message': f'Error verifying team membership: {str(e)}'})

@socketio.on('rejoin_team')
def on_rejoin_team(data):
    """Main rejoin handler, using same logic as verify_team_membership."""
    # Simply delegate to verify_team_membership as the logic is identical
    on_verify_team_membership(data)
