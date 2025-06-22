import pytest
from unittest.mock import patch, ANY, MagicMock
from flask import request
from src.config import app, socketio, db
from src.models.quiz_models import Teams
from src.state import state
import warnings
from typing import Dict, Any

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

@pytest.fixture
def inactive_team():
    with app.app_context():
        # Create an inactive team in the database
        team = Teams(team_name="test_team", is_active=False)
        db.session.add(team)
        db.session.commit()
        yield team
        # Cleanup
        db.session.delete(team)
        db.session.commit()

@pytest.fixture
def active_team():
    with app.app_context():
        team = Teams(team_name="active_team", is_active=True, player1_session_id="player1_sid")
        db.session.add(team)
        db.session.commit()
        # Set up state
        state.active_teams["active_team"] = {
            'players': ['player1_sid'],
            'team_id': team.team_id,
            'current_round_number': 0,
            'combo_tracker': {},
            'answered_current_round': {},
            'status': 'waiting_pair'
        }
        state.player_to_team['player1_sid'] = 'active_team'
        state.team_id_to_name[team.team_id] = 'active_team'
        yield team
        # Cleanup
        db.session.delete(team)
        db.session.commit()
        state.active_teams.clear()
        state.player_to_team.clear()
        state.team_id_to_name.clear()

@pytest.fixture
def full_team():
    with app.app_context():
        team = Teams(
            team_name="full_team",
            is_active=True,
            player1_session_id="player1_sid",
            player2_session_id="player2_sid"
        )
        db.session.add(team)
        db.session.commit()
        # Set up state
        state.active_teams["full_team"] = {
            'players': ['player1_sid', 'player2_sid'],
            'team_id': team.team_id,
            'current_round_number': 0,
            'combo_tracker': {},
            'answered_current_round': {},
            'status': 'active'
        }
        state.player_to_team['player1_sid'] = 'full_team'
        state.player_to_team['player2_sid'] = 'full_team'
        state.team_id_to_name[team.team_id] = 'full_team'
        yield team
        # Cleanup
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

def test_reactivate_team_success(mock_request_context, inactive_team):
    """Test successful team reactivation"""
    with patch('src.sockets.team_management.emit') as mock_emit, \
         patch('src.sockets.team_management.socketio.emit') as mock_socketio_emit, \
         patch('src.sockets.team_management.emit_dashboard_team_update') as mock_dashboard_update, \
         patch('src.sockets.team_management.join_room') as mock_join_room:
        
        # Initial state check
        assert "test_team" not in state.active_teams
        
        # Attempt to reactivate team
        from src.sockets.team_management import on_reactivate_team
        on_reactivate_team({'team_name': 'test_team'})
        
        # Verify team was updated in database
        team = Teams.query.filter_by(team_id=inactive_team.team_id).first()
        assert team.is_active == True
        assert team.player1_session_id == 'test_sid'
        
        # Verify state updates
        assert "test_team" in state.active_teams
        assert state.active_teams["test_team"]["team_id"] == inactive_team.team_id
        assert 'test_sid' in state.active_teams["test_team"]["players"]
        assert state.active_teams["test_team"]["status"] == "waiting_pair"
        assert state.player_to_team['test_sid'] == "test_team"
        
        # Verify event emissions
        mock_emit.assert_any_call(
            'team_created',
            {
                'team_name': 'test_team',
                'team_id': inactive_team.team_id,
                'message': 'Team reactivated successfully. Waiting for another player.',
                'game_started': state.game_started
            }
        )
        
        mock_socketio_emit.assert_any_call(
            'teams_updated',
            {
                'teams': ANY,
                'game_started': state.game_started
            }
        )
        
        # Verify dashboard update was called
        mock_dashboard_update.assert_called_once()

def test_reactivate_nonexistent_team(mock_request_context):
    """Test attempt to reactivate a team that doesn't exist"""
    with patch('src.sockets.team_management.emit') as mock_emit:
        from src.sockets.team_management import on_reactivate_team
        on_reactivate_team({'team_name': 'nonexistent_team'})
        
        mock_emit.assert_called_once_with(
            'error',
            {'message': 'Team not found or is already active'}
        )

