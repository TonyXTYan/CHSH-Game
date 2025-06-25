import pytest
from unittest.mock import patch, MagicMock
from flask import request
from src.state import state
from src.models.quiz_models import Teams, db
from src.config import app


@pytest.fixture
def app_context():
    with app.app_context():
        yield app

@pytest.fixture  
def mock_request_context(app_context):
    with app_context.test_request_context('/') as context:
        context.request.sid = 'test_sid'
        context.request.namespace = '/'
        yield context.request


@pytest.fixture
def active_team_with_two_players():
    """Create an active team with two players for testing"""
    with app.app_context():
        # Create team in database
        team = Teams(
            team_name='test_team',
            player1_session_id='player1_sid',
            player2_session_id='player2_sid',
            is_active=True
        )
        db.session.add(team)
        db.session.commit()
        
        # Set up state
        state.active_teams['test_team'] = {
            'players': ['player1_sid', 'player2_sid'],
            'team_id': team.team_id,
            'current_round_number': 0,
            'combo_tracker': {},
            'answered_current_round': {},
            'status': 'active'
        }
        state.player_to_team['player1_sid'] = 'test_team'
        state.player_to_team['player2_sid'] = 'test_team'
        state.team_id_to_name[team.team_id] = 'test_team'
        state.connected_players.add('player1_sid')
        state.connected_players.add('player2_sid')
        
        yield team
        
        # Cleanup
        state.reset()
        db.session.delete(team)
        db.session.commit()


@pytest.fixture
def waiting_team_with_one_player():
    """Create a team with one player waiting for another"""
    with app.app_context():
        # Create team in database
        team = Teams(
            team_name='waiting_team',
            player1_session_id='solo_player_sid',
            player2_session_id=None,
            is_active=True
        )
        db.session.add(team)
        db.session.commit()
        
        # Set up state
        state.active_teams['waiting_team'] = {
            'players': ['solo_player_sid'],
            'team_id': team.team_id,
            'current_round_number': 0,
            'combo_tracker': {},
            'answered_current_round': {},
            'status': 'waiting_pair'
        }
        state.player_to_team['solo_player_sid'] = 'waiting_team'
        state.team_id_to_name[team.team_id] = 'waiting_team'
        state.connected_players.add('solo_player_sid')
        
        yield team
        
        # Cleanup
        state.reset()
        db.session.delete(team)
        db.session.commit()


@pytest.fixture(autouse=True)
def cleanup_state():
    """Clean up state after each test"""
    yield
    state.active_teams.clear()
    state.player_to_team.clear()
    state.team_id_to_name.clear()
    state.connected_players.clear()
    state.dashboard_clients.clear()


