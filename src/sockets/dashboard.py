from flask import jsonify
from src.config import app, socketio, db
from src.state import state
from src.models.quiz_models import Teams, Answers, PairQuestionRounds
from src.game_logic import QUESTION_ITEMS, TARGET_COMBO_REPEATS
from flask_socketio import emit
from src.game_logic import start_new_round_for_pair
from time import time
import hashlib

# Store last activity time for each dashboard client
dashboard_last_activity = {}

@socketio.on('keep_alive')
def on_keep_alive():
    try:
        from flask import request
        sid = request.sid
        if sid in state.dashboard_clients:
            dashboard_last_activity[sid] = time()
            emit('keep_alive_ack', room=sid)
    except Exception as e:
        print(f"Error in on_keep_alive: {str(e)}")
        import traceback
        traceback.print_exc()

def compute_team_hashes(team_id):
    try:
        # Get all rounds and answers for this team in chronological order
        rounds = PairQuestionRounds.query.filter_by(team_id=team_id).order_by(PairQuestionRounds.timestamp_initiated).all()
        answers = Answers.query.filter_by(team_id=team_id).order_by(Answers.timestamp).all()

        # Create history string containing both questions and answers
        history = []
        for round in rounds:
            history.append(f"P1:{round.player1_item.value if round.player1_item else 'None'}")
            history.append(f"P2:{round.player2_item.value if round.player2_item else 'None'}")
        for answer in answers:
            history.append(f"A:{answer.assigned_item.value}:{answer.response_value}")
        
        history_str = "|".join(history)

        # print(f"History for team {team_id}: {history_str}")
        # print(rounds)
        
        # Generate two different hashes
        hash1 = hashlib.sha256(history_str.encode()).hexdigest()[:8]
        hash2 = hashlib.md5(history_str.encode()).hexdigest()[:8]
        
        return hash1, hash2
    except Exception as e:
        print(f"Error computing team hashes: {str(e)}")
        return "ERROR", "ERROR"

def compute_correlation_matrix(team_id):
    try:
        # Get all rounds and their corresponding answers for this team
        rounds = PairQuestionRounds.query.filter_by(team_id=team_id).order_by(PairQuestionRounds.timestamp_initiated).all()
        
        # Create a mapping from round_id to the round object for quick access
        round_map = {round.round_id: round for round in rounds}
        
        # Get all answers for this team
        answers = Answers.query.filter_by(team_id=team_id).order_by(Answers.timestamp).all()
        
        # Group answers by round_id
        answers_by_round = {}
        for answer in answers:
            if answer.question_round_id not in answers_by_round:
                answers_by_round[answer.question_round_id] = []
            answers_by_round[answer.question_round_id].append(answer)
        
        # Prepare the 4x4 correlation matrix for A, B, X, Y combinations
        item_values = ['A', 'B', 'X', 'Y']
        corr_matrix = [[0 for _ in range(4)] for _ in range(4)]
        
        # Count pairs for each item combination
        pair_counts = {(i, j): 0 for i in item_values for j in item_values}
        correlation_sums = {(i, j): 0 for i in item_values for j in item_values}
        
        # Analyze each round that has both player answers
        for round_id, round_answers in answers_by_round.items():
            # Skip if we don't have exactly 2 answers (one from each player)
            if len(round_answers) != 2 or round_id not in round_map:
                continue
                
            round_obj = round_map[round_id]
            p1_item = round_obj.player1_item.value if round_obj.player1_item else None
            p2_item = round_obj.player2_item.value if round_obj.player2_item else None
            
            # Skip if we don't have both items
            if not p1_item or not p2_item:
                continue
                
            # Get player responses (True/False)
            # Find which answer belongs to which player
            p1_answer = None
            p2_answer = None
            
            for answer in round_answers:
                if answer.assigned_item.value == p1_item:
                    p1_answer = answer.response_value
                elif answer.assigned_item.value == p2_item:
                    p2_answer = answer.response_value
            
            # Skip if we don't have both answers
            if p1_answer is None or p2_answer is None:
                continue
                
            # Update counts
            p1_idx = item_values.index(p1_item)
            p2_idx = item_values.index(p2_item)
            
            # Calculate correlation: (T,T) or (F,F) count as 1, (T,F) or (F,T) count as -1
            correlation = 1 if p1_answer == p2_answer else -1
            
            pair_counts[(p1_item, p2_item)] += 1
            correlation_sums[(p1_item, p2_item)] += correlation
        
        # Calculate correlations for each cell in the matrix
        for i, row_item in enumerate(item_values):
            for j, col_item in enumerate(item_values):
                count = pair_counts[(row_item, col_item)]
                if count > 0:
                    corr_matrix[i][j] = correlation_sums[(row_item, col_item)] / count
                else:
                    corr_matrix[i][j] = 0
        
        return corr_matrix, item_values
    except Exception as e:
        print(f"Error computing correlation matrix: {str(e)}")
        import traceback
        traceback.print_exc()
        return [[0 for _ in range(4)] for _ in range(4)], ['A', 'B', 'X', 'Y']

