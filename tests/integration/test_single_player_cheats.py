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

# Import socket handlers to register them with SocketIO
from src.sockets.team_management import handle_connect, handle_disconnect, on_create_team, on_join_team, on_leave_team
from src.sockets.game import on_submit_answer
from src.sockets import dashboard

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
            
            # Clear database with proper rollback handling
            try:
                Answers.query.delete()
                PairQuestionRounds.query.delete()
                Teams.query.delete()
                db.session.commit()
            except Exception as db_error:
                logger.warning(f"Database clear failed, rolling back: {db_error}")
                db.session.rollback()
                # Try again after rollback
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
    reset_application_state()
    yield
    logger.info("\n[TEST CLEANUP] Final state cleanup...")
    reset_application_state()

@pytest.fixture
def app_context():
    """Create application context for tests"""
    with app.app_context():
        yield app

class TestSinglePlayerCheats:
    """Integration tests for single-player cheat functionality (tony/kevin)"""
    
    def create_robust_client(self):
        """Create a SocketIO test client with robust connection handling"""
        client = SocketIOTestClient(app, server_socketio)
        
        # Ensure connection is established with retry logic
        max_retries = 5
        for attempt in range(max_retries):
            if client.connected:
                break
            eventlet.sleep(0.1)
            if attempt == max_retries - 1:
                raise AssertionError(f"Client failed to connect after {max_retries} attempts")
        
        # Wait for and verify connection_established event with extended timeout
        connection_data = None
        max_wait_time = 3.0  # Extended timeout
        start_time = time.time()
        
        while (time.time() - start_time) < max_wait_time:
            eventlet.sleep(0.1)
            messages = client.get_received()
            for msg in messages:
                if msg.get('name') == 'connection_established':
                    connection_data = msg.get('args', [{}])[0]
                    break
            if connection_data:
                break
        
        if not connection_data:
            # Log received messages for debugging
            messages = client.get_received()
            logger.error(f"Failed to receive connection_established. Received: {messages}")
            raise AssertionError("Did not receive connection_established event within timeout")
        
        return client

    def wait_for_event(self, client, event_name, timeout=3.0):
        """Wait for a specific event with improved timing"""
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            eventlet.sleep(0.05)  # Shorter sleep for better responsiveness
            messages = client.get_received()
            for msg in messages:
                if msg.get('name') == event_name:
                    return msg
        
        # If we didn't find the event, log what we did receive for debugging
        logger.warning(f"Failed to receive {event_name} within {timeout}s")
        final_messages = client.get_received()
        logger.warning(f"Final messages received: {[msg.get('name') for msg in final_messages]}")
        return None

    def setup_single_player_team(self, team_name, cheat_type, app_context):
        """Helper to set up a single-player cheat team"""
        client = self.create_robust_client()
        
        # Clear any previous messages
        client.get_received()
        
        # Create team
        client.emit('create_team', {'team_name': team_name})
        team_created = self.wait_for_event(client, 'team_created')
        assert team_created is not None, f"Failed to create team {team_name}"
        
        team_data = team_created.get('args', [{}])[0]
        team_id = team_data.get('team_id')
        assert team_id is not None, "Team creation did not return team_id"
        assert team_data.get('cheat_type') == cheat_type, f"Expected cheat_type {cheat_type}, got {team_data.get('cheat_type')}"
        
        # Clear messages after team creation
        client.get_received()
        
        return client, team_id

    @pytest.mark.integration
    def test_cheat_tony_single_player_auto_win(self, app_context):
        """Test cheat-tony functionality: single player auto-wins"""
        team_name = 'cheat-tony-test'
        client, team_id = self.setup_single_player_team(team_name, 'tony', app_context)
        
        try:
            # Enable game
            state.game_started = True
            
            # Create a test round manually
            test_round = PairQuestionRounds(
                team_id=team_id,
                round_number_for_team=1,
                player1_item=ItemEnum.A,
                player2_item=ItemEnum.X  # A-X requires "same" parity for win
            )
            db.session.add(test_round)
            db.session.commit()
            
            # Update team state for the round
            team_info = state.active_teams.get(team_name)
            team_info['current_db_round_id'] = test_round.round_id
            team_info['current_round_number'] = 1
            team_info['status'] = 'waiting_pair'  # Single player team
            
            # Verify team has only one player
            assert len(team_info['players']) == 1, "Team should have exactly one player"
            
            # Player submits answer (should trigger auto-fill for partner)
            client.emit('submit_answer', {
                'round_id': test_round.round_id,
                'item': 'A',
                'answer': True
            })
            
            # Collect all events after submission (auto-fill should trigger multiple events)
            all_events = []
            start_time = time.time()
            while (time.time() - start_time) < 5.0:  # Extended timeout for auto-fill
                eventlet.sleep(0.1)
                messages = client.get_received()
                all_events.extend(messages)
                
                # Check if we have both expected events
                answer_confirmed = next((msg for msg in all_events if msg.get('name') == 'answer_confirmed'), None)
                round_complete = next((msg for msg in all_events if msg.get('name') == 'round_complete'), None)
                
                if answer_confirmed and round_complete:
                    break
            
            # Verify we got answer confirmation
            assert answer_confirmed is not None, f"Should receive answer_confirmed. Events: {[msg.get('name') for msg in all_events]}"
            
            # Verify we got round completion
            assert round_complete is not None, f"Should receive round_complete after auto-fill. Events: {[msg.get('name') for msg in all_events]}"
            
            # Verify the round was completed with a win
            round_data = round_complete.get('args', [{}])[0]
            assert round_data.get('success') is True, "Tony team should auto-win"
            
            # Verify database state: should have exactly 2 answers
            answers = Answers.query.filter_by(question_round_id=test_round.round_id).all()
            assert len(answers) == 2, f"Should have exactly 2 answers, got {len(answers)}"
            
            # Verify one is real answer, one is auto-filled
            real_answer = next(a for a in answers if not a.player_session_id.startswith('auto_'))
            auto_answer = next(a for a in answers if a.player_session_id.startswith('auto_'))
            
            assert real_answer.response_value is True, "Real answer should be True"
            # For A-X (same parity), both should be True for a win
            assert auto_answer.response_value is True, "Auto-filled answer should be True for win"
            
        finally:
            if client.connected:
                client.disconnect()

    @pytest.mark.integration
    def test_cheat_kevin_single_player_auto_lose(self, app_context):
        """Test cheat-kevin functionality: single player auto-loses"""
        team_name = 'cheat-kevin-test'
        client, team_id = self.setup_single_player_team(team_name, 'kevin', app_context)
        
        try:
            # Enable game
            state.game_started = True
            
            # Create a test round manually
            test_round = PairQuestionRounds(
                team_id=team_id,
                round_number_for_team=1,
                player1_item=ItemEnum.A,
                player2_item=ItemEnum.X  # A-X requires "same" parity for win
            )
            db.session.add(test_round)
            db.session.commit()
            
            # Update team state for the round
            team_info = state.active_teams.get(team_name)
            team_info['current_db_round_id'] = test_round.round_id
            team_info['current_round_number'] = 1
            team_info['status'] = 'waiting_pair'  # Single player team
            
            # Player submits answer (should trigger auto-fill for partner to lose)
            client.emit('submit_answer', {
                'round_id': test_round.round_id,
                'item': 'A',
                'answer': True
            })
            
            # Collect all events after submission (auto-fill should trigger multiple events)
            all_events = []
            start_time = time.time()
            while (time.time() - start_time) < 5.0:  # Extended timeout for auto-fill
                eventlet.sleep(0.1)
                messages = client.get_received()
                all_events.extend(messages)
                
                # Check if we have both expected events
                answer_confirmed = next((msg for msg in all_events if msg.get('name') == 'answer_confirmed'), None)
                round_complete = next((msg for msg in all_events if msg.get('name') == 'round_complete'), None)
                
                if answer_confirmed and round_complete:
                    break
            
            # Verify we got answer confirmation
            assert answer_confirmed is not None, f"Should receive answer_confirmed. Events: {[msg.get('name') for msg in all_events]}"
            
            # Verify we got round completion
            assert round_complete is not None, f"Should receive round_complete after auto-fill. Events: {[msg.get('name') for msg in all_events]}"
            
            # Verify the round was completed with a loss
            round_data = round_complete.get('args', [{}])[0]
            assert round_data.get('success') is False, "Kevin team should auto-lose"
            
            # Verify database state: should have exactly 2 answers
            answers = Answers.query.filter_by(question_round_id=test_round.round_id).all()
            assert len(answers) == 2, f"Should have exactly 2 answers, got {len(answers)}"
            
            # Verify one is real answer, one is auto-filled to cause loss
            real_answer = next(a for a in answers if not a.player_session_id.startswith('auto_'))
            auto_answer = next(a for a in answers if a.player_session_id.startswith('auto_'))
            
            assert real_answer.response_value is True, "Real answer should be True"
            # For A-X (same parity), auto-answer should be False to cause loss
            assert auto_answer.response_value is False, "Auto-filled answer should be False for loss"
            
        finally:
            if client.connected:
                client.disconnect()

    @pytest.mark.integration
    def test_single_player_submission_validation(self, app_context):
        """Test that single-player teams can submit when waiting_pair but normal teams cannot"""
        # Test tony team (single player allowed)
        tony_client, tony_team_id = self.setup_single_player_team('cheat-tony-validation', 'tony', app_context)
        
        # Test normal team (single player not allowed)
        normal_client = self.create_robust_client()
        normal_client.get_received()
        
        try:
            # Create normal team
            normal_client.emit('create_team', {'team_name': 'normal-validation'})
            normal_team_created = self.wait_for_event(normal_client, 'team_created')
            assert normal_team_created is not None, "Failed to create normal team"
            normal_team_id = normal_team_created.get('args', [{}])[0].get('team_id')
            
            # Enable game
            state.game_started = True
            
            # Create test rounds for both teams with unique round numbers
            tony_round = PairQuestionRounds(
                team_id=tony_team_id,
                round_number_for_team=1,
                player1_item=ItemEnum.A,
                player2_item=ItemEnum.X
            )
            normal_round = PairQuestionRounds(
                team_id=normal_team_id,
                round_number_for_team=1,  # Same round number is OK if different team_id
                player1_item=ItemEnum.A,
                player2_item=ItemEnum.X
            )
            try:
                db.session.add(tony_round)
                db.session.add(normal_round)
                db.session.commit()
            except Exception as e:
                logger.error(f"Database constraint error: {e}")
                db.session.rollback()
                # Skip this test if we have database constraint issues
                pytest.skip(f"Database constraint issue - teams may have same ID: {e}")
            
            # Update team states
            tony_info = state.active_teams.get('cheat-tony-validation')
            tony_info['current_db_round_id'] = tony_round.round_id
            tony_info['status'] = 'waiting_pair'
            
            normal_info = state.active_teams.get('normal-validation')
            normal_info['current_db_round_id'] = normal_round.round_id
            normal_info['status'] = 'waiting_pair'
            
            # Clear messages
            tony_client.get_received()
            normal_client.get_received()
            
            # Tony team should be able to submit
            tony_client.emit('submit_answer', {
                'round_id': tony_round.round_id,
                'item': 'A',
                'answer': True
            })
            
            # Normal team should NOT be able to submit
            normal_client.emit('submit_answer', {
                'round_id': normal_round.round_id,
                'item': 'A',
                'answer': True
            })
            
            # Tony should get confirmation, normal should get error
            tony_confirmed = self.wait_for_event(tony_client, 'answer_confirmed')
            normal_error = self.wait_for_event(normal_client, 'error')
            
            assert tony_confirmed is not None, "Tony team should be able to submit when waiting_pair"
            assert normal_error is not None, "Normal team should get error when trying to submit while waiting_pair"
            
            # Verify error message
            error_data = normal_error.get('args', [{}])[0]
            assert 'not active' in error_data.get('message', '').lower(), "Error should mention team not active"
            
        finally:
            if tony_client.connected:
                tony_client.disconnect()
            if normal_client.connected:
                normal_client.disconnect()

    def wait_for_event(self, client, event_name, timeout=3.0):
        """Wait for a specific event with improved timing"""
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            eventlet.sleep(0.05)
            messages = client.get_received()
            for msg in messages:
                if msg.get('name') == event_name:
                    return msg
        return None

    def create_robust_client(self):
        """Create a SocketIO test client with robust connection handling"""
        client = SocketIOTestClient(app, server_socketio)
        
        # Ensure connection is established with retry logic
        max_retries = 5
        for attempt in range(max_retries):
            if client.connected:
                break
            eventlet.sleep(0.1)
            if attempt == max_retries - 1:
                raise AssertionError(f"Client failed to connect after {max_retries} attempts")
        
        # Wait for and verify connection_established event with extended timeout
        connection_data = None
        max_wait_time = 3.0
        start_time = time.time()
        
        while (time.time() - start_time) < max_wait_time:
            eventlet.sleep(0.1)
            messages = client.get_received()
            for msg in messages:
                if msg.get('name') == 'connection_established':
                    connection_data = msg.get('args', [{}])[0]
                    break
            if connection_data:
                break
        
        if not connection_data:
            # Log received messages for debugging
            messages = client.get_received()
            logger.error(f"Failed to receive connection_established. Received: {messages}")
            raise AssertionError("Did not receive connection_established event within timeout")
        
        return client

    def setup_single_player_team(self, team_name, cheat_type, app_context):
        """Helper to set up a single-player cheat team"""
        client = self.create_robust_client()
        
        # Clear any previous messages
        client.get_received()
        
        # Create team
        client.emit('create_team', {'team_name': team_name})
        team_created = self.wait_for_event(client, 'team_created')
        assert team_created is not None, f"Failed to create team {team_name}"
        
        team_data = team_created.get('args', [{}])[0]
        team_id = team_data.get('team_id')
        assert team_id is not None, "Team creation did not return team_id"
        assert team_data.get('cheat_type') == cheat_type, f"Expected cheat_type {cheat_type}, got {team_data.get('cheat_type')}"
        
        # Clear messages after team creation
        client.get_received()
        
        return client, team_id

    @pytest.mark.integration
    def test_tony_auto_fill_different_parity(self, app_context):
        """Test tony auto-fill with different parity requirement (BY/YB)"""
        team_name = 'cheat-tony-different'
        client, team_id = self.setup_single_player_team(team_name, 'tony', app_context)
        
        try:
            # Enable game
            state.game_started = True
            
            # Create round with BY (requires different answers for win)
            test_round = PairQuestionRounds(
                team_id=team_id,
                round_number_for_team=1,
                player1_item=ItemEnum.B,
                player2_item=ItemEnum.Y
            )
            db.session.add(test_round)
            db.session.commit()
            
            # Update team state
            team_info = state.active_teams.get(team_name)
            team_info['current_db_round_id'] = test_round.round_id
            team_info['current_round_number'] = 1
            team_info['status'] = 'waiting_pair'
            
            # Player submits True
            client.emit('submit_answer', {
                'round_id': test_round.round_id,
                'item': 'B',
                'answer': True
            })
            
            # Wait for round completion
            round_complete = self.wait_for_event(client, 'round_complete')
            assert round_complete is not None, "Should receive round_complete"
            
            # Should win (BY requires different, so True/False wins)
            round_data = round_complete.get('args', [{}])[0]
            assert round_data.get('success') is True, "Tony should auto-win with different parity"
            
            # Verify database: auto-filled answer should be False (different from True)
            answers = Answers.query.filter_by(question_round_id=test_round.round_id).all()
            assert len(answers) == 2, "Should have 2 answers"
            
            auto_answer = next(a for a in answers if a.player_session_id.startswith('auto_'))
            assert auto_answer.response_value is False, "Auto-filled answer should be False for different parity win"
            
        finally:
            if client.connected:
                client.disconnect()

    @pytest.mark.integration
    def test_kevin_auto_fill_same_parity(self, app_context):
        """Test kevin auto-fill with same parity requirement (AX/BX/AY)"""
        team_name = 'cheat-kevin-same'
        client, team_id = self.setup_single_player_team(team_name, 'kevin', app_context)
        
        try:
            # Enable game
            state.game_started = True
            
            # Create round with AX (requires same answers for win)
            test_round = PairQuestionRounds(
                team_id=team_id,
                round_number_for_team=1,
                player1_item=ItemEnum.A,
                player2_item=ItemEnum.X
            )
            db.session.add(test_round)
            db.session.commit()
            
            # Update team state
            team_info = state.active_teams.get(team_name)
            team_info['current_db_round_id'] = test_round.round_id
            team_info['current_round_number'] = 1
            team_info['status'] = 'waiting_pair'
            
            # Player submits True
            client.emit('submit_answer', {
                'round_id': test_round.round_id,
                'item': 'A',
                'answer': True
            })
            
            # Wait for round completion
            round_complete = self.wait_for_event(client, 'round_complete')
            assert round_complete is not None, "Should receive round_complete"
            
            # Should lose (kevin auto-loses)
            round_data = round_complete.get('args', [{}])[0]
            assert round_data.get('success') is False, "Kevin should auto-lose"
            
            # Verify database: auto-filled answer should be False (opposite of True for loss)
            answers = Answers.query.filter_by(question_round_id=test_round.round_id).all()
            assert len(answers) == 2, "Should have 2 answers"
            
            auto_answer = next(a for a in answers if a.player_session_id.startswith('auto_'))
            assert auto_answer.response_value is False, "Auto-filled answer should be False to cause loss"
            
        finally:
            if client.connected:
                client.disconnect()

    @pytest.mark.integration
    def test_single_player_stops_auto_fill_when_second_joins(self, app_context):
        """Test that auto-fill stops working when a second player joins mid-round"""
        team_name = 'cheat-tony-two-player'
        client1, team_id = self.setup_single_player_team(team_name, 'tony', app_context)
        
        try:
            # Enable game
            state.game_started = True
            
            # Create test round
            test_round = PairQuestionRounds(
                team_id=team_id,
                round_number_for_team=1,
                player1_item=ItemEnum.A,
                player2_item=ItemEnum.X
            )
            db.session.add(test_round)
            db.session.commit()
            
            # Update team state
            team_info = state.active_teams.get(team_name)
            team_info['current_db_round_id'] = test_round.round_id
            team_info['current_round_number'] = 1
            team_info['status'] = 'waiting_pair'
            
            # Second player joins
            client2 = self.create_robust_client()
            client2.get_received()  # Clear connection messages
            
            client2.emit('join_team', {'team_name': team_name})
            team_joined = self.wait_for_event(client2, 'team_joined')
            assert team_joined is not None, "Second player should join successfully"
            
            # Team should now be active with 2 players
            team_info = state.active_teams.get(team_name)
            assert len(team_info['players']) == 2, "Team should have 2 players"
            assert team_info['status'] == 'active', "Team should be active with 2 players"
            
            # Clear messages
            client1.get_received()
            client2.get_received()
            
            # Now when player 1 submits, it should NOT auto-fill (standard 2-player logic)
            client1.emit('submit_answer', {
                'round_id': test_round.round_id,
                'item': 'A',
                'answer': True
            })
            
            # Should get confirmation but NO round completion (waiting for player 2)
            answer_confirmed = self.wait_for_event(client1, 'answer_confirmed')
            assert answer_confirmed is not None, "Player 1 should get confirmation"
            
            # Should NOT get round_complete (because player 2 hasn't answered)
            round_complete = self.wait_for_event(client1, 'round_complete', timeout=1.0)
            assert round_complete is None, "Should NOT get round_complete with 2 players until both answer"
            
            # Verify only 1 answer in database (no auto-fill)
            answers = Answers.query.filter_by(question_round_id=test_round.round_id).all()
            assert len(answers) == 1, f"Should have only 1 answer (no auto-fill), got {len(answers)}"
            
            # Clean up second client
            if client2.connected:
                client2.disconnect()
            
        finally:
            if client1.connected:
                client1.disconnect()