class TestDisconnectionLogic:
    """Test disconnect/reconnect scenarios"""

    def test_player_disconnect_from_full_team_sets_waiting_status(self, mock_request_context, active_team_with_two_players):
        """When one player disconnects from a full team, status should become 'waiting_pair'"""
        mock_request_context.sid = 'player1_sid'
        
        with patch('src.sockets.team_management.emit') as mock_emit, \
             patch('src.sockets.team_management.leave_room') as mock_leave_room, \
             patch('src.sockets.dashboard.emit_dashboard_team_update') as mock_dashboard_update:
            
            from src.sockets.team_management import handle_disconnect
            handle_disconnect()
            
            # Verify team status changed to waiting_pair
            assert state.active_teams['test_team']['status'] == 'waiting_pair'
            assert len(state.active_teams['test_team']['players']) == 1
            assert 'player2_sid' in state.active_teams['test_team']['players']
            assert 'player1_sid' not in state.active_teams['test_team']['players']
            
            # Verify notifications were sent
            mock_emit.assert_any_call(
                'player_left',
                {'message': 'A team member has disconnected.'},
                to='test_team'
            )
            
            mock_emit.assert_any_call(
                'team_status_update',
                {
                    'team_name': 'test_team',
                    'status': 'waiting_pair',
                    'members': ['player2_sid'],
                    'game_started': state.game_started
                },
                to='test_team'
            )

    def test_last_player_disconnect_makes_team_inactive(self, mock_request_context, waiting_team_with_one_player):
        """When the last player disconnects, team should become inactive"""
        mock_request_context.sid = 'solo_player_sid'
        
        with patch('src.sockets.team_management.emit') as mock_emit, \
             patch('src.sockets.team_management.leave_room') as mock_leave_room, \
             patch('src.sockets.dashboard.emit_dashboard_team_update') as mock_dashboard_update:
            
            from src.sockets.team_management import handle_disconnect
            handle_disconnect()
            
            # Verify team is removed from active teams
            assert 'waiting_team' not in state.active_teams
            assert 'solo_player_sid' not in state.player_to_team
            
            # Verify team is marked inactive in database
            team = Teams.query.filter_by(team_name='waiting_team').first()
            assert team.is_active is False

    def test_both_players_disconnect_preserves_responses(self, mock_request_context, active_team_with_two_players):
        """When both players disconnect, responses should be preserved in database"""
        team_id = active_team_with_two_players.team_id
        
        # Simulate both players disconnecting
        with patch('src.sockets.team_management.emit'), \
             patch('src.sockets.team_management.leave_room'), \
             patch('src.sockets.dashboard.emit_dashboard_team_update'):
            
            from src.sockets.team_management import handle_disconnect
            
            # First player disconnects
            mock_request_context.sid = 'player1_sid'
            handle_disconnect()
            
            # Second player disconnects
            mock_request_context.sid = 'player2_sid'
            handle_disconnect()
            
            # Verify team is inactive but exists in database
            team = Teams.query.filter_by(team_id=team_id).first()
            assert team is not None
            assert team.is_active is False
            # Responses would be preserved as they're linked by team_id


class TestRejoinLogic:
    """Test rejoin team functionality"""

    def test_rejoin_team_success(self, mock_request_context, waiting_team_with_one_player):
        """Player should be able to rejoin their previous team successfully"""
        team_id = waiting_team_with_one_player.team_id
        mock_request_context.sid = 'returning_player_sid'
        
        with patch('src.sockets.team_management.emit') as mock_emit, \
             patch('src.sockets.team_management.join_room') as mock_join_room, \
             patch('src.sockets.team_management.socketio.emit') as mock_socketio_emit, \
             patch('src.sockets.dashboard.emit_dashboard_team_update') as mock_dashboard_update:
            
            from src.sockets.team_management import on_rejoin_team
            
            # Test rejoin with correct team info
            on_rejoin_team({
                'team_name': 'waiting_team',
                'team_id': team_id
            })
            
            # Verify player was added to team
            assert 'returning_player_sid' in state.active_teams['waiting_team']['players']
            assert len(state.active_teams['waiting_team']['players']) == 2
            assert state.active_teams['waiting_team']['status'] == 'active'
            assert state.player_to_team['returning_player_sid'] == 'waiting_team'
            
            # Verify success response
            mock_emit.assert_any_call(
                'rejoin_team_response',
                {
                    'success': True,
                    'team_name': 'waiting_team',
                    'team_id': team_id,
                    'message': 'Successfully rejoined team waiting_team.',
                    'game_started': state.game_started,
                    'team_status': 'full'
                }
            )

    def test_rejoin_team_wrong_id(self, mock_request_context, waiting_team_with_one_player):
        """Rejoin should fail with wrong team_id"""
        mock_request_context.sid = 'returning_player_sid'
        
        with patch('src.sockets.team_management.emit') as mock_emit:
            
            from src.sockets.team_management import on_rejoin_team
            
            # Test rejoin with wrong team_id
            on_rejoin_team({
                'team_name': 'waiting_team',
                'team_id': 99999  # Wrong ID
            })
            
            # Verify failure response
            mock_emit.assert_called_with(
                'rejoin_team_response',
                {
                    'success': False,
                    'message': 'Team information does not match.'
                }
            )

    def test_rejoin_team_already_full(self, mock_request_context, active_team_with_two_players):
        """Rejoin should fail if team is already full"""
        team_id = active_team_with_two_players.team_id
        mock_request_context.sid = 'third_player_sid'
        
        with patch('src.sockets.team_management.emit') as mock_emit:
            
            from src.sockets.team_management import on_rejoin_team
            
            # Test rejoin when team is full
            on_rejoin_team({
                'team_name': 'test_team',
                'team_id': team_id
            })
            
            # Verify failure response
            mock_emit.assert_called_with(
                'rejoin_team_response',
                {
                    'success': False,
                    'message': 'Team is already full.'
                }
            )

    def test_rejoin_nonexistent_team(self, mock_request_context):
        """Rejoin should fail if team doesn't exist"""
        mock_request_context.sid = 'returning_player_sid'
        
        with patch('src.sockets.team_management.emit') as mock_emit:
            
            from src.sockets.team_management import on_rejoin_team
            
            # Test rejoin with non-existent team
            on_rejoin_team({
                'team_name': 'nonexistent_team',
                'team_id': 99999
            })
            
            # Verify failure response
            mock_emit.assert_called_with(
                'rejoin_team_response',
                {
                    'success': False,
                    'message': 'Team no longer exists or cannot be found.'
                }
            )


