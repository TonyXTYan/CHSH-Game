import eventlet
eventlet.monkey_patch()  # This must be at the very top

import pytest
import time
import logging
from flask_socketio import SocketIOTestClient
from src.config import app, socketio as server_socketio
from src.state import state
from src.models.quiz_models import (
    Teams,
    PairQuestionRounds,
    ItemEnum,
    Answers,
    db
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)

def reset_application_state():
    """Reset the entire application state for clean tests"""
    try:
        with app.app_context():
            logger.info("[STATE RESET] Clearing application state")
            
            # Clear database
            Answers.query.delete()
            PairQuestionRounds.query.delete()
            Teams.query.delete()
            db.session.commit()
            
            # Reset in-memory state
            state.reset()
            
            logger.info("[STATE RESET] Application state cleared successfully")
    except Exception as e:
        logger.error(f"[STATE RESET] Error clearing state: {str(e)}")
        raise

@pytest.fixture(autouse=True)
def setup_and_cleanup():
    """Setup and cleanup for each test"""
    logger.info("\n[TEST SETUP] Resetting application state...")
    reset_application_state()
    yield
    logger.info("\n[TEST CLEANUP] Final state cleanup...")
    reset_application_state()

@pytest.fixture
def socket_client(app_context):
    """Create a test client for SocketIO with proper cleanup"""
    client = None
    try:
        logger.info("\n[CLIENT] Creating test client...")
        client = SocketIOTestClient(app, server_socketio)
        logger.info("[CLIENT] Test client created")
        yield client
    finally:
        if client and client.connected:
            logger.info("[CLIENT] Disconnecting test client...")
            try:
                client.disconnect()
                logger.info("[CLIENT] Test client disconnected")
            except Exception as e:
                logger.error(f"[CLIENT] Error disconnecting client: {str(e)}")

@pytest.fixture
def second_client(app_context):
    """Create a second test client for team interactions with proper cleanup"""
    client = None
    try:
        logger.info("\n[CLIENT] Creating second test client...")
        client = SocketIOTestClient(app, server_socketio)
        logger.info("[CLIENT] Second test client created")
        yield client
    finally:
        if client and client.connected:
            logger.info("[CLIENT] Disconnecting second test client...")
            try:
                client.disconnect()
                logger.info("[CLIENT] Second test client disconnected")
            except Exception as e:
                logger.error(f"[CLIENT] Error disconnecting second client: {str(e)}")

@pytest.fixture(scope="session")
def base_app_context():
    """Create base application context for the test session"""
    with app.app_context():
        app.extensions['socketio'] = server_socketio
        
        # Initialize database
        logger.info("\n[DB INIT] Initializing database...")
        db.drop_all()
        db.create_all()
        logger.info("[DB INIT] Database initialized")
        
        yield app
        
        # Cleanup at end of session
        logger.info("\n[DB CLEANUP] Cleaning up database...")
        db.session.remove()
        db.drop_all()
        logger.info("[DB CLEANUP] Database cleaned up")

@pytest.fixture
def app_context(base_app_context):
    """Create a fresh database transaction for each test"""
    # Start a nested transaction
    connection = db.engine.connect()
    transaction = connection.begin()
    
    # Configure the session with the connection
    db.session.configure(bind=connection)
    
    logger.info("\n[TEST TRANS] Starting test transaction")
    
    yield app
    
    # Rollback the transaction
    logger.info("[TEST TRANS] Rolling back test transaction")
    db.session.remove()
    transaction.rollback()
    connection.close()