def test_reactivate_team_name_conflict(mock_request_context, inactive_team):
    """Test attempt to reactivate a team when active team with same name exists"""
    # Set up an active team with the same name
    state.active_teams['test_team'] = {
        'players': ['other_sid'],
        'team_id': 999,
        'status': 'waiting_pair'
    }
    
    with patch('src.sockets.team_management.emit') as mock_emit:
        from src.sockets.team_management import on_reactivate_team
        on_reactivate_team({'team_name': 'test_team'})
        
        mock_emit.assert_called_once_with(
            'error',
            {'message': 'An active team with this name already exists'}
        )

def test_get_available_teams_list(app_context, active_team, inactive_team):
    """Test getting list of available teams"""
    from src.sockets.team_management import get_available_teams_list
    
    teams_list = get_available_teams_list()
    
    # Should find both active and inactive teams
    assert any(t['team_name'] == 'active_team' and t['is_active'] for t in teams_list)
    assert any(t['team_name'] == 'test_team' and not t['is_active'] for t in teams_list)

def test_get_team_members(app_context, active_team):
    """Test getting team members"""
    from src.sockets.team_management import get_team_members
    
    members = get_team_members("active_team")
    assert members == ['player1_sid']
    
    # Test nonexistent team
    members = get_team_members("nonexistent_team")
    assert members == []

def test_handle_connect(mock_request_context):
    """Test client connection handling"""
    with patch('src.sockets.team_management.emit') as mock_emit, \
         patch('src.sockets.team_management.emit_dashboard_full_update') as mock_dashboard_update:
        from src.sockets.team_management import handle_connect
        
        # Test regular player connection
        handle_connect()
        
        assert 'test_sid' in state.connected_players
        assert 'test_sid' not in state.dashboard_clients
        
        mock_emit.assert_called_once_with('connection_established', {
            'game_started': state.game_started,
            'available_teams': ANY
        })
        mock_dashboard_update.assert_called_once()

def test_create_team_success(mock_request_context):
    """Test successful team creation"""
    with patch('src.sockets.team_management.emit') as mock_emit, \
         patch('src.sockets.team_management.socketio.emit') as mock_socketio_emit, \
         patch('src.sockets.team_management.emit_dashboard_team_update') as mock_dashboard_update, \
         patch('src.sockets.team_management.join_room') as mock_join_room:
        
        from src.sockets.team_management import on_create_team
        on_create_team({'team_name': 'new_team'})
        
        # Verify team was created in database
        team = Teams.query.filter_by(team_name='new_team').first()
        assert team is not None
        assert team.is_active == True
        assert team.player1_session_id == 'test_sid'
        
        # Verify state updates
        assert 'new_team' in state.active_teams
        assert state.active_teams['new_team']['players'] == ['test_sid']
        assert state.active_teams['new_team']['status'] == 'waiting_pair'
        assert state.player_to_team['test_sid'] == 'new_team'
        
        # Verify event emissions
        mock_emit.assert_any_call(
            'team_created',
            {
                'team_name': 'new_team',
                'team_id': ANY,
                'message': 'Team created. Waiting for another player.',
                'game_started': state.game_started
            }
        )
        
        mock_socketio_emit.assert_called_once_with(
            'teams_updated',
            {
                'teams': ANY,
                'game_started': state.game_started
            }
        )
        
        mock_dashboard_update.assert_called_once()
        mock_join_room.assert_called_once_with('new_team', sid='test_sid')
        
        # Cleanup
        db.session.delete(team)
        db.session.commit()

def test_create_team_missing_name(mock_request_context):
    """Test team creation with missing team name"""
    with patch('src.sockets.team_management.emit') as mock_emit:
        from src.sockets.team_management import on_create_team
        on_create_team({})
        
        mock_emit.assert_called_once_with(
            'error',
            {'message': 'Team name is required'}
        )

def test_create_team_duplicate_name(mock_request_context, active_team):
    """Test team creation with duplicate name"""
    with patch('src.sockets.team_management.emit') as mock_emit:
        from src.sockets.team_management import on_create_team
        on_create_team({'team_name': 'active_team'})
        
        mock_emit.assert_called_once_with(
            'error',
            {'message': 'Team name already exists or is active'}
        )