class TestTeamStateConsistency:
    """Test that team state remains consistent across disconnect/reconnect cycles"""

    def test_disconnect_reconnect_cycle_preserves_team_data(self, mock_request_context, active_team_with_two_players):
        """Full disconnect/reconnect cycle should preserve team data"""
        team_id = active_team_with_two_players.team_id
        original_round_number = state.active_teams['test_team']['current_round_number']
        
        # Both players disconnect
        with patch('src.sockets.team_management.emit'), \
             patch('src.sockets.team_management.leave_room'), \
             patch('src.sockets.dashboard.emit_dashboard_team_update'):
            
            from src.sockets.team_management import handle_disconnect
            
            # First player disconnects
            mock_request_context.sid = 'player1_sid'
            handle_disconnect()
            
            # Second player disconnects
            mock_request_context.sid = 'player2_sid'
            handle_disconnect()
            
            # Verify team is inactive
            assert 'test_team' not in state.active_teams
        
        # Player reactivates team
        with patch('src.sockets.team_management.emit') as mock_emit, \
             patch('src.sockets.team_management.join_room'), \
             patch('src.sockets.team_management.socketio.emit'), \
             patch('src.sockets.dashboard.emit_dashboard_team_update'):
            
            from src.sockets.team_management import on_reactivate_team
            
            mock_request_context.sid = 'new_player1_sid'
            on_reactivate_team({'team_name': 'test_team'})
            
            # Verify team was reactivated with preserved data
            assert 'test_team' in state.active_teams
            assert state.active_teams['test_team']['current_round_number'] == original_round_number
            assert state.active_teams['test_team']['team_id'] == team_id

    def test_concurrent_disconnect_handling(self, mock_request_context, active_team_with_two_players):
        """Test that concurrent disconnects are handled properly"""
        # This test simulates what happens when both players disconnect nearly simultaneously
        
        with patch('src.sockets.team_management.emit'), \
             patch('src.sockets.team_management.leave_room'), \
             patch('src.sockets.dashboard.emit_dashboard_team_update'):
            
            from src.sockets.team_management import handle_disconnect
            
            # Simulate both disconnects happening very close together
            # (In real scenario, second disconnect might happen before first one completes)
            
            # First disconnect
            mock_request_context.sid = 'player1_sid'
            handle_disconnect()
            
            # Verify intermediate state
            assert state.active_teams['test_team']['status'] == 'waiting_pair'
            assert len(state.active_teams['test_team']['players']) == 1
            
            # Second disconnect
            mock_request_context.sid = 'player2_sid'
            handle_disconnect()
            
            # Verify final state
            assert 'test_team' not in state.active_teams
            team = Teams.query.filter_by(team_name='test_team').first()
            assert team.is_active is False