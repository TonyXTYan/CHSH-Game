import eventlet
eventlet.monkey_patch()  # This must be at the very top

import pytest
import time
from flask_socketio import SocketIOTestClient
from wsgi import app
from src.config import socketio as server_socketio
from src.state import state
from src.models.quiz_models import Teams, PairQuestionRounds, ItemEnum, db

def _clear_state():
    """Helper to clear application state between tests"""
    state.active_teams.clear()
    state.player_to_team.clear()
    state.team_id_to_name.clear()
    state.dashboard_clients.clear()
    state.connected_players.clear()
    state.game_started = False
    state.game_paused = False

@pytest.fixture(autouse=True)
def clean_state():
    """Automatically clean state before each test"""
    _clear_state()
    yield
    _clear_state()

@pytest.fixture
def socket_client(app_context):
    """Create a test client for SocketIO"""
    client = SocketIOTestClient(app, server_socketio)
    print("\nTest client created")  # Debug output
    yield client
    print("\nDisconnecting test client")  # Debug output
    client.disconnect()

@pytest.fixture
def second_client(app_context):
    """Create a second test client for team interactions"""
    client = SocketIOTestClient(app, server_socketio)
    print("\nSecond test client created")
    yield client
    print("\nDisconnecting second test client")
    client.disconnect()

@pytest.fixture
def app_context():
    """Create application context"""
    with app.app_context():
        app.extensions['socketio'] = server_socketio
        with app.test_request_context():
            yield app

class TestPlayerInteraction:
    """Test class for player interaction scenarios"""

    def get_received_event(self, client, event_name):
        """Helper method to get a specific event from received messages"""
        messages = client.get_received()
        return next((msg for msg in messages if msg.get('name') == event_name), None)

    def verify_connection(self, client):
        """Helper method to verify client connection"""
        assert client.connected, "Client failed to connect to server"
        time.sleep(0.1)
        
        # Verify connection_established event
        msg = self.get_received_event(client, 'connection_established')
        assert msg is not None, "Did not receive connection_established event"
        data = msg.get('args', [{}])[0]
        assert 'game_started' in data, "connection_established missing game_started status"
        assert 'available_teams' in data, "connection_established missing available_teams list"
        return data

    def wait_for_event(self, client, event_name, timeout=1.0):
        """Helper method to wait for and get a specific event"""
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            eventlet.sleep(0.1)  # Use eventlet sleep instead of time.sleep
            event = self.get_received_event(client, event_name)
            if event is not None:
                return event
        return None

    @pytest.mark.integration
    def test_player_connection(self, app_context, socket_client):
        """Test that a player can successfully connect to the game server"""
        self.verify_connection(socket_client)

    @pytest.mark.integration
    def test_team_creation(self, app_context, socket_client):
        """Test successful team creation"""
        conn_data = self.verify_connection(socket_client)
        socket_client.get_received()  # Clear initial messages
        
        # Create team
        socket_client.emit('create_team', {'team_name': 'TestTeam'})
        eventlet.sleep(0.2)  # Use eventlet sleep instead of time.sleep

        # Get all messages since team creation
        messages = socket_client.get_received()
        
        # Verify team_created event
        team_created = next((msg for msg in messages if msg.get('name') == 'team_created'), None)
        assert team_created is not None, "Did not receive team_created event"
        team_data = team_created.get('args', [{}])[0]
        assert team_data.get('team_name') == 'TestTeam', "Incorrect team name"
        assert 'team_id' in team_data, "team_created missing team_id"
        assert 'game_started' in team_data, "team_created missing game_started status"

        # Verify teams_updated event was received
        teams_updated = next((msg for msg in messages if msg.get('name') == 'teams_updated'), None)
        assert teams_updated is not None, "Did not receive teams_updated event"
        assert 'teams' in teams_updated.get('args', [{}])[0], "teams_updated missing teams list"

    @pytest.mark.integration
    def test_team_joining(self, app_context, socket_client, second_client):
        """Test successful team joining"""
        # Setup and create team with first client
        self.verify_connection(socket_client)
        socket_client.emit('create_team', {'team_name': 'TeamToJoin'})
        eventlet.sleep(0.2)  # Use eventlet sleep
        socket_client.get_received()  # Clear messages

        # Connect second client and join team
        self.verify_connection(second_client)
        second_client.get_received()  # Clear connection messages
        
        second_client.emit('join_team', {'team_name': 'TeamToJoin'})
        eventlet.sleep(0.2)  # Use eventlet sleep

        # Get all messages since team join
        p2_messages = second_client.get_received()
        p1_messages = socket_client.get_received()

        # Verify team_joined event for second client
        team_joined = next((msg for msg in p2_messages if msg.get('name') == 'team_joined'), None)
        assert team_joined is not None, "Did not receive team_joined event"
        join_data = team_joined.get('args', [{}])[0]
        assert join_data.get('team_name') == 'TeamToJoin', "Incorrect team name"
        assert join_data.get('team_status') == 'full', "Incorrect team status in join event"

        # Verify team_status_update for both clients
        status_p1 = next((msg for msg in p1_messages if msg.get('name') == 'team_status_update'), None)
        status_p2 = next((msg for msg in p2_messages if msg.get('name') == 'team_status_update'), None)

        assert status_p1 is not None, "First client did not receive team_status_update"
        assert status_p2 is not None, "Second client did not receive team_status_update"
        
        assert status_p1.get('args', [{}])[0].get('status') == 'full', "Incorrect team status for first client"
        assert status_p2.get('args', [{}])[0].get('status') == 'full', "Incorrect team status for second client"

    @pytest.mark.integration
    def test_answer_submission(self, app_context, socket_client, second_client):
        """Test answer submission by team members"""
        # Create and join team
        self.verify_connection(socket_client)
        socket_client.emit('create_team', {'team_name': 'AnswerTeam'})
        team_created = self.wait_for_event(socket_client, 'team_created')
        team_id = team_created.get('args', [{}])[0].get('team_id')
        socket_client.get_received()

        self.verify_connection(second_client)
        second_client.emit('join_team', {'team_name': 'AnswerTeam'})
        eventlet.sleep(0.2)
        second_client.get_received()

        # Turn on game state
        state.game_started = True

        # Create a test round in the database
        test_round = PairQuestionRounds(
            team_id=team_id,
            round_number_for_team=1,
            player1_item=ItemEnum.X,
            player2_item=ItemEnum.Y
        )
        db.session.add(test_round)
        db.session.commit()
        
        # Set up current round data in state
        team_info = state.active_teams.get('AnswerTeam')
        assert team_info is not None, "Team was not created properly"
        team_info['current_db_round_id'] = test_round.round_id
        team_info['current_round_number'] = 1

        # Submit answer
        socket_client.emit('submit_answer', {
            'round_id': test_round.round_id,
            'item': 'X',  # Use valid ItemEnum value
            'answer': True
        })
        eventlet.sleep(0.2)  # Use eventlet sleep
        
        # Get all messages since answer submission
        messages = socket_client.get_received()
        
        # Verify answer_confirmed event
        answer_confirmed = next((msg for msg in messages if msg.get('name') == 'answer_confirmed'), None)
        assert answer_confirmed is not None, "Did not receive answer_confirmed event"
        confirm_data = answer_confirmed.get('args', [{}])[0]
        assert 'message' in confirm_data, "answer_confirmed missing message"