def test_join_team_success(mock_request_context, active_team):
    """Test successful team join"""
    with patch('src.sockets.team_management.emit') as mock_emit, \
         patch('src.sockets.team_management.socketio.emit') as mock_socketio_emit, \
         patch('src.sockets.team_management.emit_dashboard_team_update') as mock_dashboard_update, \
         patch('src.sockets.team_management.join_room') as mock_join_room, \
         patch('src.sockets.team_management.start_new_round_for_pair') as mock_start_round:
        
        from src.sockets.team_management import on_join_team
        on_join_team({'team_name': 'active_team'})
        
        # Verify database updates
        # Using Session.get() instead of Query.get()
        team = db.session.get(Teams, active_team.team_id)
        assert team.player2_session_id == 'test_sid'
        
        # Verify state updates
        assert len(state.active_teams['active_team']['players']) == 2
        assert 'test_sid' in state.active_teams['active_team']['players']
        assert state.player_to_team['test_sid'] == 'active_team'
        assert state.active_teams['active_team']['status'] == 'active'
        
        # Verify event emissions
        mock_emit.assert_any_call(
            'team_joined',
            {
                'team_name': 'active_team',
                'message': 'You joined team active_team.',
                'game_started': state.game_started,
                'team_status': 'full'
            },
            to='test_sid'
        )
        
        mock_socketio_emit.assert_called_with(
            'teams_updated',
            {
                'teams': ANY,
                'game_started': state.game_started
            }
        )
        
        mock_dashboard_update.assert_called_once()
        mock_join_room.assert_called_once_with('active_team', sid='test_sid')

def test_join_nonexistent_team(mock_request_context):
    """Test joining a nonexistent team"""
    with patch('src.sockets.team_management.emit') as mock_emit:
        from src.sockets.team_management import on_join_team
        on_join_team({'team_name': 'nonexistent_team'})
        
        mock_emit.assert_called_once_with(
            'error',
            {'message': 'Team not found or invalid team name.'}
        )

def test_join_full_team(mock_request_context, active_team):
    """Test joining a team that is already full"""
    # Make the team full
    state.active_teams['active_team']['players'].append('player2_sid')
    
    with patch('src.sockets.team_management.emit') as mock_emit:
        from src.sockets.team_management import on_join_team
        on_join_team({'team_name': 'active_team'})
        
        mock_emit.assert_called_once_with(
            'error',
            {'message': 'Team is already full.'}
        )

def test_join_team_already_member(mock_request_context, active_team):
    """Test joining a team you're already in"""
    request.sid = 'player1_sid'  # Simulate being the first player
    
    with patch('src.sockets.team_management.emit') as mock_emit:
        from src.sockets.team_management import on_join_team
        on_join_team({'team_name': 'active_team'})
        
        mock_emit.assert_called_once_with(
            'error',
            {'message': 'You are already in this team.'}
        )

def test_handle_disconnect_dashboard_client(mock_request_context):
    """Test disconnection of a dashboard client"""
    state.dashboard_clients.add('test_sid')
    state.connected_players.add('test_sid')
    
    with patch('src.sockets.team_management.emit_dashboard_full_update') as mock_dashboard_update:
        from src.sockets.team_management import handle_disconnect
        handle_disconnect()
        
        assert 'test_sid' not in state.dashboard_clients
        assert 'test_sid' not in state.connected_players
        mock_dashboard_update.assert_called_once()

def test_handle_disconnect_team_member(mock_request_context, active_team):
    """Test disconnection of a team member"""
    request.sid = 'player1_sid'
    state.connected_players.add('player1_sid')
    
    with patch('src.sockets.team_management.emit') as mock_emit, \
         patch('src.sockets.team_management.socketio.emit') as mock_socketio_emit, \
         patch('src.sockets.team_management.emit_dashboard_team_update') as mock_dashboard_update, \
         patch('src.sockets.team_management.leave_room') as mock_leave_room:
        
        from src.sockets.team_management import handle_disconnect
        handle_disconnect()
        
        # Verify state updates
        assert 'player1_sid' not in state.connected_players
        
        # Team should be marked inactive since last player left
        team = Teams.query.filter_by(team_id=active_team.team_id).first()
        assert team.is_active == False
        assert team.player1_session_id is None
        assert 'active_team' not in state.active_teams
        assert active_team.team_id not in state.team_id_to_name
        
        mock_leave_room.assert_called_once_with('active_team', sid='player1_sid')
        mock_dashboard_update.assert_called_once()

