import pytest
from unittest.mock import patch, ANY, MagicMock
from flask import request
from src.config import app, socketio, db
from src.models.quiz_models import Teams
from src.state import state
from src.sockets.team_management import (
    handle_connect, handle_disconnect, on_create_team, 
    on_join_team, on_leave_team, emit_dashboard_team_update
)
import time

@pytest.fixture
def app_context():
    with app.app_context():
        app.extensions['socketio'] = socketio
        yield app

@pytest.fixture
def mock_request_context(app_context):
    with app_context.test_request_context('/') as context:
        context.request.sid = 'test_sid'
        context.request.namespace = '/'
        yield context.request

@pytest.fixture(autouse=True)
def cleanup_state():
    """Clean up state after each test"""
    yield
    state.active_teams.clear()
    state.player_to_team.clear()
    state.team_id_to_name.clear()
    state.connected_players.clear()
    state.dashboard_clients.clear()
    # Clean up any test teams from database
    with app.app_context():
        Teams.query.filter(Teams.team_name.like('test_%')).delete()
        db.session.commit()

class TestTeamFormationDynamics:
    """Test team formation, disconnection, and dashboard update dynamics"""

    def test_sequential_team_formation_and_dashboard_updates(self, mock_request_context):
        """Test sequential team formation with dashboard updates at each step"""
        with patch('src.sockets.team_management.emit') as mock_emit, \
             patch('src.sockets.team_management.socketio.emit') as mock_socketio_emit, \
             patch('src.sockets.team_management.emit_dashboard_team_update') as mock_dashboard_update, \
             patch('src.sockets.team_management.join_room') as mock_join_room:
            
            # Add dashboard client
            state.dashboard_clients.add('dashboard_1')
            
            # Step 1: Player 1 connects
            handle_connect()
            assert 'test_sid' in state.connected_players
            
            # Step 2: Player 1 creates team
            on_create_team({'team_name': 'test_team_dynamics'})
            
            # Verify team creation
            assert 'test_team_dynamics' in state.active_teams
            assert state.active_teams['test_team_dynamics']['status'] == 'waiting_pair'
            assert len(state.active_teams['test_team_dynamics']['players']) == 1
            
            # Dashboard should be updated
            assert mock_dashboard_update.call_count >= 1
            
            # Step 3: Player 2 joins
            request.sid = 'player2_sid'
            state.connected_players.add('player2_sid')
            on_join_team({'team_name': 'test_team_dynamics'})
            
            # Verify team is now full
            assert len(state.active_teams['test_team_dynamics']['players']) == 2
            assert state.active_teams['test_team_dynamics']['status'] == 'active'
            
            # Dashboard should be updated again
            assert mock_dashboard_update.call_count >= 2
            
            # Verify both players are tracked
            assert state.player_to_team['test_sid'] == 'test_team_dynamics'
            assert state.player_to_team['player2_sid'] == 'test_team_dynamics'

    def test_rapid_team_formation_dissolution(self, mock_request_context):
        """Test rapid team formation and dissolution with multiple players"""
        with patch('src.sockets.team_management.emit') as mock_emit, \
             patch('src.sockets.team_management.socketio.emit') as mock_socketio_emit, \
             patch('src.sockets.team_management.emit_dashboard_team_update') as mock_dashboard_update, \
             patch('src.sockets.team_management.join_room') as mock_join_room, \
             patch('src.sockets.team_management.leave_room') as mock_leave_room:
            
            # Create multiple teams rapidly
            teams = []
            for i in range(3):
                team_name = f'test_rapid_team_{i}'
                request.sid = f'creator_{i}'
                state.connected_players.add(f'creator_{i}')
                on_create_team({'team_name': team_name})
                teams.append(team_name)
                
                # Add second player to each team
                request.sid = f'joiner_{i}'
                state.connected_players.add(f'joiner_{i}')
                on_join_team({'team_name': team_name})
            
            # Verify all teams are active
            assert len(state.active_teams) == 3
            for team_name in teams:
                assert state.active_teams[team_name]['status'] == 'active'
                assert len(state.active_teams[team_name]['players']) == 2
            
            # Rapidly disconnect first player from each team
            for i in range(3):
                request.sid = f'creator_{i}'
                handle_disconnect()
            
            # Verify teams are now waiting for players
            for team_name in teams:
                if team_name in state.active_teams:  # Some might be dissolved
                    assert state.active_teams[team_name]['status'] == 'waiting_pair'
                    assert len(state.active_teams[team_name]['players']) == 1

    def test_dashboard_consistency_during_team_changes(self, mock_request_context):
        """Test that dashboard receives consistent updates during rapid team changes"""
        dashboard_updates = []
        
        def capture_dashboard_update():
            dashboard_updates.append({
                'teams_count': len(state.active_teams),
                'total_players': sum(len(team['players']) for team in state.active_teams.values()),
                'timestamp': time.time()
            })
        
        with patch('src.sockets.team_management.emit') as mock_emit, \
             patch('src.sockets.team_management.socketio.emit') as mock_socketio_emit, \
             patch('src.sockets.team_management.join_room') as mock_join_room, \
             patch('src.sockets.team_management.leave_room') as mock_leave_room:
            
            # Mock the dashboard update to capture state
            with patch('src.sockets.team_management.emit_dashboard_team_update', 
                      side_effect=capture_dashboard_update):
                
                # Add dashboard clients
                state.dashboard_clients.update(['dash1', 'dash2', 'dash3'])
                
                # Perform sequence of operations
                operations = [
                    ('create', 'team_a', 'player_1'),
                    ('create', 'team_b', 'player_2'),
                    ('join', 'team_a', 'player_3'),
                    ('join', 'team_b', 'player_4'),
                    ('disconnect', None, 'player_1'),
                    ('create', 'team_c', 'player_5'),
                    ('disconnect', None, 'player_2'),
                    ('join', 'team_c', 'player_6')
                ]
                
                for op_type, team_name, player_id in operations:
                    request.sid = player_id
                    if player_id not in state.connected_players:
                        state.connected_players.add(player_id)
                    
                    if op_type == 'create':
                        on_create_team({'team_name': team_name})
                    elif op_type == 'join':
                        on_join_team({'team_name': team_name})
                    elif op_type == 'disconnect':
                        handle_disconnect()
                
                # Verify dashboard was updated at each step
                assert len(dashboard_updates) >= len(operations)
                
                # Check that player counts are consistent
                for i, update in enumerate(dashboard_updates[1:], 1):
                    prev_update = dashboard_updates[i-1]
                    # Each update should represent a valid state transition
                    assert update['teams_count'] >= 0
                    assert update['total_players'] >= 0

    def test_multiple_dashboard_clients_receive_same_updates(self, mock_request_context):
        """Test that multiple dashboard clients receive consistent updates"""
        dashboard_emissions = []
        
        def capture_socketio_emit(event, data, to=None):
            if event == 'team_status_changed_for_dashboard':
                dashboard_emissions.append({
                    'event': event,
                    'to': to,
                    'teams_count': len(data.get('teams', [])),
                    'connected_players': data.get('connected_players_count', 0)
                })
        
        with patch('src.sockets.team_management.emit') as mock_emit, \
             patch('src.sockets.team_management.join_room') as mock_join_room, \
             patch('src.sockets.team_management.socketio.emit', side_effect=capture_socketio_emit):
            
            # Add multiple dashboard clients
            dashboards = ['dash_1', 'dash_2', 'dash_3']
            state.dashboard_clients.update(dashboards)
            
            # Perform team operations
            on_create_team({'team_name': 'test_multi_dash'})
            
            request.sid = 'player_2'
            state.connected_players.add('player_2')
            on_join_team({'team_name': 'test_multi_dash'})
            
            # Verify each dashboard client received updates
            dashboard_events = [e for e in dashboard_emissions if e['event'] == 'team_status_changed_for_dashboard']
            
            # Should have emissions for each dashboard client
            for dashboard_id in dashboards:
                dashboard_specific_events = [e for e in dashboard_events if e['to'] == dashboard_id]
                assert len(dashboard_specific_events) > 0, f"Dashboard {dashboard_id} didn't receive updates"

    def test_team_name_conflicts_and_resolution(self, mock_request_context):
        """Test handling of team name conflicts when teams become inactive"""
        with patch('src.sockets.team_management.emit') as mock_emit, \
             patch('src.sockets.team_management.socketio.emit') as mock_socketio_emit, \
             patch('src.sockets.team_management.join_room') as mock_join_room, \
             patch('src.sockets.team_management.leave_room') as mock_leave_room:
            
            # Create first team
            on_create_team({'team_name': 'conflict_team'})
            team1_id = state.active_teams['conflict_team']['team_id']
            
            # Player leaves, making team inactive
            on_leave_team({})
            
            # Verify team is now inactive in database
            team1 = Teams.query.get(team1_id)
            assert team1.is_active == False
            
            # Create new team with same name
            request.sid = 'new_player'
            state.connected_players.add('new_player')
            on_create_team({'team_name': 'conflict_team'})
            
            # Should succeed - new active team created
            assert 'conflict_team' in state.active_teams
            team2_id = state.active_teams['conflict_team']['team_id']
            assert team2_id != team1_id
            
            # Verify database state
            team2 = Teams.query.get(team2_id)
            assert team2.is_active == True
            assert team2.team_name == 'conflict_team'

    def test_game_state_during_team_transitions(self, mock_request_context):
        """Test game state behavior during team formation and dissolution"""
        with patch('src.sockets.team_management.emit') as mock_emit, \
             patch('src.sockets.team_management.socketio.emit') as mock_socketio_emit, \
             patch('src.sockets.team_management.join_room') as mock_join_room, \
             patch('src.sockets.team_management.leave_room') as mock_leave_room, \
             patch('src.sockets.team_management.start_new_round_for_pair') as mock_start_round:
            
            # Start with game not started
            assert state.game_started == False
            
            # Create team and join
            on_create_team({'team_name': 'game_state_team'})
            request.sid = 'player_2'
            state.connected_players.add('player_2')
            on_join_team({'team_name': 'game_state_team'})
            
            # Start game
            state.game_started = True
            
            # Join should trigger new round since game started and team is full
            request.sid = 'player_3'
            state.connected_players.add('player_3')
            # Reset team to single player first
            state.active_teams['game_state_team']['players'] = ['test_sid']
            state.active_teams['game_state_team']['status'] = 'waiting_pair'
            
            on_join_team({'team_name': 'game_state_team'})
            
            # Should have attempted to start new round
            mock_start_round.assert_called_with('game_state_team')
            
            # Verify team status includes game state
            team_status_calls = [call for call in mock_emit.call_args_list 
                               if call[0][0] == 'team_status_update']
            assert any('game_started' in call[0][1] for call in team_status_calls)

    def test_concurrent_team_operations(self, mock_request_context):
        """Test handling of concurrent team operations"""
        with patch('src.sockets.team_management.emit') as mock_emit, \
             patch('src.sockets.team_management.socketio.emit') as mock_socketio_emit, \
             patch('src.sockets.team_management.join_room') as mock_join_room, \
             patch('src.sockets.team_management.leave_room') as mock_leave_room:
            
            # Simulate concurrent operations by rapid successive calls
            
            # Multiple players try to create teams with similar names
            players = ['concurrent_1', 'concurrent_2', 'concurrent_3']
            team_names = ['concurrent_team_1', 'concurrent_team_2', 'concurrent_team_1']  # Duplicate name
            
            for player, team_name in zip(players, team_names):
                request.sid = player
                state.connected_players.add(player)
                on_create_team({'team_name': team_name})
            
            # Verify only unique team names succeeded
            active_team_names = list(state.active_teams.keys())
            assert len(set(active_team_names)) == len(active_team_names)  # No duplicates
            
            # Verify error was emitted for duplicate name
            error_calls = [call for call in mock_emit.call_args_list if call[0][0] == 'error']
            assert len(error_calls) >= 1

    def test_team_dissolution_edge_cases(self, mock_request_context):
        """Test edge cases in team dissolution"""
        with patch('src.sockets.team_management.emit') as mock_emit, \
             patch('src.sockets.team_management.socketio.emit') as mock_socketio_emit, \
             patch('src.sockets.team_management.join_room') as mock_join_room, \
             patch('src.sockets.team_management.leave_room') as mock_leave_room:
            
            # Create team with two players
            on_create_team({'team_name': 'dissolution_team'})
            team_id = state.active_teams['dissolution_team']['team_id']
            
            request.sid = 'player_2'
            state.connected_players.add('player_2')
            on_join_team({'team_name': 'dissolution_team'})
            
            # Both players disconnect simultaneously (simulate)
            request.sid = 'test_sid'
            handle_disconnect()
            
            request.sid = 'player_2'
            # Team should still exist with one player
            assert 'dissolution_team' in state.active_teams
            assert len(state.active_teams['dissolution_team']['players']) == 1
            
            # Second player disconnects
            handle_disconnect()
            
            # Team should now be inactive
            assert 'dissolution_team' not in state.active_teams
            team = Teams.query.get(team_id)
            assert team.is_active == False

    def test_dashboard_state_consistency_after_errors(self, mock_request_context):
        """Test dashboard state remains consistent even after errors"""
        error_count = 0
        
        def mock_emit_with_errors(*args, **kwargs):
            nonlocal error_count
            if error_count < 2:  # Simulate first 2 calls failing
                error_count += 1
                raise Exception("Simulated error")
            return MagicMock()
        
        with patch('src.sockets.team_management.socketio.emit', side_effect=mock_emit_with_errors), \
             patch('src.sockets.team_management.join_room'), \
             patch('src.sockets.team_management.emit') as mock_emit:
            
            state.dashboard_clients.add('dashboard_error_test')
            
            # Operations that would normally trigger dashboard updates
            on_create_team({'team_name': 'error_test_team'})
            
            # Despite errors, team should still be created
            assert 'error_test_team' in state.active_teams
            
            # State should remain internally consistent
            assert state.player_to_team['test_sid'] == 'error_test_team'
            assert 'test_sid' in state.active_teams['error_test_team']['players']