def compute_correlation_stats(team_id):
    try:
        # Get the correlation matrix
        corr_matrix, item_values = compute_correlation_matrix(team_id)
        
        # Validate matrix dimensions and contents
        if not all(isinstance(row, list) and len(row) == 4 for row in corr_matrix) or len(corr_matrix) != 4:
            print(f"Invalid correlation matrix dimensions for team_id {team_id}")
            return 0.0, 0.0
            
        # Validate expected item values
        expected_items = ['A', 'B', 'X', 'Y']
        if not all(item in item_values for item in expected_items):
            print(f"Missing expected items in correlation matrix for team_id {team_id}")
            return 0.0, 0.0
            
        # Calculate first statistic: Trace(corr_matrix) / 4
        try:
            trace_sum = sum(corr_matrix[i][i] for i in range(4))
            stat1 = trace_sum / 4
        except (TypeError, IndexError) as e:
            print(f"Error calculating trace statistic: {e}")
            stat1 = 0.0
        
        # Calculate second statistic using CHSH game formula
        # corrAX + corrAY + corrBX - corrBY + corrXA + corrXB + corrYA - corrYB
        # Get indices for A, B, X, Y from item_values
        try:
            A_idx = item_values.index('A')
            B_idx = item_values.index('B')
            X_idx = item_values.index('X')
            Y_idx = item_values.index('Y')
            
            stat2 = (
                corr_matrix[A_idx][X_idx] + corr_matrix[A_idx][Y_idx] + 
                corr_matrix[B_idx][X_idx] - corr_matrix[B_idx][Y_idx] +
                corr_matrix[X_idx][A_idx] + corr_matrix[X_idx][B_idx] + 
                corr_matrix[Y_idx][A_idx] - corr_matrix[Y_idx][B_idx]
            )
        except (ValueError, IndexError, TypeError) as e:
            print(f"Error calculating CHSH statistic: {e}")
            stat2 = 0.0
        
        return stat1, stat2
    except Exception as e:
        print(f"Error computing correlation statistics: {str(e)}")
        import traceback
        traceback.print_exc()
        return 0.0, 0.0


def get_serialized_active_teams():
    try:
        teams_list = []
        for name, info in state.active_teams.items():
            players = info['players']
            # Compute hashes for the team
            hash1, hash2 = compute_team_hashes(info['team_id'])
            # Check if all combinations have reached target repeats
            all_combos = [(i1.value, i2.value) for i1 in QUESTION_ITEMS for i2 in QUESTION_ITEMS]
            combo_tracker = info.get('combo_tracker', {})
            min_stats_sig = all(combo_tracker.get(combo, 0) >= TARGET_COMBO_REPEATS 
                            for combo in all_combos)
            
            # Compute correlation matrix for the team
            correlation_matrix, item_labels = compute_correlation_matrix(info['team_id'])
            
            # Compute correlation statistics
            stat1, stat2 = compute_correlation_stats(info['team_id'])
            
            teams_list.append({
                'team_name': name,
                'team_id': info['team_id'],
                'player1_sid': players[0] if len(players) > 0 else None,
                'player2_sid': players[1] if len(players) > 1 else None,
                'current_round_number': info.get('current_round_number', 0),
                'history_hash1': hash1,
                'history_hash2': hash2,
                'min_stats_sig': min_stats_sig,
                'correlation_matrix': correlation_matrix,
                'correlation_labels': item_labels,
                'correlation_stats': {
                    'trace_avg': stat1,
                    'chsh_value': stat2
                }
            })
        return teams_list
    except Exception as e:
        print(f"Error in get_serialized_active_teams: {str(e)}")
        import traceback
        traceback.print_exc()
        return []

