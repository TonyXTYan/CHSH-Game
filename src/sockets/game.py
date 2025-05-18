from datetime import datetime
from flask import request
from flask_socketio import emit, join_room, leave_room
from src.config import socketio, db
from src.state import state
from src.models.quiz_models import Teams, PairQuestionRounds, Answers, ItemEnum
from src.sockets.dashboard import emit_dashboard_team_update, emit_dashboard_full_update
from src.game_logic import start_new_round_for_pair

def validate_team_sessions(team_name):
    """
    Validates that a team doesn't have the same SID in both player positions.
    Returns True if validation passes, False if there were errors.
    """
    try:
        team_info = state.active_teams.get(team_name)
        if not team_info:
            print(f"Team {team_name} not found in memory - cannot validate")
            return False
            
        db_team = Teams.query.get(team_info['team_id'])
        if not db_team:
            print(f"Team ID {team_info['team_id']} not found in database - cannot validate")
            return False
        
        # Make sure we have a players array
        if 'players' not in team_info:
            print(f"Team {team_name} has no players array, initializing it")
            team_info['players'] = []
            
        # Clean up None values in memory
        players = [p for p in team_info['players'] if p is not None]
        team_info['players'] = players
            
        # Check for empty SIDs or None values in database and ensure they're truly NULL
        if db_team.player1_session_id == '':
            db_team.player1_session_id = None
            print(f"Fixing empty string in player1_session_id")
            
        if db_team.player2_session_id == '':
            db_team.player2_session_id = None
            print(f"Fixing empty string in player2_session_id")
            
        # Always check database for duplicate SIDs or empty strings
        if db_team.player1_session_id == db_team.player2_session_id and db_team.player1_session_id is not None:
            print(f"ERROR: Same SID {db_team.player1_session_id} found in both player positions in database")
            
            # Check if this SID is actually connected
            if db_team.player1_session_id in state.connected_players:
                print(f"SID {db_team.player1_session_id} is still connected, keeping in player1 position")
                db_team.player2_session_id = None
            else:
                print(f"SID {db_team.player1_session_id} is not connected, clearing both positions")
                db_team.player1_session_id = None
                db_team.player2_session_id = None
            
            db.session.commit()
            return False
        
        # Check if database SIDs are actually still connected
        if db_team.player1_session_id is not None and db_team.player1_session_id not in state.connected_players:
            print(f"SID {db_team.player1_session_id} in player1 position is no longer connected, clearing it")
            db_team.player1_session_id = None
            db.session.commit()
            
        if db_team.player2_session_id is not None and db_team.player2_session_id not in state.connected_players:
            print(f"SID {db_team.player2_session_id} in player2 position is no longer connected, clearing it")
            db_team.player2_session_id = None
            db.session.commit()
            
        # Check memory for duplicate players
        if len(players) > 1 and len(set(players)) < len(players):
            print(f"ERROR: Duplicate SIDs found in memory players array: {players}")
            unique_players = []
            seen = set()
            for player in players:
                if player and player not in seen:
                    unique_players.append(player)
                    seen.add(player)
            team_info['players'] = unique_players
            return False
        
        # Check if memory players are still connected
        disconnected_players = [p for p in players if p not in state.connected_players]
        if disconnected_players:
            print(f"Removing disconnected players from memory: {disconnected_players}")
            team_info['players'] = [p for p in players if p in state.connected_players]
            
        # Final sanity check - ensure database and memory match
        db_sids = [sid for sid in [db_team.player1_session_id, db_team.player2_session_id] if sid is not None]
        memory_sids = team_info['players']
        
        # Check for mismatch between DB and memory
        if set(db_sids) != set(memory_sids):
            print(f"Mismatch between DB players {db_sids} and memory players {memory_sids}")
            
            # Determine which source to trust based on connected players
            db_connected = [sid for sid in db_sids if sid in state.connected_players]
            memory_connected = [sid for sid in memory_sids if sid in state.connected_players]
            
            if len(memory_connected) >= len(db_connected):
                # Trust memory
                print(f"Trusting memory over database")
                if len(memory_connected) > 0:
                    db_team.player1_session_id = memory_connected[0]
                else:
                    db_team.player1_session_id = None
                    
                if len(memory_connected) > 1:
                    db_team.player2_session_id = memory_connected[1]
                else:
                    db_team.player2_session_id = None
            else:
                # Trust database
                print(f"Trusting database over memory")
                team_info['players'] = db_connected
                
            db.session.commit()
            return False
            
        return True
    except Exception as e:
        print(f"Error in validate_team_sessions: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def sync_team_state(team_name):
    """
    Helper function to ensure database and memory state are consistent
    for a given team.
    """
    try:
        team_info = state.active_teams.get(team_name)
        if not team_info:
            print(f"Warning: Team {team_name} not found in memory - cannot sync")
            return False
            
        db_team = Teams.query.get(team_info['team_id'])
        if not db_team:
            print(f"Warning: Team ID {team_info['team_id']} not found in database - cannot sync")
            return False
            
        players = team_info['players'].copy()  # Work with a copy to avoid issues during iteration
        
        # Remove any None values
        players = [p for p in players if p is not None]
        
        # Get current size of players array
        player_count = len(players)
        
        # Detect duplicate SIDs in the players array and fix them
        if player_count > 1:
            duplicate_found = False
            # Check for duplicates in the memory list
            if players.count(players[0]) > 1:
                print(f"Fixing duplicate SID {players[0]} in players array")
                duplicate_found = True
            
            # Check database for the same SID in both positions
            if db_team.player1_session_id is not None and db_team.player1_session_id == db_team.player2_session_id:
                print(f"Found same SID {db_team.player1_session_id} in both player positions in database")
                # Clear player2 since it's a duplicate
                db_team.player2_session_id = None
                duplicate_found = True

            if duplicate_found:
                unique_players = []
                seen = set()
                for player in players:
                    if player not in seen:
                        unique_players.append(player)
                        seen.add(player)
                    else:
                        print(f"Removed duplicate player SID: {player}")
                players = unique_players
                player_count = len(players)
        
        # Check for consistency between memory and database
        # If there's a player1 in database but not in memory (and room in memory)
        if db_team.player1_session_id and (player_count == 0 or db_team.player1_session_id != players[0]):
            if player_count == 0:
                print(f"Adding missing player1 {db_team.player1_session_id} to memory")
                players.append(db_team.player1_session_id)
                player_count = 1
            elif player_count == 1 and not db_team.player2_session_id:
                # If the DB has a player1 but memory has someone else in that spot
                # and no player2 exists, move memory player to player2 spot
                print(f"Moving player in memory from p1 to p2 since db has p1={db_team.player1_session_id}")
                players.append(players[0])  
                players[0] = db_team.player1_session_id
                player_count = 2
                
        # If there's a player2 in database but not in memory
        if db_team.player2_session_id and (player_count < 2 or db_team.player2_session_id != players[1 if player_count > 1 else 0]):
            if player_count < 2:
                print(f"Adding missing player2 {db_team.player2_session_id} to memory")
                players.append(db_team.player2_session_id)
                player_count = 2
                
        # Remove any disconnected players from the memory array
        connected_players = [p for p in players if p in state.connected_players]
        if len(connected_players) < len(players):
            disconnected_players = set(players) - set(connected_players)
            print(f"Removing disconnected players from memory: {disconnected_players}")
            players = connected_players
            player_count = len(players)

        # Now update the database based on the fixed memory state
        if player_count > 0:
            if db_team.player1_session_id != players[0]:
                print(f"Fixing mismatch: db p1={db_team.player1_session_id}, memory p1={players[0]}")
                db_team.player1_session_id = players[0]
        else:
            # No players in memory, clear player1 in db
            if db_team.player1_session_id is not None:
                print(f"Clearing db player1 because no players in memory")
                db_team.player1_session_id = None
            
        if player_count > 1:
            if db_team.player2_session_id != players[1]:
                print(f"Fixing mismatch: db p2={db_team.player2_session_id}, memory p2={players[1]}")
                db_team.player2_session_id = players[1]
        elif db_team.player2_session_id is not None:
            print(f"Clearing db player2 because not enough players in memory")
            db_team.player2_session_id = None
        
        # Update the team_info players array with our fixed version
        team_info['players'] = players
            
        db.session.commit()
        
        # Double check player_to_team mapping is correct
        for idx, player_sid in enumerate(players):
            if player_sid and player_sid not in state.player_to_team:
                print(f"Fixing missing player_to_team mapping for {player_sid}")
                state.player_to_team[player_sid] = team_name
            
        return True
    except Exception as e:
        print(f"Error in sync_team_state: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

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
        
        # Only emit team update, not full dashboard refresh
        emit_dashboard_team_update()

        if len(team_info['answered_current_round']) == 2:
            # print(f"Both players in team {team_name} answered round {team_info['current_round_number']}.")
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
            game_status = ""
            if state.game_started:
                game_status = " Game has started!" if not state.game_paused else " Game is paused!"
            else:
                game_status = " Waiting for game to start."
            status_message = "Team is full!" + game_status
            
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
            
        # Check team membership in database first
        db_team = Teams.query.get(team_info['team_id'])
        
        # Determine player position from database first - this is most reliable
        player_idx = None
        is_db_member = False
        
        # Direct database check
        if db_team.player1_session_id == previous_sid:
            player_idx = 0
            is_db_member = True
            print(f"Rejoin: Found previous_sid {previous_sid} as player1 in database")
        elif db_team.player2_session_id == previous_sid:
            player_idx = 1
            is_db_member = True
            print(f"Rejoin: Found previous_sid {previous_sid} as player2 in database")
        
        # If not found directly, check previous session chains
        if player_idx is None:
            # Check our chain of previous sessions
            current_sid_chain = set()
            temp_sid = previous_sid
            while temp_sid in state.previous_sessions and temp_sid not in current_sid_chain:
                current_sid_chain.add(temp_sid)
                temp_sid = state.previous_sessions[temp_sid]
                
                # Check if this is in the database
                if db_team.player1_session_id == temp_sid:
                    player_idx = 0
                    is_db_member = True
                    print(f"Rejoin: Found sid {temp_sid} in session chain as player1")
                    break
                elif db_team.player2_session_id == temp_sid:
                    player_idx = 1
                    is_db_member = True
                    print(f"Rejoin: Found sid {temp_sid} in session chain as player2")
                    break
        
        # Next check in-memory state only if we haven't found a position
        if player_idx is None:
            if previous_sid in team_info['players']:
                player_idx = team_info['players'].index(previous_sid)
                print(f"Rejoin: Found previous_sid {previous_sid} at index {player_idx} in memory")
                # Update database to match memory for consistency
                is_db_member = True
        
        # If we still haven't found a position but team isn't full, assign to available slot
        if player_idx is None and is_db_member and len(team_info['players']) < 2:
            available_positions = set([0, 1]).difference(set(range(len(team_info['players']))))
            if available_positions:
                player_idx = min(available_positions)
                print(f"Rejoin: Assigning to available slot {player_idx}")

        # Last resort - if the team has an empty slot, use it
        if player_idx is None and len(team_info['players']) < 2:
            if len(team_info['players']) == 0:
                player_idx = 0
                print(f"Rejoin: Last resort, assigning to position 0")
            elif len(team_info['players']) == 1:
                player_idx = 1
                print(f"Rejoin: Last resort, assigning to position 1")
        
        # If we still don't have a valid index, use position 0 as a fallback for connected players
        # This prevents the NoneType error in list indices
        if player_idx is None:
            if is_db_member:
                # If we determined they should be a member but couldn't figure out position
                player_idx = 0
                print(f"Rejoin: Using fallback position 0 for verified member")
            else:
                emit('rejoin_team_failed', {'message': 'You were not a member of this team'}); return
            
        # Update session mapping
        state.previous_sessions[previous_sid] = current_sid
        print(f"Rejoin: Mapping previous sid {previous_sid} to current sid {current_sid}")
        
        # Update team info with new sid based on assigned player_idx
        print(f"Rejoin: Updating team to add {current_sid} at position {player_idx}")
        
        # If we have a valid player index, ensure it's within bounds and update the array
        if player_idx == 0 or player_idx == 1:  
            # For consistency, ensure the players array is properly sized
            while len(team_info['players']) <= player_idx:
                team_info['players'].append(None)
                
            # Now set the player at the correct index
            team_info['players'][player_idx] = current_sid
            
            # If this is the player1 position and player2 exists but is invalid, clear it out
            if player_idx == 0 and len(team_info['players']) > 1 and team_info['players'][1] == current_sid:
                print(f"Rejoin: Detected duplicate SID {current_sid} in position 1, clearing")
                team_info['players'][1] = None
                
                # If this is the player2 position and player1 is the same, clear player1
            if player_idx == 1 and len(team_info['players']) > 0 and team_info['players'][0] == current_sid:
                print(f"Rejoin: Detected duplicate SID {current_sid} in position 0, clearing")
                team_info['players'][0] = None
                
            # Clean up the players array - remove None values
            team_info['players'] = [p for p in team_info['players'] if p is not None]
        else:
            print(f"Rejoin ERROR: Invalid player_idx {player_idx}")

        # Update database with the correct player position based on our determined index
        if db_team:
            print(f"Rejoin: Updating database - player {current_sid} is at position {player_idx}")
            # First check if this SID is already used in the other position
            if player_idx == 0:
                if db_team.player2_session_id == current_sid:
                    print(f"Warning: SID {current_sid} already in player2 position, clearing it")
                    db_team.player2_session_id = None
                db_team.player1_session_id = current_sid
            elif player_idx == 1:
                if db_team.player1_session_id == current_sid:
                    print(f"Warning: SID {current_sid} already in player1 position, clearing it")
                    db_team.player1_session_id = None
                db_team.player2_session_id = current_sid
            else:
                print(f"Rejoin ERROR: Invalid player_idx {player_idx}")
            db.session.commit()
                
        # Update player to team mapping
        state.player_to_team[current_sid] = team_name
        if previous_sid in state.player_to_team:
            del state.player_to_team[previous_sid]
            print(f"Rejoin: Removed previous player mapping for {previous_sid}")
            
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
            game_status = ""
            if state.game_started:
                game_status = " Game has started!" if not state.game_paused else " Game is paused!"
            else:
                game_status = " Waiting for game to start."
            status_message = "Team is full!" + game_status
            
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
        
        # First validate the team sessions to check for duplicates
        validate_team_sessions(team_name)
        
        # Final sanity check - ensure database and memory are in sync
        sync_team_state(team_name)
            
        emit_dashboard_team_update()
        
    except Exception as e:
        print(f"Error in on_rejoin_team: {str(e)}")
        import traceback
        traceback.print_exc()
        emit('rejoin_team_failed', {'message': f'Error rejoining team: {str(e)}'})