def test_handle_disconnect_from_full_team(mock_request_context, full_team):
    """Test disconnection of one member from a full team"""
    request.sid = 'player1_sid'
    state.connected_players.add('player1_sid')
    
    with patch('src.sockets.team_management.emit') as mock_emit, \
         patch('src.sockets.team_management.socketio.emit') as mock_socketio_emit, \
         patch('src.sockets.team_management.emit_dashboard_team_update') as mock_dashboard_update, \
         patch('src.sockets.team_management.leave_room') as mock_leave_room:
        
        from src.sockets.team_management import handle_disconnect
        handle_disconnect()
        
        # Verify state updates
        assert 'player1_sid' not in state.connected_players
        assert len(state.active_teams['full_team']['players']) == 1
        assert state.active_teams['full_team']['status'] == 'waiting_pair'
        
        # Verify team in database
        team = Teams.query.filter_by(team_id=full_team.team_id).first()
        assert team.is_active == True
        assert team.player1_session_id is None
        assert team.player2_session_id == 'player2_sid'
        
        # Verify notifications
        mock_emit.assert_any_call(
            'player_left',
            {'message': 'A team member has disconnected.'},
            to='full_team'
        )
        
        mock_emit.assert_any_call(
            'team_status_update',
            {
                'team_name': 'full_team',
                'status': 'waiting_pair',
                'members': ['player2_sid'],
                'game_started': state.game_started
            },
            to='full_team'
        )
        
        mock_leave_room.assert_called_once_with('full_team', sid='player1_sid')
        mock_dashboard_update.assert_called_once()

def test_leave_team_success(mock_request_context, active_team):
    """Test successful team leave"""
    request.sid = 'player1_sid'
    
    with patch('src.sockets.team_management.emit') as mock_emit, \
         patch('src.sockets.team_management.socketio.emit') as mock_socketio_emit, \
         patch('src.sockets.team_management.emit_dashboard_team_update') as mock_dashboard_update, \
         patch('src.sockets.team_management.leave_room') as mock_leave_room:
        
        from src.sockets.team_management import on_leave_team
        on_leave_team({})
        
        # Team should be marked inactive since last player left
        team = Teams.query.filter_by(team_id=active_team.team_id).first()
        assert team.is_active == False
        assert team.player1_session_id is None
        assert 'active_team' not in state.active_teams
        assert active_team.team_id not in state.team_id_to_name
        assert 'player1_sid' not in state.player_to_team
        
        mock_emit.assert_any_call(
            'left_team_success',
            {'message': 'You have left the team.'},
            to='player1_sid'
        )
        
        mock_leave_room.assert_called_once_with('active_team', sid='player1_sid')
        mock_dashboard_update.assert_called_once()

def test_leave_team_not_in_team(mock_request_context):
    """Test leaving when not in a team"""
    with patch('src.sockets.team_management.emit') as mock_emit:
        from src.sockets.team_management import on_leave_team
        on_leave_team({})
        
        mock_emit.assert_called_once_with(
            'error',
            {'message': 'You are not in a team.'}
        )

def test_leave_full_team(mock_request_context, full_team):
    """Test one player leaving a full team"""
    request.sid = 'player1_sid'
    
    with patch('src.sockets.team_management.emit') as mock_emit, \
         patch('src.sockets.team_management.socketio.emit') as mock_socketio_emit, \
         patch('src.sockets.team_management.emit_dashboard_team_update') as mock_dashboard_update, \
         patch('src.sockets.team_management.leave_room') as mock_leave_room:
        
        from src.sockets.team_management import on_leave_team
        on_leave_team({})
        
        # Verify team updates
        team = Teams.query.filter_by(team_id=full_team.team_id).first()
        assert team.is_active == True
        assert team.player1_session_id is None
        assert team.player2_session_id == 'player2_sid'
        
        # Verify state updates
        assert len(state.active_teams['full_team']['players']) == 1
        assert state.active_teams['full_team']['status'] == 'waiting_pair'
        assert 'player1_sid' not in state.player_to_team
        
        # Verify notifications
        mock_emit.assert_any_call(
            'player_left',
            {'message': 'A team member has left.'},
            to='full_team'
        )
        
        mock_emit.assert_any_call(
            'team_status_update',
            {
                'team_name': 'full_team',
                'status': 'waiting_pair',
                'members': ['player2_sid'],
                'game_started': state.game_started
            },
            to='full_team'
        )
        
        mock_emit.assert_any_call(
            'left_team_success',
            {'message': 'You have left the team.'},
            to='player1_sid'
        )
        
        mock_leave_room.assert_called_once_with('full_team', sid='player1_sid')
        mock_dashboard_update.assert_called_once()
