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
        if sid not in state.participant_to_team:
            emit('error', {'message': 'You are not in a team or session expired.'}); return
        team_name = state.participant_to_team[sid]
        team_info = state.active_teams.get(team_name)
        if not team_info or not team_info.get('participant2_sid'):
            emit('error', {'message': 'Team not valid or partner missing.'}); return

        round_id = data.get('round_id')
        assigned_item_str = data.get('item')
        response_bool = data.get('answer')

        if round_id != team_info.get('current_db_round_id') or assigned_item_str is None or response_bool is None:
            emit('error', {'message': 'Invalid answer submission data.'}); return

        try:
            assigned_item_enum = ItemEnum(assigned_item_str)
        except ValueError:
            emit('error', {'message': 'Invalid item in answer.'}); return

        is_p1 = team_info['creator_sid'] == sid
        if (is_p1 and team_info.get('p1_answered_current_round')) or (not is_p1 and team_info.get('p2_answered_current_round')):
            emit('error', {'message': 'You have already answered this round.'}); return

        new_answer_db = Answers(
            team_id=team_info['team_id'],
            participant_session_id=sid,
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

        if is_p1:
            team_info['p1_answered_current_round'] = True
            round_db_entry.p1_answered_at = datetime.utcnow()
        else:
            team_info['p2_answered_current_round'] = True
            round_db_entry.p2_answered_at = datetime.utcnow()

        db.session.commit()
        emit('answer_confirmed', {'message': 'Answer received.'}, room=sid)

        # Emit to dashboard
        answer_for_dash = {
            'timestamp': new_answer_db.timestamp.isoformat(),
            'team_name': team_name,
            'team_id': team_info['team_id'],
            'participant_session_id': sid,
            'question_round_id': round_id,
            'assigned_item': assigned_item_str,
            'response_value': response_bool
        }
        for dash_sid in state.dashboard_clients:
            socketio.emit('new_answer_for_dashboard', answer_for_dash, room=dash_sid)
        emit_dashboard_full_update()

        if team_info.get('p1_answered_current_round') and team_info.get('p2_answered_current_round'):
            print(f"Both participants in team {team_name} answered round {team_info['current_round_number']}.")
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
                        'creator_sid': db_team.participant1_session_id,
                        'participant2_sid': db_team.participant2_session_id,
                        'team_id': db_team.team_id,
                        'current_round_number': 0,
                        'combo_tracker': {},
                        'p1_answered_current_round': False,
                        'p2_answered_current_round': False
                    }
                    state.active_teams[team_name] = team_info
                    state.team_id_to_name[db_team.team_id] = team_name
                    print(f"Recreated team {team_name} from database")
                else:
                    emit('rejoin_team_failed', {'message': 'Team not found or no longer active'}); return
            else:
                emit('rejoin_team_failed', {'message': 'Team not found or no longer active'}); return
            
        # Check if previous_sid matches creator or participant2 directly
        is_creator = team_info['creator_sid'] == previous_sid
        is_participant2 = team_info.get('participant2_sid') == previous_sid
        
        # If no direct match, check previous session mapping chain
        if not is_creator and not is_participant2:
            # Check if previous_sid is in our mapping chain
            for old_sid, mapped_sid in state.previous_sessions.items():
                if team_info['creator_sid'] == mapped_sid:
                    is_creator = True
                    break
                elif team_info.get('participant2_sid') == mapped_sid:
                    is_participant2 = True
                    break
        
        if not is_creator and not is_participant2:
            emit('rejoin_team_failed', {'message': 'You were not a member of this team'}); return
            
        # Update session mapping
        state.previous_sessions[previous_sid] = current_sid
        
        # Update team info with new sid
        if is_creator:
            team_info['creator_sid'] = current_sid
            # Update in database
            db_team = Teams.query.get(team_info['team_id'])
            if db_team: 
                db_team.participant1_session_id = current_sid
                db.session.commit()
        elif is_participant2:
            team_info['participant2_sid'] = current_sid
            # Update in database
            db_team = Teams.query.get(team_info['team_id'])
            if db_team: 
                db_team.participant2_session_id = current_sid
                db.session.commit()
                
        # Update participant_to_team mapping
        state.participant_to_team[current_sid] = team_name
        if previous_sid in state.participant_to_team:
            del state.participant_to_team[previous_sid]
            
        # Join the room
        join_room(team_name)
        
        # Prepare current round info if exists
        current_round_data = None
        already_answered = False
        if team_info.get('current_db_round_id'):
            round_db = PairQuestionRounds.query.get(team_info['current_db_round_id'])
            if round_db:
                item = round_db.participant1_item.value if is_creator else round_db.participant2_item.value
                current_round_data = {
                    'round_id': team_info['current_db_round_id'],
                    'round_number': team_info['current_round_number'],
                    'item': item
                }
                # Check if already answered
                if is_creator and team_info.get('p1_answered_current_round'):
                    already_answered = True
                elif not is_creator and team_info.get('p2_answered_current_round'):
                    already_answered = True
        
        # Send success response
        status_message = "Team created! Waiting for a partner." if is_creator else "You have joined the team!"
        if team_info.get('participant2_sid') and is_creator:
            status_message = "Your team is full! Waiting for game to start."
            if state.game_started:
                status_message = "Game has started! Get ready for questions."
            
        emit('rejoin_team_success', {
            'team_name': team_name,
            'status_message': status_message,
            'is_creator': is_creator,
            'current_round': current_round_data,
            'already_answered': already_answered,
            'game_started': state.game_started
        })
        
        # Notify other team member if exists
        other_sid = team_info.get('participant2_sid') if is_creator else team_info['creator_sid']
        if other_sid and other_sid != current_sid:
            emit('partner_reconnected', {
                'message': 'Your partner has reconnected!'
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
                        'creator_sid': db_team.participant1_session_id,
                        'participant2_sid': db_team.participant2_session_id,
                        'team_id': db_team.team_id,
                        'current_round_number': 0,
                        'combo_tracker': {},
                        'p1_answered_current_round': False,
                        'p2_answered_current_round': False
                    }
                    state.active_teams[team_name] = team_info
                    state.team_id_to_name[db_team.team_id] = team_name
                    print(f"Recreated team {team_name} from database")
                else:
                    emit('rejoin_team_failed', {'message': 'Team not found or no longer active'}); return
            else:
                emit('rejoin_team_failed', {'message': 'Team not found or no longer active'}); return
            
        # Rest of rejoin logic is identical to verify_team_membership
        is_creator = team_info['creator_sid'] == previous_sid
        is_participant2 = team_info.get('participant2_sid') == previous_sid
        
        if not is_creator and not is_participant2:
            for old_sid, mapped_sid in state.previous_sessions.items():
                if team_info['creator_sid'] == mapped_sid:
                    is_creator = True
                    break
                elif team_info.get('participant2_sid') == mapped_sid:
                    is_participant2 = True
                    break
        
        if not is_creator and not is_participant2:
            emit('rejoin_team_failed', {'message': 'You were not a member of this team'}); return
            
        state.previous_sessions[previous_sid] = current_sid
        
        if is_creator:
            team_info['creator_sid'] = current_sid
            db_team = Teams.query.get(team_info['team_id'])
            if db_team: 
                db_team.participant1_session_id = current_sid
                db.session.commit()
        elif is_participant2:
            team_info['participant2_sid'] = current_sid
            db_team = Teams.query.get(team_info['team_id'])
            if db_team: 
                db_team.participant2_session_id = current_sid
                db.session.commit()
                
        state.participant_to_team[current_sid] = team_name
        if previous_sid in state.participant_to_team:
            del state.participant_to_team[previous_sid]
            
        join_room(team_name)
        
        current_round_data = None
        already_answered = False
        if team_info.get('current_db_round_id'):
            round_db = PairQuestionRounds.query.get(team_info['current_db_round_id'])
            if round_db:
                item = round_db.participant1_item.value if is_creator else round_db.participant2_item.value
                current_round_data = {
                    'round_id': team_info['current_db_round_id'],
                    'round_number': team_info['current_round_number'],
                    'item': item
                }
                if is_creator and team_info.get('p1_answered_current_round'):
                    already_answered = True
                elif not is_creator and team_info.get('p2_answered_current_round'):
                    already_answered = True
        
        status_message = "Team created! Waiting for a partner." if is_creator else "You have joined the team!"
        if team_info.get('participant2_sid') and is_creator:
            status_message = "Your team is full! Waiting for game to start."
            if state.game_started:
                status_message = "Game has started! Get ready for questions."
            
        emit('rejoin_team_success', {
            'team_name': team_name,
            'status_message': status_message,
            'is_creator': is_creator,
            'current_round': current_round_data,
            'already_answered': already_answered,
            'game_started': state.game_started
        })
        
        other_sid = team_info.get('participant2_sid') if is_creator else team_info['creator_sid']
        if other_sid and other_sid != current_sid:
            emit('partner_reconnected', {
                'message': 'Your partner has reconnected!'
            }, room=other_sid)
            
        emit_dashboard_team_update()
        
    except Exception as e:
        print(f"Error in on_rejoin_team: {str(e)}")
        import traceback
        traceback.print_exc()
        emit('rejoin_team_failed', {'message': f'Error rejoining team: {str(e)}'})