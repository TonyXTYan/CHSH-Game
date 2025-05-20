import pytest
from unittest.mock import patch, MagicMock, ANY
from src.sockets.team_management import on_create_team, on_join_team
from src.sockets.dashboard import on_dashboard_join, on_start_game
from src.sockets.game import on_submit_answer
from src.state import state
from wsgi import app
from src.config import socketio

@pytest.fixture
def app_context():
    with app.app_context():
        app.extensions['socketio'] = socketio
        yield app

@pytest.fixture
def mock_request_context(app_context):
    with app_context.test_request_context('/') as context:
        # Configure the request for SocketIO
        context.request.sid = 'test_sid'
        context.request.namespace = '/'
        yield context.request

@pytest.fixture
def mock_db_session():
    """Mock database session"""
    mock_session = MagicMock()
    mock_session.commit = MagicMock()
    return mock_session

@pytest.fixture
def mock_teams(mock_db_session):
    """Mock Teams model"""
    with patch('src.sockets.team_management.Teams') as mock_teams_cls:
        class MockTeam:
            def __init__(self, name=None):
                self.team_name = name
                self.team_id = 1
                self.is_active = True

        mock_teams_cls.__call__ = MagicMock(side_effect=MockTeam)
        mock_teams_cls.query = MagicMock()
        mock_teams_cls.query.filter_by.return_value.first.side_effect = [None, None]
        mock_teams_cls.query.get.return_value = None

        with patch('src.sockets.team_management.db') as mock_db:
            mock_db.session = mock_db_session
            yield mock_teams_cls

@pytest.fixture(autouse=True)
def cleanup_state():
    """Clean up state after each test"""
    yield
    state.player_to_team.clear()
    state.active_teams.clear()
    state.dashboard_clients.clear()
    state.game_started = False
    state.game_paused = False

@pytest.fixture
def mock_active_team(mock_db):
    """Create and return a mock team object"""
    team = MagicMock()
    team.team_id = 1
    team.team_name = "Test Team"
    team.is_active = True
    mock_db.session.add = MagicMock()
    mock_db.session.commit = MagicMock()
    mock_db.session.query = MagicMock()
    mock_db.session.query.return_value.filter_by.return_value.first.return_value = team
    return team

def test_complete_player_interaction_flow(mock_app, mock_socketio, mock_state, mock_db_session, mock_request_context, mock_teams):
    """
    Test a complete interaction flow:
    1. P1 connects and creates team
    2. P2 connects and joins team
    3. Dashboard starts game
    4. Players submit answers
    """
    # Setup mock contexts for different clients
    p1_request = MagicMock()
    p1_request.sid = "player1_sid"
    p2_request = MagicMock()
    p2_request.sid = "player2_sid"
    dashboard_request = MagicMock()
    dashboard_request.sid = "dashboard_sid"

    # Create mock team for later lookups
    team = MagicMock()
    team.team_id = 1
    team.team_name = "Test Team"
    team.player1_session_id = "player1_sid"
    
    # Mock socket emit and room operations
    with patch('src.sockets.team_management.emit') as mock_team_emit, \
         patch('src.sockets.dashboard.emit') as mock_dash_emit, \
         patch('src.sockets.game.emit') as mock_game_emit, \
         patch('src.sockets.team_management.socketio.emit') as mock_team_socketio_emit, \
         patch('src.sockets.dashboard.socketio.emit') as mock_dash_socketio_emit, \
         patch('src.sockets.game.socketio.emit') as mock_game_socketio_emit, \
         patch('src.sockets.team_management.join_room') as mock_join_room, \
         patch('src.sockets.team_management.leave_room') as mock_leave_room, \
         patch('src.sockets.team_management.Teams') as mock_teams_cls, \
         patch('flask.request', p1_request):

        # Set up mock Teams behavior
        filter_result = MagicMock()
        filter_result.first = MagicMock(side_effect=[None, team])  # First call returns None, second call returns team
        mock_teams_cls.query.filter_by.return_value = filter_result
        mock_teams_cls.query.get.return_value = team

        # Step 1: Player 1 creates team
        team_data = {'team_name': 'Test Team'}
        on_create_team(team_data)

        # Verify team creation events
        mock_team_emit.assert_any_call('team_created', {
            'team_name': 'Test Team',
            'team_id': ANY,
            'message': 'Team created. Waiting for another player.',
            'game_started': False
        })

        # Step 2: Player 2 joins team
        with patch('flask.request', p2_request):
            on_join_team(team_data)

            # Verify team join events
            mock_team_emit.assert_any_call('team_joined', {
                'team_name': 'Test Team',
                'message': ANY,
                'game_started': False,
                'team_status': 'full'
            }, room='player2_sid')

        # Step 3: Dashboard joins and starts game
        with patch('flask.request', dashboard_request):
            # Add dashboard client to state
            state.dashboard_clients.add('dashboard_sid')
            
            # Start game
            on_start_game()

            # Verify game start events
            mock_dash_socketio_emit.assert_any_call('game_start', 
                {'game_started': True}, 
                room='Test Team')

        # Step 4: Players submit answers
        # First player submits answer
        with patch('flask.request', p1_request):
            answer_data = {
                'round_id': 1,
                'item': 'A',
                'answer': True
            }
            on_submit_answer(answer_data)

        # Second player submits answer
        with patch('flask.request', p2_request):
            answer_data = {
                'round_id': 1,
                'item': 'B',
                'answer': False
            }
            on_submit_answer(answer_data)

        # Verify round completion events
        mock_game_socketio_emit.assert_any_call('round_complete', 
            {
                'team_name': 'Test Team',
                'round_number': ANY
            },
            room='Test Team')

        # Verify final game state
        assert state.game_started == True
        assert 'Test Team' in state.active_teams
        assert len(state.active_teams['Test Team']['players']) == 2
        assert state.player_to_team['player1_sid'] == 'Test Team'
        assert state.player_to_team['player2_sid'] == 'Test Team'
        assert 'dashboard_sid' in state.dashboard_clients

def test_player_interaction_error_cases(mock_app, mock_socketio, mock_state, mock_db_session, mock_request_context, mock_teams):
    """
    Test error cases in the player interaction flow:
    1. Join non-existent team
    2. Create duplicate team
    3. Join full team
    4. Submit answer without being in team
    """
    p1_request = MagicMock()
    p1_request.sid = "player1_sid"

    with patch('src.sockets.team_management.emit') as mock_team_emit, \
         patch('src.sockets.game.emit') as mock_game_emit, \
         patch('flask.request', p1_request):

        # Try joining non-existent team
        on_join_team({'team_name': 'Non Existent Team'})
        mock_team_emit.assert_any_call('error', 
            {'message': 'Team not found or invalid team name.'})

        # Create a team
        on_create_team({'team_name': 'Test Team'})

        # Try creating same team again
        on_create_team({'team_name': 'Test Team'})
        mock_team_emit.assert_any_call('error', 
            {'message': 'Team name already exists or is active'})

        # Try submitting answer without being in active game
        answer_data = {
            'round_id': 1,
            'item': 'A',
            'answer': True
        }
        on_submit_answer(answer_data)
        mock_game_emit.assert_any_call('error', 
            {'message': 'Team not valid or other player missing.'})
