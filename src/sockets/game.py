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
    try:
        sid = request.sid
        if sid not in state.player_to_team:
            emit('error', {'message': 'You are not in a team or session expired.'}); return
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
        emit('answer_confirmed', {'message': 'Answer received.'}, room=sid)

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
        emit_dashboard_full_update()

        if len(team_info['answered_current_round']) == 2:
            print(f"Both players in team {team_name} answered round {team_info['current_round_number']}.")
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
    try:
        team_name = data.get('team_name')
        previous_sid = data.get('previous_sid')
        current_sid = request.sid
        team_id = data.get('team_id')  # Optional, for additional verification
        
        if not team_name or not previous_sid:
            emit('rejoin_team_failed', {'message': 'Missing team name or previous session ID'}); return
            
        # Check if team exists and is active
        team_info = state.active_teams.get(team_name)
        
        # If team_name lookup failed but we have team_id, try that
        if not team_info and team_id and team_id in state.team_id_to_name:
            team_name = state.team_id_to_name[team_id]
            team_info = state.active_teams.get(team_name)
        
        if not team_info:
            # Try to find team by looking up the team in the database
            if team_id:
                db_team = Teams.query.get(team_id)
                if db_team and db_team.is_active:
                    # Team exists in DB but not in memory, recreate it
                    team_name = db_team.team_name
                    team_info = {
                        'players': [],
                        'team_id': db_team.team_id,
                        'current_round_number': 0,
                        'combo_tracker': {},
                        'answered_current_round': {}
                    }
                    if db_team.player1_session_id:
                        team_info['players'].append(db_team.player1_session_id)
                    if db_team.player2_session_id:
                        team_info['players'].append(db_team.player2_session_id)
                    state.active_teams[team_name] = team_info
                    state.team_id_to_name[db_team.team_id] = team_name
                    print(f"Recreated team {team_name} from database")
                else:
                    emit('rejoin_team_failed', {'message': 'Team not found or no longer active'}); return
            else:
                emit('rejoin_team_failed', {'message': 'Team not found or no longer active'}); return
            
        # Check team membership in database first
        db_team = Teams.query.get(team_info['team_id'])
        is_db_member = (db_team.player1_session_id == previous_sid or
                       db_team.player2_session_id == previous_sid)

        # Then check in-memory state
        player_idx = None
        if previous_sid in team_info['players']:
            player_idx = team_info['players'].index(previous_sid)
        else:
            # Check previous session mapping chain
            for old_sid, mapped_sid in state.previous_sessions.items():
                if mapped_sid in team_info['players']:
                    player_idx = team_info['players'].index(mapped_sid)
                    break
                # Also check if this old session was in the database
                if (db_team.player1_session_id == old_sid or
                    db_team.player2_session_id == old_sid):
                    is_db_member = True

        # If not found in memory but found in DB, assign to first available slot
        if player_idx is None and is_db_member:
            if len(team_info['players']) == 0:
                player_idx = 0
            elif len(team_info['players']) == 1:
                player_idx = 1
                
        if player_idx is None and not is_db_member:
            emit('rejoin_team_failed', {'message': 'You were not a member of this team'}); return

        # Update session mapping
        state.previous_sessions[previous_sid] = current_sid
        
        # Update team info with new sid
        team_info['players'][player_idx] = current_sid
        
        # Update in database
        db_team = Teams.query.get(team_info['team_id'])
        if db_team:
            if player_idx == 0:
                db_team.player1_session_id = current_sid
            else:
                db_team.player2_session_id = current_sid
            db.session.commit()
                
        # Update player_to_team mapping
        state.player_to_team[current_sid] = team_name
        if previous_sid in state.player_to_team:
            del state.player_to_team[previous_sid]
            
        # Join the room
        join_room(team_name)
        
        # Prepare current round info if exists
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
                # Check if already answered
                if team_info['answered_current_round'].get(current_sid):
                    already_answered = True
        
        # Send success response
        if len(team_info['players']) < 2:
            status_message = "Team joined! Waiting for another player."
        else:
            status_message = "Team is full!" + (" Game has started!" if state.game_started else " Waiting for game to start.")
            
        emit('rejoin_team_success', {
            'team_name': team_name,
            'status_message': status_message,
            'player_idx': player_idx,
            'current_round': current_round_data,
            'already_answered': already_answered,
            'game_started': state.game_started
        })
        
        # Notify other team member if exists
        other_sids = [sid for sid in team_info['players'] if sid != current_sid]
        for other_sid in other_sids:
            emit('player_reconnected', {
                'message': 'A team member has reconnected!'
            }, room=other_sid)
            
        # Update dashboard
        emit_dashboard_team_update()
        
    except Exception as e:
        print(f"Error in on_verify_team_membership: {str(e)}")
        import traceback
        traceback.print_exc()
        emit('rejoin_team_failed', {'message': f'Error verifying team membership: {str(e)}'})