def emit_dashboard_team_update():
    try:
        serialized_teams = get_serialized_active_teams()
        update_data = {
            'teams': serialized_teams,
            'connected_players_count': len(state.connected_players)
        }
        for sid in state.dashboard_clients:
            socketio.emit('team_status_changed_for_dashboard', update_data, room=sid)
    except Exception as e:
        print(f"Error in emit_dashboard_team_update: {str(e)}")
        import traceback
        traceback.print_exc()

def emit_dashboard_full_update(client_sid=None):
    try:
        with app.app_context():
            total_answers = Answers.query.count()

        update_data = {
            'active_teams': get_serialized_active_teams(),
            'total_answers_count': total_answers,
            'connected_players_count': len(state.connected_players),
            'game_state': {
                'started': state.game_started,
                'paused': state.game_paused,
                'streaming_enabled': state.answer_stream_enabled
            }
        }
        if client_sid:
            socketio.emit('dashboard_update', update_data, room=client_sid)
        else:
            for dash_sid in state.dashboard_clients:
                socketio.emit('dashboard_update', update_data, room=dash_sid)
    except Exception as e:
        print(f"Error in emit_dashboard_full_update: {str(e)}")
        import traceback
        traceback.print_exc()

@socketio.on('dashboard_join')
def on_dashboard_join(data=None, callback=None):
    try:
        from flask import request
        sid = request.sid
        
        # Add to dashboard clients
        state.dashboard_clients.add(sid)
        dashboard_last_activity[sid] = time()
        print(f"Dashboard client connected: {sid}")
        
        # Whenever a dashboard client joins, emit updated status to all dashboards
        emit_dashboard_full_update()
        
        # Prepare update data
        with app.app_context():
            total_answers = Answers.query.count()
        update_data = {
            'active_teams': get_serialized_active_teams(),
            'total_answers_count': total_answers,
            'connected_players_count': len(state.connected_players),
            'game_state': {
                'started': state.game_started,
                'streaming_enabled': state.answer_stream_enabled
            }
        }
        
        # If callback provided, use it to return data directly
        if callback:
            callback(update_data)
        else:
            # Otherwise emit as usual
            socketio.emit('dashboard_update', update_data, room=sid)
    except Exception as e:
        print(f"Error in on_dashboard_join: {str(e)}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': f'Error joining dashboard: {str(e)}'})

@socketio.on('start_game')
def on_start_game(data=None):
    try:
        from flask import request
        if request.sid in state.dashboard_clients:
            state.game_started = True
            # Notify teams and dashboard that game has started
            for team_name, team_info in state.active_teams.items():
                if len(team_info['players']) == 2:  # Only notify paired teams
                    socketio.emit('game_start', {'game_started': True}, room=team_name)
            
            # Notify dashboard
            for dashboard_sid in state.dashboard_clients:
                socketio.emit('game_started', room=dashboard_sid)
                
            # Notify all clients about game state change
            socketio.emit('game_state_changed', {'game_started': True})
                
            # Start first round for all paired teams
            for team_name, team_info in state.active_teams.items():
                if len(team_info['players']) == 2: # If team is paired
                    start_new_round_for_pair(team_name)
    except Exception as e:
        print(f"Error in on_start_game: {str(e)}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': f'Error starting game: {str(e)}'})

@socketio.on('pause_game')
def on_pause_game():
    try:
        from flask import request
        if request.sid not in state.dashboard_clients:
            emit('error', {'message': 'Unauthorized: Not a dashboard client'})
            return

        state.game_paused = not state.game_paused  # Toggle pause state
        pause_status = "paused" if state.game_paused else "resumed"
        print(f"Game {pause_status} by {request.sid}")

        # Notify all clients about pause state change
        for team_name in state.active_teams.keys():
            socketio.emit('game_state_update', {
                'paused': state.game_paused
            }, room=team_name)

        # Update dashboard state
        emit_dashboard_full_update()

    except Exception as e:
        print(f"Error in on_pause_game: {str(e)}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': f'Error toggling game pause: {str(e)}'})

@socketio.on('disconnect')
def on_disconnect():
    try:
        from flask import request
        sid = request.sid
        if sid in state.dashboard_clients:
            state.dashboard_clients.remove(sid)
            if sid in dashboard_last_activity:
                del dashboard_last_activity[sid]
    except Exception as e:
        print(f"Error in on_disconnect: {str(e)}")
        import traceback
        traceback.print_exc()

@socketio.on('restart_game')
def on_restart_game():
    try:
        from flask import request
        print(f"Received restart_game from {request.sid}")
        if request.sid not in state.dashboard_clients:
            emit('error', {'message': 'Unauthorized: Not a dashboard client'})
            emit('game_reset_complete', room=request.sid)
            return

        # First update game state to prevent new answers during reset
        state.game_started = False
        # print("Set game_started=False")
        
        # Even if there are no active teams, clear the database
        try:
            # Clear database entries within a transaction
            db.session.begin_nested()  # Create savepoint
            PairQuestionRounds.query.delete()
            Answers.query.delete()
            db.session.commit()
        except Exception as db_error:
            db.session.rollback()
            print(f"Database error during game reset: {str(db_error)}")
            import traceback
            traceback.print_exc()
            emit('error', {'message': 'Database error during reset'})
            emit('game_reset_complete', room=request.sid)
            return

        # If no active teams, still complete the reset successfully
        if not state.active_teams:
            emit('game_state_changed', {'game_started': False})
            emit_dashboard_full_update()
            emit('game_reset_complete', room=request.sid)
            return
        
        # Reset team state after successful database clear
        for team_name, team_info in state.active_teams.items():
            if team_info:  # Validate team info exists
                team_info['current_round_number'] = 0
                team_info['current_db_round_id'] = None
                team_info['answered_current_round'] = {}
                team_info['combo_tracker'] = {}
        
        # Notify all teams about the reset
        for team_name in state.active_teams.keys():
            socketio.emit('game_reset', room=team_name)
        
        # Ensure all clients are notified of the state change
        socketio.emit('game_state_changed', {'game_started': False})
        
        # Update dashboard with reset state
        emit_dashboard_full_update()

        # Notify dashboard clients that reset is complete
        print("Emitting game_reset_complete to all dashboard clients")
        for dash_sid in state.dashboard_clients:
            socketio.emit('game_reset_complete', room=dash_sid)
            
    except Exception as e:
        print(f"Error in on_restart_game: {str(e)}")
        import traceback
        traceback.print_exc()
        emit('error', {'message': f'Error restarting game: {str(e)}'})

@app.route('/api/dashboard/data', methods=['GET'])
def get_dashboard_data():
    try:
        all_answers = Answers.query.order_by(Answers.timestamp.asc()).all()
        answers_data = [
            {
                'answer_id': ans.answer_id,
                'team_id': ans.team_id,
                'team_name': Teams.query.get(ans.team_id).team_name if Teams.query.get(ans.team_id) else 'N/A',
                'player_session_id': ans.player_session_id,
                'question_round_id': ans.question_round_id,
                'assigned_item': ans.assigned_item.value,
                'response_value': ans.response_value,
                'timestamp': ans.timestamp.isoformat()
            } for ans in all_answers
        ]
        return jsonify({'answers': answers_data}), 200
    except Exception as e:
        print(f"Error in get_dashboard_data: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500