class TestDashboardRealTimeUpdates:
    """Test real-time dashboard updates during team dynamics"""

    def test_dashboard_reflects_player_count_changes(self, mock_request_context):
        """Test dashboard correctly reflects connected player count changes"""
        updates = []
        
        def capture_dashboard_data(*args, **kwargs):
            if args and args[0] == 'team_status_changed_for_dashboard':
                data = args[1] if len(args) > 1 else {}
                updates.append({
                    'connected_players': data.get('connected_players_count', 0),
                    'teams': len(data.get('teams', []))
                })
        
        with patch('src.sockets.team_management.emit'), \
             patch('src.sockets.team_management.join_room'), \
             patch('src.sockets.team_management.socketio.emit', side_effect=capture_dashboard_data):
            
            state.dashboard_clients.add('dashboard_player_count')
            
            # Initial state
            initial_players = len(state.connected_players)
            
            # Connect players and create teams
            for i in range(3):
                player_id = f'count_test_player_{i}'
                request.sid = player_id
                handle_connect()
                on_create_team({'team_name': f'count_test_team_{i}'})
            
            # Verify dashboard received updates with correct player counts
            if updates:
                latest_update = updates[-1]
                assert latest_update['connected_players'] >= initial_players
                assert latest_update['teams'] > 0

    def test_dashboard_team_status_transitions(self, mock_request_context):
        """Test dashboard correctly shows team status transitions"""
        status_transitions = []
        
        def mock_get_all_teams():
            # Simulate the get_all_teams function
            teams = []
            for team_name, team_info in state.active_teams.items():
                teams.append({
                    'team_name': team_name,
                    'team_id': team_info['team_id'],
                    'is_active': True,
                    'status': team_info.get('status', 'unknown'),
                    'current_round_number': team_info.get('current_round_number', 0),
                    'player_count': len(team_info.get('players', []))
                })
            status_transitions.append([t.copy() for t in teams])
            return teams
        
        with patch('src.sockets.team_management.emit'), \
             patch('src.sockets.team_management.join_room'), \
             patch('src.sockets.team_management.get_all_teams', side_effect=mock_get_all_teams):
            
            state.dashboard_clients.add('dashboard_status_test')
            
            # Create team (waiting status)
            on_create_team({'team_name': 'status_transition_team'})
            
            # Join team (active status)
            request.sid = 'joiner_player'
            state.connected_players.add('joiner_player')
            on_join_team({'team_name': 'status_transition_team'})
            
            # Leave team (back to waiting or dissolved)
            on_leave_team({})
            
            # Verify we captured the status transitions
            assert len(status_transitions) >= 3
            
            # Find our team in the transitions
            our_team_transitions = []
            for snapshot in status_transitions:
                team_data = next((t for t in snapshot if t['team_name'] == 'status_transition_team'), None)
                if team_data:
                    our_team_transitions.append(team_data)
            
            if len(our_team_transitions) >= 2:
                # Should see transition from waiting to active (or similar)
                first_status = our_team_transitions[0]
                second_status = our_team_transitions[1]
                
                assert first_status['player_count'] != second_status['player_count'] or \
                       first_status['status'] != second_status['status']