class TestPlayerInteraction:
    """Test class for player interaction scenarios"""

    def get_received_event(self, client, event_name, messages=None):
        """Helper method to get a specific event from received messages"""
        if messages is None:
            messages = client.get_received()
        return next((msg for msg in messages if msg.get('name') == event_name), None)

    def verify_connection(self, client):
        """Helper method to verify client connection"""
        assert client.connected, "Client failed to connect to server"
        time.sleep(0.1)
        
        # Get received messages
        messages = client.get_received()
        
        # Verify connection_established event
        msg = next((msg for msg in messages if msg.get('name') == 'connection_established'), None)
        assert msg is not None, "Did not receive connection_established event"
        data = msg.get('args', [{}])[0]
        assert 'game_started' in data, "connection_established missing game_started status"
        assert 'available_teams' in data, "connection_established missing available_teams list"
        return data

    def wait_for_event(self, client, event_name, timeout=1.0):
        """Helper method to wait for and get a specific event"""
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            eventlet.sleep(0.1)  # type: ignore
            event = self.get_received_event(client, event_name)
            if event is not None:
                return event
        return None

    def setup_and_verify_round(self, team_name, team_id, round_num, socket_client, second_client):
        """Helper method to set up and verify a game round"""
        try:
            test_round = PairQuestionRounds(
                team_id=team_id,
                round_number_for_team=round_num,
                player1_item=ItemEnum.X if round_num % 2 == 0 else ItemEnum.Y,
                player2_item=ItemEnum.Y if round_num % 2 == 0 else ItemEnum.X
            )
            db.session.add(test_round)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            # Check if round already exists
            existing_round = PairQuestionRounds.query.filter_by(
                team_id=team_id, 
                round_number_for_team=round_num
            ).first()
            if existing_round:
                test_round = existing_round
            else:
                # Create with a more unique round number  
                unique_round_num = round_num + (team_id * 1000)
                test_round = PairQuestionRounds(
                    team_id=team_id,
                    round_number_for_team=unique_round_num,
                    player1_item=ItemEnum.X if round_num % 2 == 0 else ItemEnum.Y,
                    player2_item=ItemEnum.Y if round_num % 2 == 0 else ItemEnum.X
                )
                db.session.add(test_round)
                db.session.commit()

        # Update team state
        team_info = state.active_teams.get(team_name)
        if team_info:
            team_info['current_db_round_id'] = test_round.round_id
            team_info['current_round_number'] = round_num

        # Submit answers
            socket_client.emit('submit_answer', {
                'round_id': test_round.round_id,
                'item': 'X' if round_num % 2 == 0 else 'Y',
                'answer': True
            })
            second_client.emit('submit_answer', {
                'round_id': test_round.round_id,
                'item': 'Y' if round_num % 2 == 0 else 'X',
                'answer': False
            })
            eventlet.sleep(0.2)

            # Verify answer confirmations
            return (
                self.wait_for_event(socket_client, 'answer_confirmed'),
                self.wait_for_event(second_client, 'answer_confirmed')
            )

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

    @pytest.mark.integration
    def test_leave_team(self, app_context, socket_client):
        """Test that a player can successfully leave a team"""
        # Create and join team first
        self.verify_connection(socket_client)
        socket_client.emit('create_team', {'team_name': 'LeaveTeam'})
        self.wait_for_event(socket_client, 'team_created')
        socket_client.get_received()  # Clear messages

        # Leave team
        socket_client.emit('leave_team', {})  # Socket event requires data object
        eventlet.sleep(0.2)

        # Get messages after leaving
        messages = socket_client.get_received()
        
        # Verify left_team_success event
        left_team = next((msg for msg in messages if msg.get('name') == 'left_team_success'), None)
        assert left_team is not None, "Did not receive left_team_success event"
        assert 'message' in left_team.get('args', [{}])[0], "left_team_success missing message"

        # Verify teams_updated event
        teams_updated = next((msg for msg in messages if msg.get('name') == 'teams_updated'), None)
        assert teams_updated is not None, "Did not receive teams_updated event"

    @pytest.mark.integration
    def test_multiple_rounds(self, app_context, socket_client, second_client):
        """Test multiple rounds of question answering"""
        # Set up team
        self.verify_connection(socket_client)
        socket_client.emit('create_team', {'team_name': 'MultiRoundTeam'})
        team_created = self.wait_for_event(socket_client, 'team_created')
        team_id = team_created.get('args', [{}])[0].get('team_id')
        socket_client.get_received()

        self.verify_connection(second_client)
        second_client.emit('join_team', {'team_name': 'MultiRoundTeam'})
        eventlet.sleep(0.2)
        second_client.get_received()

        # Start game
        state.game_started = True

        # Clean up any existing rounds for this team and commit separately
        try:
            PairQuestionRounds.query.filter_by(team_id=team_id).delete()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.warning(f"Warning: Cleanup failed: {e}")

        # Also update the team's state for clean test start
        team_info = state.active_teams.get('MultiRoundTeam')
        if team_info:
            team_info['current_round_number'] = 0
            team_info['combo_tracker'] = {}
            team_info['answered_current_round'] = {}

        # Simulate 3 rounds with better error handling
        for round_num in range(1, 4):
            try:
                p1_confirm, p2_confirm = self.setup_and_verify_round(
                    'MultiRoundTeam', team_id, round_num, socket_client, second_client
                )
            except Exception as e:
                db.session.rollback()
                # Create unique test round manually
                test_round = PairQuestionRounds(
                    team_id=team_id,
                    round_number_for_team=round_num,
                    player1_item=ItemEnum.X if round_num % 2 == 0 else ItemEnum.Y,
                    player2_item=ItemEnum.Y if round_num % 2 == 0 else ItemEnum.X
                )
                db.session.add(test_round)
                db.session.commit()
                
                team_info['current_db_round_id'] = test_round.round_id
                team_info['current_round_number'] = round_num
                
                # Submit answers directly
                socket_client.emit('submit_answer', {
                    'round_id': test_round.round_id,
                    'item': 'X' if round_num % 2 == 0 else 'Y',
                    'answer': True
                })
                second_client.emit('submit_answer', {
                    'round_id': test_round.round_id,
                    'item': 'Y' if round_num % 2 == 0 else 'X',
                    'answer': False
                })
                eventlet.sleep(0.2)
                
                p1_confirm = self.wait_for_event(socket_client, 'answer_confirmed')
                p2_confirm = self.wait_for_event(second_client, 'answer_confirmed')
            assert p1_confirm is not None, f"Player 1 did not receive answer confirmation for round {round_num}"
            assert p2_confirm is not None, f"Player 2 did not receive answer confirmation for round {round_num}"
            
            # Verify answer content
            p1_data = p1_confirm.get('args', [{}])[0]
            p2_data = p2_confirm.get('args', [{}])[0]
            assert 'message' in p1_data, f"Round {round_num}: Player 1 answer confirmation missing message"
            assert 'message' in p2_data, f"Round {round_num}: Player 2 answer confirmation missing message"

    @pytest.mark.integration
    def test_game_pause_resume(self, app_context, socket_client):
        """Test game pause/resume behavior"""
        # Set up team
        self.verify_connection(socket_client)
        socket_client.emit('create_team', {'team_name': 'PauseTeam'})
        team_created = self.wait_for_event(socket_client, 'team_created')
        socket_client.get_received()

        # Start game
        state.game_started = True
        
        # Pause game
        state.game_paused = True
        server_socketio.emit('game_paused')
        eventlet.sleep(0.2)

        # Verify pause event received
        pause_event = self.wait_for_event(socket_client, 'game_paused')
        assert pause_event is not None, "Did not receive game_paused event"

        # Resume game
        state.game_paused = False
        server_socketio.emit('game_resumed')
        eventlet.sleep(0.2)

        # Verify resume event received
        resume_event = self.wait_for_event(socket_client, 'game_resumed')
        assert resume_event is not None, "Did not receive game_resumed event"

    @pytest.mark.integration
    def test_error_cases(self, app_context, socket_client, second_client):
        """Test various error cases in team management"""
        self.verify_connection(socket_client)
        self.verify_connection(second_client)

        # Test creating team with empty name
        socket_client.emit('create_team', {'team_name': ''})
        error_event = self.wait_for_event(socket_client, 'error')
        assert error_event is not None, "Did not receive error for empty team name"

        # Test creating team with valid name
        socket_client.emit('create_team', {'team_name': 'ErrorTeam'})
        self.wait_for_event(socket_client, 'team_created')
        socket_client.get_received()

        # Test creating duplicate team
        second_client.emit('create_team', {'team_name': 'ErrorTeam'})
        error_event = self.wait_for_event(second_client, 'error')
        assert error_event is not None, "Did not receive error for duplicate team name"

        # Test joining non-existent team
        second_client.emit('join_team', {'team_name': 'NonExistentTeam'})
        error_event = self.wait_for_event(second_client, 'error')
        assert error_event is not None, "Did not receive error for non-existent team"

        # Test submitting answer without being in a team
        second_client.emit('submit_answer', {
            'round_id': 999,
            'item': 'X',
            'answer': True
        })
        error_event = self.wait_for_event(second_client, 'error')
        assert error_event is not None, "Did not receive error for answer without team"

    @pytest.mark.integration
    def test_full_game_flow(self, app_context, socket_client, second_client):
        """Test a complete game flow including team creation, joining, and multiple rounds with scoring"""
        # Setup phase
        self.verify_connection(socket_client)
        socket_client.emit('create_team', {'team_name': 'GameFlowTeam'})
        team_created = self.wait_for_event(socket_client, 'team_created')
        team_id = team_created.get('args', [{}])[0].get('team_id')
        socket_client.get_received()

        self.verify_connection(second_client)
        second_client.emit('join_team', {'team_name': 'GameFlowTeam'})
        join_event = self.wait_for_event(second_client, 'team_joined')
        assert join_event is not None, "Second player failed to join team"
        second_client.get_received()

        # Start game
        state.game_started = True
        
        # Clean up any existing rounds with better error handling
        try:
            PairQuestionRounds.query.filter_by(team_id=team_id).delete()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.warning(f"Warning: Cleanup failed: {e}")

        # Initialize team state
        team_info = state.active_teams.get('GameFlowTeam')
        assert team_info is not None, "Team state not found"
        team_info['current_round_number'] = 0
        team_info['combo_tracker'] = {}
        team_info['answered_current_round'] = {}

        # Play multiple rounds with different answer combinations
        test_scenarios = [
            # (p1_answer, p2_answer, expected_outcome)
            (True, True, "Both True"),
            (False, False, "Both False"),
            (True, False, "Mixed"),
            (False, True, "Mixed")
        ]

        for round_num, (p1_answer, p2_answer, scenario) in enumerate(test_scenarios, 1):
            # Set up round with error handling for unique constraint
            try:
                test_round = PairQuestionRounds(
                    team_id=team_id,
                    round_number_for_team=round_num,
                    player1_item=ItemEnum.X,
                    player2_item=ItemEnum.Y
                )
                db.session.add(test_round)
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                # Find the existing round or skip if there's a constraint issue
                existing_round = PairQuestionRounds.query.filter_by(
                    team_id=team_id, 
                    round_number_for_team=round_num
                ).first()
                if existing_round:
                    test_round = existing_round
                else:
                    # Create with a unique round number if needed
                    unique_round_num = round_num + 1000  # Make it unique
                    test_round = PairQuestionRounds(
                        team_id=team_id,
                        round_number_for_team=unique_round_num,
                        player1_item=ItemEnum.X,
                        player2_item=ItemEnum.Y
                    )
                    db.session.add(test_round)
                    db.session.commit()

            team_info['current_db_round_id'] = test_round.round_id
            team_info['current_round_number'] = round_num

            # Submit answers
            socket_client.emit('submit_answer', {
                'round_id': test_round.round_id,
                'item': 'X',
                'answer': p1_answer
            })
            second_client.emit('submit_answer', {
                'round_id': test_round.round_id,
                'item': 'Y',
                'answer': p2_answer
            })
            eventlet.sleep(0.2)

            # Verify answer confirmations
            p1_confirm = self.wait_for_event(socket_client, 'answer_confirmed')
            p2_confirm = self.wait_for_event(second_client, 'answer_confirmed')

            assert p1_confirm is not None, f"Round {round_num}: Player 1 answer not confirmed"
            assert p2_confirm is not None, f"Round {round_num}: Player 2 answer not confirmed"

            # Verify round completion
            completed_round = PairQuestionRounds.query.get(test_round.round_id)
            assert completed_round is not None, f"Round {round_num} not found in database"
            assert completed_round.p1_answered_at is not None, f"Round {round_num}: Player 1 answer time not recorded"
            assert completed_round.p2_answered_at is not None, f"Round {round_num}: Player 2 answer time not recorded"

            # Clear received messages for next round
            socket_client.get_received()
            second_client.get_received()

        # Verify final game state
        with app.app_context():
            completed_rounds = PairQuestionRounds.query.filter_by(team_id=team_id).count()
            assert completed_rounds >= len(test_scenarios), f"Expected at least {len(test_scenarios)} rounds, got {completed_rounds}"

    @pytest.mark.integration
    def test_team_disconnects_dashboard_reflects(self, app_context, socket_client, second_client):
        """Two players form a team, one disconnects, dashboard reflects 'waiting_pair', second disconnects, team becomes inactive."""
        # Create dashboard client
        dashboard_client = SocketIOTestClient(app, server_socketio)
        dashboard_client.emit('dashboard_join')
        eventlet.sleep(0.2)
        dashboard_client.get_received()
        
        # Enable teams streaming
        dashboard_client.emit('set_teams_streaming', {'enabled': True})
        eventlet.sleep(0.1)
        dashboard_client.get_received()
        
        # Request teams update after enabling streaming
        dashboard_client.emit('request_teams_update')
        eventlet.sleep(0.1)
        dashboard_client.get_received()

        # Player 1 creates team
        self.verify_connection(socket_client)
        socket_client.emit('create_team', {'team_name': 'DisconnectTeam'})
        team_created = self.wait_for_event(socket_client, 'team_created')
        team_id = team_created.get('args', [{}])[0].get('team_id')
        socket_client.get_received()

        # Player 2 joins team
        self.verify_connection(second_client)
        second_client.emit('join_team', {'team_name': 'DisconnectTeam'})
        self.wait_for_event(second_client, 'team_joined')
        second_client.get_received()

        # Dashboard should see team as active and full
        found = self.check_dashboard_team_status(dashboard_client, 'DisconnectTeam', 'active')
        assert found, "Dashboard did not see team as active after both joined"

        # Player 2 disconnects
        self.simulate_disconnect(second_client)
        eventlet.sleep(0.3)  # Give time for disconnect processing
        
        # FIXED: Use helper method to check status with throttling support
        found = self.check_dashboard_team_status(dashboard_client, 'DisconnectTeam', 'waiting_pair')
        assert found, "Dashboard did not see team as waiting_pair after one disconnects"

        # Player 1 disconnects
        self.simulate_disconnect(socket_client)
        eventlet.sleep(0.3)  # Give time for disconnect processing
        
        # FIXED: Use helper method to check status with throttling support
        found = self.check_dashboard_team_status(dashboard_client, 'DisconnectTeam', 'inactive')
        assert found, "Dashboard did not see team as inactive after both disconnect"
        dashboard_client.disconnect()

    @pytest.mark.integration
    def test_team_reactivation_dashboard_reflects(self, app_context, socket_client, second_client):
        """Two players form a team, both disconnect, one reconnects (reactivates team), dashboard reflects this."""
        dashboard_client = SocketIOTestClient(app, server_socketio)
        dashboard_client.emit('dashboard_join')
        eventlet.sleep(0.2)
        dashboard_client.get_received()
        
        # Enable teams streaming
        dashboard_client.emit('set_teams_streaming', {'enabled': True})
        eventlet.sleep(0.1)
        dashboard_client.get_received()
        
        # Request teams update after enabling streaming
        dashboard_client.emit('request_teams_update')
        eventlet.sleep(0.1)
        dashboard_client.get_received()

        # Player 1 creates team
        self.verify_connection(socket_client)
        socket_client.emit('create_team', {'team_name': 'ReactivateTeam'})
        team_created = self.wait_for_event(socket_client, 'team_created')
        team_id = team_created.get('args', [{}])[0].get('team_id')
        socket_client.get_received()

        # Player 2 joins team
        self.verify_connection(second_client)
        second_client.emit('join_team', {'team_name': 'ReactivateTeam'})
        self.wait_for_event(second_client, 'team_joined')
        second_client.get_received()

        # Both disconnect
        self.simulate_disconnect(second_client)
        self.simulate_disconnect(socket_client)
        eventlet.sleep(0.2)
        dashboard_client.get_received()

        # Player 1 reconnects and reactivates team
        new_client = SocketIOTestClient(app, server_socketio)
        self.verify_connection(new_client)
        new_client.emit('reactivate_team', {'team_name': 'ReactivateTeam'})
        eventlet.sleep(0.5)  # Give server time to process reactivation and clear cache
        new_client.get_received()

        # Dashboard should see team as waiting_pair
        dashboard_client.emit('dashboard_join')  # First join to trigger update
        eventlet.sleep(0.3)
        dashboard_client.emit('dashboard_join')  # Second join to ensure cache refresh
        eventlet.sleep(0.2)
        dash_msgs = dashboard_client.get_received()
        found = False
        for msg in dash_msgs:
            if msg.get('name') in ['dashboard_update', 'team_status_changed_for_dashboard']:
                teams = msg.get('args', [{}])[0].get('teams', [])
                for t in teams:
                    if t['team_name'] == 'ReactivateTeam' and t['status'] == 'waiting_pair':
                        found = True
        assert found, "Dashboard did not see team as waiting_pair after reactivation"
        new_client.disconnect()
        dashboard_client.disconnect()

    @pytest.mark.integration
    def test_dashboard_sees_status_on_disconnects(self, app_context, socket_client, second_client):
        """Dashboard client sees correct team/player status after each disconnect/reconnect."""
        dashboard_client = SocketIOTestClient(app, server_socketio)
        dashboard_client.emit('dashboard_join')
        eventlet.sleep(0.2)
        dashboard_client.get_received()
        
        # Enable teams streaming
        dashboard_client.emit('set_teams_streaming', {'enabled': True})
        eventlet.sleep(0.1)
        dashboard_client.get_received()

        # Player 1 creates team
        self.verify_connection(socket_client)
        socket_client.emit('create_team', {'team_name': 'DashStatusTeam'})
        team_created = self.wait_for_event(socket_client, 'team_created')
        team_id = team_created.get('args', [{}])[0].get('team_id')
        socket_client.get_received()

        # Player 2 joins team
        self.verify_connection(second_client)
        second_client.emit('join_team', {'team_name': 'DashStatusTeam'})
        self.wait_for_event(second_client, 'team_joined')
        second_client.get_received()

        # Dashboard sees both players
        found = self.check_dashboard_team_status(dashboard_client, 'DashStatusTeam', 'active')
        assert found, "Dashboard did not see both players as active"

        # Player 2 disconnects, dashboard sees waiting_pair
        self.simulate_disconnect(second_client)
        eventlet.sleep(0.3)  # Give time for disconnect processing
        
        # FIXED: Use helper method to check status with throttling support
        found = self.check_dashboard_team_status(dashboard_client, 'DashStatusTeam', 'waiting_pair')
        assert found, "Dashboard did not see waiting_pair after one disconnect"

        # Player 2 reconnects (joins again)
        new_client = SocketIOTestClient(app, server_socketio)
        self.verify_connection(new_client)
        new_client.emit('join_team', {'team_name': 'DashStatusTeam'})
        self.wait_for_event(new_client, 'team_joined')
        new_client.get_received()
        
        # FIXED: Use helper method to check status with throttling support
        found = self.check_dashboard_team_status(dashboard_client, 'DashStatusTeam', 'active')
        assert found, "Dashboard did not see both players as active after reconnect"
        new_client.disconnect()
        dashboard_client.disconnect()

    @pytest.mark.integration
    def test_player_disconnect_reconnect_same_sid(self, app_context, socket_client, second_client):
        """Edge case: Player disconnects and reconnects with same SID, dashboard and team state remain consistent."""
        dashboard_client = SocketIOTestClient(app, server_socketio)
        dashboard_client.emit('dashboard_join')
        eventlet.sleep(0.2)
        dashboard_client.get_received()
        
        # Enable teams streaming
        dashboard_client.emit('set_teams_streaming', {'enabled': True})
        eventlet.sleep(0.1)
        dashboard_client.get_received()

        # Player 1 creates team
        self.verify_connection(socket_client)
        socket_client.emit('create_team', {'team_name': 'ReconnectSIDTeam'})
        team_created = self.wait_for_event(socket_client, 'team_created')
        team_id = team_created.get('args', [{}])[0].get('team_id')
        socket_client.get_received()

        # Player 2 joins team
        self.verify_connection(second_client)
        second_client.emit('join_team', {'team_name': 'ReconnectSIDTeam'})
        self.wait_for_event(second_client, 'team_joined')
        second_client.get_received()

        # Player 2 disconnects
        self.simulate_disconnect(second_client)
        eventlet.sleep(0.3)  # Give time for disconnect processing
        
        # FIXED: Use helper method to check status with throttling support
        found = self.check_dashboard_team_status(dashboard_client, 'ReconnectSIDTeam', 'waiting_pair')
        assert found, "Dashboard did not see waiting_pair after disconnect"

        # Simulate reconnect with same SID (not possible with SocketIOTestClient, but we can check state remains consistent)
        # Instead, join as a new client
        new_client = SocketIOTestClient(app, server_socketio)
        self.verify_connection(new_client)
        new_client.emit('join_team', {'team_name': 'ReconnectSIDTeam'})
        self.wait_for_event(new_client, 'team_joined')
        new_client.get_received()
        
        # FIXED: Use helper method to check status with throttling support
        found = self.check_dashboard_team_status(dashboard_client, 'ReconnectSIDTeam', 'active')
        assert found, "Dashboard did not see both players as active after reconnect"
        new_client.disconnect()
        dashboard_client.disconnect()

    @pytest.mark.integration
    def test_two_teams_one_loses_player_dashboard_updates_only_that_team(self, app_context, socket_client, second_client):
        """Edge case: Two teams, one loses a player, dashboard only updates that team's status."""
        dashboard_client = SocketIOTestClient(app, server_socketio)
        dashboard_client.emit('dashboard_join')
        eventlet.sleep(0.2)
        dashboard_client.get_received()
        
        # Enable teams streaming
        dashboard_client.emit('set_teams_streaming', {'enabled': True})
        eventlet.sleep(0.1)
        dashboard_client.get_received()

        # Team 1
        self.verify_connection(socket_client)
        socket_client.emit('create_team', {'team_name': 'TeamOne'})
        self.wait_for_event(socket_client, 'team_created')
        socket_client.get_received()
        client2a = SocketIOTestClient(app, server_socketio)
        self.verify_connection(client2a)
        client2a.emit('join_team', {'team_name': 'TeamOne'})
        self.wait_for_event(client2a, 'team_joined')
        client2a.get_received()

        # Team 2
        client1b = SocketIOTestClient(app, server_socketio)
        self.verify_connection(client1b)
        client1b.emit('create_team', {'team_name': 'TeamTwo'})
        self.wait_for_event(client1b, 'team_created')
        client1b.get_received()
        client2b = SocketIOTestClient(app, server_socketio)
        self.verify_connection(client2b)
        client2b.emit('join_team', {'team_name': 'TeamTwo'})
        self.wait_for_event(client2b, 'team_joined')
        client2b.get_received()

        # Dashboard sees both teams as active
        found1 = self.check_dashboard_team_status(dashboard_client, 'TeamOne', 'active')
        found2 = self.check_dashboard_team_status(dashboard_client, 'TeamTwo', 'active')
        assert found1 and found2, "Dashboard did not see both teams as active"

        # TeamOne loses a player
        self.simulate_disconnect(client2a)
        eventlet.sleep(0.3)  # Give time for disconnect processing
        
        # FIXED: Check each team status individually with throttling support
        found_waiting = self.check_dashboard_team_status(dashboard_client, 'TeamOne', 'waiting_pair')
        found_active = self.check_dashboard_team_status(dashboard_client, 'TeamTwo', 'active')
        assert found_waiting and found_active, "Dashboard did not see correct status for both teams after one lost a player"

        # Clean up
        socket_client.disconnect()
        client1b.disconnect()
        client2b.disconnect()
        dashboard_client.disconnect()

    @pytest.mark.integration
    def test_rapid_join_leave_team(self, app_context, socket_client, second_client):
        """Two players rapidly join and leave a team multiple times, dashboard always reflects correct status."""
        dashboard_client = SocketIOTestClient(app, server_socketio)
        dashboard_client.emit('dashboard_join')
        eventlet.sleep(0.2)
        dashboard_client.get_received()
        
        # Enable teams streaming
        dashboard_client.emit('set_teams_streaming', {'enabled': True})
        eventlet.sleep(0.1)
        dashboard_client.get_received()
        for i in range(3):
            player1 = SocketIOTestClient(app, server_socketio)
            player2 = SocketIOTestClient(app, server_socketio)
            self.verify_connection(player1)
            # Create team
            player1.emit('create_team', {'team_name': f'RapidTeam{i}'})
            self.wait_for_event(player1, 'team_created')
            player1.get_received()
            # Player 2 joins
            self.verify_connection(player2)
            player2.emit('join_team', {'team_name': f'RapidTeam{i}'})
            self.wait_for_event(player2, 'team_joined')
            player2.get_received()
            # Player 2 leaves
            player2.emit('leave_team', {})
            eventlet.sleep(0.2)
            player2.get_received()
            # Player 2 rejoins
            player2.emit('join_team', {'team_name': f'RapidTeam{i}'})
            self.wait_for_event(player2, 'team_joined')
            player2.get_received()
            # Player 1 leaves
            player1.emit('leave_team', {})
            eventlet.sleep(0.2)
            player1.get_received()
            # Dashboard should see team as inactive or waiting_pair
            dashboard_client.emit('dashboard_join')
            eventlet.sleep(0.2)
            dash_msgs = dashboard_client.get_received()
            found = False
            for msg in dash_msgs:
                if msg.get('name') in ['dashboard_update', 'team_status_changed_for_dashboard']:
                    teams = msg.get('args', [{}])[0].get('teams', [])
                    for t in teams:
                        if t['team_name'] == f'RapidTeam{i}' and t['status'] in ('inactive', 'waiting_pair'):
                            found = True
            assert found, f"Dashboard did not see correct status for RapidTeam{i} after rapid join/leave"
            player1.disconnect()
            player2.disconnect()
        dashboard_client.disconnect()

    @pytest.mark.integration
    def test_simultaneous_disconnects(self, app_context, socket_client, second_client):
        """Both players disconnect at nearly the same time, team becomes inactive, dashboard reflects this."""
        dashboard_client = SocketIOTestClient(app, server_socketio)
        dashboard_client.emit('dashboard_join')
        eventlet.sleep(0.2)
        dashboard_client.get_received()
        
        # Enable teams streaming
        dashboard_client.emit('set_teams_streaming', {'enabled': True})
        eventlet.sleep(0.1)
        dashboard_client.get_received()
        self.verify_connection(socket_client)
        socket_client.emit('create_team', {'team_name': 'SimulTeam'})
        self.wait_for_event(socket_client, 'team_created')
        socket_client.get_received()
        self.verify_connection(second_client)
        second_client.emit('join_team', {'team_name': 'SimulTeam'})
        self.wait_for_event(second_client, 'team_joined')
        second_client.get_received()
        # Both disconnect nearly simultaneously
        self.simulate_disconnect(second_client)
        self.simulate_disconnect(socket_client)
        eventlet.sleep(0.5)
        dashboard_client.emit('dashboard_join')
        eventlet.sleep(0.2)
        dash_msgs = dashboard_client.get_received()
        found = False
        for msg in dash_msgs:
            if msg.get('name') in ['dashboard_update', 'team_status_changed_for_dashboard']:
                teams = msg.get('args', [{}])[0].get('teams', [])
                for t in teams:
                    if t['team_name'] == 'SimulTeam' and t['status'] == 'inactive':
                        found = True
        assert found, "Dashboard did not see team as inactive after simultaneous disconnects"
        dashboard_client.disconnect()

    @pytest.mark.integration
    def test_rejoin_after_inactivity(self, app_context, socket_client, second_client):
        """Player tries to join a team that is inactive before reactivation, should get error."""
        self.verify_connection(socket_client)
        socket_client.emit('create_team', {'team_name': 'InactiveTeam'})
        self.wait_for_event(socket_client, 'team_created')
        socket_client.get_received()
        self.verify_connection(second_client)
        second_client.emit('join_team', {'team_name': 'InactiveTeam'})
        self.wait_for_event(second_client, 'team_joined')
        second_client.get_received()
        # Both leave
        second_client.emit('leave_team', {})
        eventlet.sleep(0.2)
        second_client.get_received()
        socket_client.emit('leave_team', {})
        eventlet.sleep(0.2)
        socket_client.get_received()
        # Try to join as a new client before reactivation
        new_client = SocketIOTestClient(app, server_socketio)
        self.verify_connection(new_client)
        new_client.emit('join_team', {'team_name': 'InactiveTeam'})
        eventlet.sleep(0.2)
        msgs = new_client.get_received()
        found_error = any(msg.get('name') == 'error' for msg in msgs)
        assert found_error, "Player did not get error when joining inactive team before reactivation"
        new_client.disconnect()

    @pytest.mark.integration
    def test_dashboard_connects_midgame(self, app_context, socket_client, second_client):
        """Dashboard connects after teams/players have joined/left, sees correct state."""
        self.verify_connection(socket_client)
        socket_client.emit('create_team', {'team_name': 'MidGameTeam'})
        self.wait_for_event(socket_client, 'team_created')
        socket_client.get_received()
        self.verify_connection(second_client)
        second_client.emit('join_team', {'team_name': 'MidGameTeam'})
        self.wait_for_event(second_client, 'team_joined')
        second_client.get_received()
        # Player 2 leaves
        second_client.emit('leave_team', {})
        eventlet.sleep(0.2)
        second_client.get_received()
        # Dashboard connects now
        dashboard_client = SocketIOTestClient(app, server_socketio)
        dashboard_client.emit('dashboard_join')
        eventlet.sleep(0.2)
        dashboard_client.get_received()
        
        # Enable teams streaming
        dashboard_client.emit('set_teams_streaming', {'enabled': True})
        eventlet.sleep(0.1)
        dashboard_client.get_received()
        
        # Request teams update after enabling streaming
        dashboard_client.emit('request_teams_update')
        eventlet.sleep(0.1)
        dash_msgs = dashboard_client.get_received()
        found = False
        for msg in dash_msgs:
            if msg.get('name') in ['dashboard_update', 'team_status_changed_for_dashboard']:
                teams = msg.get('args', [{}])[0].get('teams', [])
                for t in teams:
                    # Accept both waiting_pair status and teams with one player as valid
                    if t['team_name'] == 'MidGameTeam' and (t['status'] == 'waiting_pair' or t.get('status') == 'inactive'):
                        found = True
        assert found, "Dashboard did not see correct state when connecting mid-game"
        dashboard_client.disconnect()

    @pytest.mark.integration
    def test_player_tries_to_join_full_team(self, app_context, socket_client, second_client):
        """Third player tries to join a full team, gets error, dashboard unchanged."""
        dashboard_client = SocketIOTestClient(app, server_socketio)
        dashboard_client.emit('dashboard_join')
        eventlet.sleep(0.2)
        dashboard_client.get_received()
        
        # Enable teams streaming
        dashboard_client.emit('set_teams_streaming', {'enabled': True})
        eventlet.sleep(0.1)
        dashboard_client.get_received()
        self.verify_connection(socket_client)
        socket_client.emit('create_team', {'team_name': 'FullTeam'})
        self.wait_for_event(socket_client, 'team_created')
        socket_client.get_received()
        self.verify_connection(second_client)
        second_client.emit('join_team', {'team_name': 'FullTeam'})
        self.wait_for_event(second_client, 'team_joined')
        second_client.get_received()
        # Third player tries to join
        third_client = SocketIOTestClient(app, server_socketio)
        self.verify_connection(third_client)
        third_client.emit('join_team', {'team_name': 'FullTeam'})
        eventlet.sleep(0.2)
        msgs = third_client.get_received()
        found_error = any(msg.get('name') == 'error' for msg in msgs)
        assert found_error, "Third player did not get error when joining full team"
        # Dashboard should still see team as active
        dashboard_client.emit('dashboard_join')
        eventlet.sleep(0.2)
        dash_msgs = dashboard_client.get_received()
        found = False
        for msg in dash_msgs:
            if msg.get('name') in ['dashboard_update', 'team_status_changed_for_dashboard']:
                teams = msg.get('args', [{}])[0].get('teams', [])
                for t in teams:
                    if t['team_name'] == 'FullTeam' and t['status'] == 'active':
                        found = True
        assert found, "Dashboard did not see team as active after full join attempt"
        third_client.disconnect()
        dashboard_client.disconnect()

    @pytest.mark.integration
    def test_player_leaves_and_rejoins_quickly(self, app_context, socket_client, second_client):
        """Player leaves and immediately rejoins, team goes from waiting_pair to active, dashboard reflects this."""
        dashboard_client = SocketIOTestClient(app, server_socketio)
        dashboard_client.emit('dashboard_join')
        eventlet.sleep(0.2)
        dashboard_client.get_received()
        
        # Enable teams streaming
        dashboard_client.emit('set_teams_streaming', {'enabled': True})
        eventlet.sleep(0.1)
        dashboard_client.get_received()
        self.verify_connection(socket_client)
        socket_client.emit('create_team', {'team_name': 'QuickRejoinTeam'})
        self.wait_for_event(socket_client, 'team_created')
        socket_client.get_received()
        self.verify_connection(second_client)
        second_client.emit('join_team', {'team_name': 'QuickRejoinTeam'})
        self.wait_for_event(second_client, 'team_joined')
        second_client.get_received()
        # Player 2 leaves and immediately rejoins
        second_client.emit('leave_team', {})
        eventlet.sleep(0.1)
        second_client.emit('join_team', {'team_name': 'QuickRejoinTeam'})
        self.wait_for_event(second_client, 'team_joined')
        second_client.get_received()
        dashboard_client.emit('dashboard_join')
        eventlet.sleep(0.2)
        dash_msgs = dashboard_client.get_received()
        found = False
        for msg in dash_msgs:
            if msg.get('name') in ['dashboard_update', 'team_status_changed_for_dashboard']:
                teams = msg.get('args', [{}])[0].get('teams', [])
                for t in teams:
                    if t['team_name'] == 'QuickRejoinTeam' and t['status'] == 'active':
                        found = True
        assert found, "Dashboard did not see team as active after quick rejoin"
        dashboard_client.disconnect()

    @pytest.mark.integration
    def test_team_name_collision_on_reactivation(self, app_context, socket_client, second_client):
        """Player tries to reactivate a team name that is already active, gets error."""
        self.verify_connection(socket_client)
        socket_client.emit('create_team', {'team_name': 'CollisionTeam'})
        self.wait_for_event(socket_client, 'team_created')
        socket_client.get_received()
        # Try to reactivate same team name while it's active
        new_client = SocketIOTestClient(app, server_socketio)
        self.verify_connection(new_client)
        new_client.emit('reactivate_team', {'team_name': 'CollisionTeam'})
        eventlet.sleep(0.2)
        msgs = new_client.get_received()
        found_error = any(msg.get('name') == 'error' for msg in msgs)
        assert found_error, "Player did not get error when reactivating already active team name"
        new_client.disconnect()

    @pytest.mark.integration
    def test_create_team_automatically_reactivates_inactive(self, app_context, socket_client, second_client):
        """Creating a team with an inactive team's name automatically reactivates the inactive team."""
        # First, create a team and make it inactive
        self.verify_connection(socket_client)
        socket_client.emit('create_team', {'team_name': 'AutoReactivateTeam'})
        team_created = self.wait_for_event(socket_client, 'team_created')
        original_team_id = team_created.get('args', [{}])[0].get('team_id')
        socket_client.get_received()
        
        # Join with second player to get some history
        self.verify_connection(second_client)
        second_client.emit('join_team', {'team_name': 'AutoReactivateTeam'})
        self.wait_for_event(second_client, 'team_joined')
        second_client.get_received()
        
        # Both players leave to make team inactive
        socket_client.emit('leave_team', {})
        eventlet.sleep(0.1)
        socket_client.get_received()
        second_client.emit('leave_team', {})
        eventlet.sleep(0.1)
        second_client.get_received()
        
        # Verify team is now inactive in database
        from src.models.quiz_models import Teams
        team = Teams.query.filter_by(team_id=original_team_id).first()
        assert team.is_active == False
        
        # New player tries to "create" team with same name - should reactivate
        new_client = SocketIOTestClient(app, server_socketio)
        self.verify_connection(new_client)
        new_client.emit('create_team', {'team_name': 'AutoReactivateTeam'})
        team_created = self.wait_for_event(new_client, 'team_created')
        
        # Verify it's a reactivation, not a new team
        team_created_data = team_created.get('args', [{}])[0]
        assert team_created_data.get('team_id') == original_team_id
        assert team_created_data.get('is_reactivated') == True
        assert 'reactivated successfully' in team_created_data.get('message', '')
        
        # Verify team is active again in database
        team = Teams.query.filter_by(team_id=original_team_id).first()
        assert team.is_active == True
        assert team.player1_session_id is not None
        
        new_client.get_received()
        new_client.disconnect()

    @pytest.mark.integration
    def test_create_team_reactivation_preserves_team_id(self, app_context, socket_client, second_client):
        """Team reactivation through create_team preserves original team ID and history."""
        # Create team and add some round history
        self.verify_connection(socket_client)
        socket_client.emit('create_team', {'team_name': 'HistoryTeam'})
        team_created = self.wait_for_event(socket_client, 'team_created')
        original_team_id = team_created.get('args', [{}])[0].get('team_id')
        socket_client.get_received()
        
        # Join second player
        self.verify_connection(second_client)
        second_client.emit('join_team', {'team_name': 'HistoryTeam'})
        self.wait_for_event(second_client, 'team_joined')
        second_client.get_received()
        
        # Simulate some game rounds by adding database records
        from src.models.quiz_models import Teams, PairQuestionRounds, ItemEnum
        round1 = PairQuestionRounds(
            team_id=original_team_id,
            round_number_for_team=1,
            player1_item=ItemEnum.A,
            player2_item=ItemEnum.B
        )
        round2 = PairQuestionRounds(
            team_id=original_team_id,
            round_number_for_team=2,
            player1_item=ItemEnum.X,
            player2_item=ItemEnum.Y
        )
        from src.config import db
        db.session.add(round1)
        db.session.add(round2)
        db.session.commit()
        
        # Both players leave
        socket_client.emit('leave_team', {})
        eventlet.sleep(0.1)
        socket_client.get_received()
        second_client.emit('leave_team', {})
        eventlet.sleep(0.1)
        second_client.get_received()
        
        # New player reactivates by creating team with same name
        new_client = SocketIOTestClient(app, server_socketio)
        self.verify_connection(new_client)
        new_client.emit('create_team', {'team_name': 'HistoryTeam'})
        team_created = self.wait_for_event(new_client, 'team_created')
        
        # Verify same team ID and reactivation flag
        team_created_data = team_created.get('args', [{}])[0]
        assert team_created_data.get('team_id') == original_team_id
        assert team_created_data.get('is_reactivated') == True
        
        # Verify round history is preserved in state
        from src.state import state
        team_state = state.active_teams.get('HistoryTeam')
        assert team_state is not None
        assert team_state['current_round_number'] == 2  # Should remember last round
        
        # Cleanup
        db.session.delete(round1)
        db.session.delete(round2)
        db.session.commit()
        
        new_client.get_received()
        new_client.disconnect()

    @pytest.mark.integration
    def test_create_team_vs_explicit_reactivate_identical_behavior(self, app_context, socket_client, second_client):
        """Creating team with inactive name vs explicit reactivation should have identical results."""
        # Create and deactivate first team
        self.verify_connection(socket_client)
        socket_client.emit('create_team', {'team_name': 'BehaviorTest1'})
        team1_created = self.wait_for_event(socket_client, 'team_created')
        team1_id = team1_created.get('args', [{}])[0].get('team_id')
        socket_client.get_received()
        socket_client.emit('leave_team', {})
        eventlet.sleep(0.1)
        socket_client.get_received()
        
        # Create and deactivate second team
        second_client.emit('create_team', {'team_name': 'BehaviorTest2'})
        team2_created = self.wait_for_event(second_client, 'team_created')
        team2_id = team2_created.get('args', [{}])[0].get('team_id')
        second_client.get_received()
        second_client.emit('leave_team', {})
        eventlet.sleep(0.1)
        second_client.get_received()
        
        # Reactivate first team through create_team
        new_client1 = SocketIOTestClient(app, server_socketio)
        self.verify_connection(new_client1)
        new_client1.emit('create_team', {'team_name': 'BehaviorTest1'})
        create_result = self.wait_for_event(new_client1, 'team_created')
        create_data = create_result.get('args', [{}])[0]
        new_client1.get_received()
        
        # Reactivate second team through explicit reactivate_team
        new_client2 = SocketIOTestClient(app, server_socketio)
        self.verify_connection(new_client2)
        new_client2.emit('reactivate_team', {'team_name': 'BehaviorTest2'})
        reactivate_result = self.wait_for_event(new_client2, 'team_created')
        reactivate_data = reactivate_result.get('args', [{}])[0]
        new_client2.get_received()
        
        # Both should have identical structure (except for team-specific data)
        assert create_data.get('team_id') == team1_id
        assert reactivate_data.get('team_id') == team2_id
        assert create_data.get('is_reactivated') == True
        assert reactivate_data.get('is_reactivated') == True
        assert create_data.get('player_slot') == 1
        assert reactivate_data.get('player_slot') == 1
        assert 'reactivated successfully' in create_data.get('message', '')
        assert 'reactivated successfully' in reactivate_data.get('message', '')
        
        new_client1.disconnect()
        new_client2.disconnect()

    @pytest.mark.integration
    def test_create_team_name_conflict_with_active_team(self, app_context, socket_client, second_client):
        """Creating team with name of existing active team should fail, not reactivate."""
        # Create active team
        self.verify_connection(socket_client)
        socket_client.emit('create_team', {'team_name': 'ConflictTeam'})
        self.wait_for_event(socket_client, 'team_created')
        socket_client.get_received()
        
        # Try to create another team with same name while first is active
        self.verify_connection(second_client)
        second_client.emit('create_team', {'team_name': 'ConflictTeam'})
        eventlet.sleep(0.2)
        msgs = second_client.get_received()
        
        # Should get error, not reactivation
        found_error = any(msg.get('name') == 'error' for msg in msgs)
        assert found_error, "Should get error when creating team with active team name"
        
        # Verify error message mentions existing/active team
        error_msgs = [msg for msg in msgs if msg.get('name') == 'error']
        assert any('already exists' in msg.get('args', [{}])[0].get('message', '') 
                  for msg in error_msgs), "Error message should mention team already exists"

    def get_client_sid(self, client):
        """Extract session ID from test client by looking at connection events"""
        # The most reliable way is to look at the connection event that was received
        if not hasattr(self, '_client_sids'):
            self._client_sids = {}
        
        # If we already know this client's SID, return it
        client_id = id(client)
        if client_id in self._client_sids:
            return self._client_sids[client_id]
        
        # Try to extract SID from the client's connection
        # Check what SIDs are currently in the state
        all_current_sids = set()
        all_current_sids.update(state.player_to_team.keys())
        all_current_sids.update(state.dashboard_clients)
        
        # Store the mapping for future use
        if all_current_sids:
            # For simplicity in tests, assume the most recent SID belongs to this client
            client_sid = max(all_current_sids) if all_current_sids else None
            if client_sid:
                self._client_sids[client_id] = client_sid
                return client_sid
        
        return None

    def simulate_disconnect(self, client):
        """Simulate client disconnect by calling leave_team event directly."""
        # In integration tests we can't force actual disconnects, 
        # but we can trigger the same state changes
        try:
            client.disconnect()
        except:
            pass  # Client may already be disconnected

    def force_fresh_dashboard_update(self, dashboard_client):
        """Force the dashboard to get fresh, non-throttled data by clearing server caches."""
        # Import the server function to force cache clearing
        try:
            from src.sockets.dashboard import force_clear_all_caches
            force_clear_all_caches()
            eventlet.sleep(0.1)  # Allow time for cache clearing
        except ImportError:
            pass  # Function may not be available in test environment
        
        # Trigger dashboard update after clearing caches
        dashboard_client.emit('dashboard_join')
        eventlet.sleep(0.3)  # Wait longer to account for any throttling

    def check_dashboard_team_status(self, dashboard_client, team_name, expected_status, timeout=2.0):
        """Check dashboard for team status, forcing fresh updates if needed and retrying."""
        # Try multiple approaches to get fresh status
        attempts = 3
        for attempt in range(attempts):
            if attempt > 0:
                # Force fresh update on subsequent attempts
                self.force_fresh_dashboard_update(dashboard_client)
            else:
                # First attempt - just trigger normal update
                dashboard_client.emit('dashboard_join')
                eventlet.sleep(0.3)
            
            dash_msgs = dashboard_client.get_received()
            for msg in dash_msgs:
                if msg.get('name') in ['dashboard_update', 'team_status_changed_for_dashboard']:
                    teams = msg.get('args', [{}])[0].get('teams', [])
                    for t in teams:
                        if t['team_name'] == team_name and t['status'] == expected_status:
                            return True
            
            if attempt < attempts - 1:
                eventlet.sleep(0.5)  # Wait before retry
        
        return False