@socketio.on('rejoin_team')
def on_rejoin_team(data):
    try:
        team_name = data.get('team_name')
        previous_sid = data.get('previous_sid')
        current_sid = request.sid
        team_id = data.get('team_id')  # Optional, for additional verification
        
        if not team_name or not previous_sid:
            emit('rejoin_team_failed', {'message': 'Missing team name or previous session ID'}); return
            
        # Check if team exists and is active
        team_info = state.active_teams.get(team_name)
        
        # If team_name lookup failed but we have team_id, try that
        if not team_info and team_id and team_id in state.team_id_to_name:
            team_name = state.team_id_to_name[team_id]
            team_info = state.active_teams.get(team_name)
        
        if not team_info:
            # Try to find team by looking up the team in the database
            if team_id:
                db_team = Teams.query.get(team_id)
                if db_team and db_team.is_active:
                    # Team exists in DB but not in memory, recreate it
                    team_name = db_team.team_name
                    team_info = {
                        'players': [],
                        'team_id': db_team.team_id,
                        'current_round_number': 0,
                        'combo_tracker': {},
                        'answered_current_round': {}
                    }
                    if db_team.player1_session_id:
                        team_info['players'].append(db_team.player1_session_id)
                    if db_team.player2_session_id:
                        team_info['players'].append(db_team.player2_session_id)
                    state.active_teams[team_name] = team_info
                    state.team_id_to_name[db_team.team_id] = team_name
                    print(f"Recreated team {team_name} from database")
                else:
                    emit('rejoin_team_failed', {'message': 'Team not found or no longer active'}); return
            else:
                emit('rejoin_team_failed', {'message': 'Team not found or no longer active'}); return
            
        # Rest of rejoin logic is identical to verify_team_membership
        # Check team membership in database first
        db_team = Teams.query.get(team_info['team_id'])
        is_db_member = (db_team.player1_session_id == previous_sid or
                       db_team.player2_session_id == previous_sid)

        # Then check in-memory state
        player_idx = None
        if previous_sid in team_info['players']:
            player_idx = team_info['players'].index(previous_sid)
        else:
            # Check previous session mapping chain
            for old_sid, mapped_sid in state.previous_sessions.items():
                if mapped_sid in team_info['players']:
                    player_idx = team_info['players'].index(mapped_sid)
                    break
                # Also check if this old session was in the database
                if (db_team.player1_session_id == old_sid or
                    db_team.player2_session_id == old_sid):
                    is_db_member = True

        # If not found in memory but found in DB, assign to first available slot
        if player_idx is None and is_db_member:
            if len(team_info['players']) == 0:
                player_idx = 0
            elif len(team_info['players']) == 1:
                player_idx = 1

        if player_idx is None and not is_db_member:
            emit('rejoin_team_failed', {'message': 'You were not a member of this team'}); return
            
        state.previous_sessions[previous_sid] = current_sid
        
        # Update session mapping
        state.previous_sessions[previous_sid] = current_sid
        
        # Update team info with new sid
        if player_idx is not None:
            if player_idx >= len(team_info['players']):
                team_info['players'].append(current_sid)
            else:
                team_info['players'][player_idx] = current_sid
        else:
            # New slot for db member
            team_info['players'].append(current_sid)
            player_idx = len(team_info['players']) - 1

        # Update database
        if db_team:
            if player_idx == 0:
                db_team.player1_session_id = current_sid
            else:
                db_team.player2_session_id = current_sid
            db.session.commit()
                
        state.player_to_team[current_sid] = team_name
        if previous_sid in state.player_to_team:
            del state.player_to_team[previous_sid]
            
        join_room(team_name)
        
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
        
        if len(team_info['players']) < 2:
            status_message = "Team joined! Waiting for another player."
        else:
            status_message = "Team is full!" + (" Game has started!" if state.game_started else " Waiting for game to start.")
            
        emit('rejoin_team_success', {
            'team_name': team_name,
            'status_message': status_message,
            'player_idx': player_idx,
            'current_round': current_round_data,
            'already_answered': already_answered,
            'game_started': state.game_started
        })
        
        other_sids = [sid for sid in team_info['players'] if sid != current_sid]
        for other_sid in other_sids:
            emit('player_reconnected', {
                'message': 'A team member has reconnected!'
            }, room=other_sid)
            
        emit_dashboard_team_update()
        
    except Exception as e:
        print(f"Error in on_rejoin_team: {str(e)}")
        import traceback
        traceback.print_exc()
        emit('rejoin_team_failed', {'message': f'Error rejoining team: {str(e)}'})
