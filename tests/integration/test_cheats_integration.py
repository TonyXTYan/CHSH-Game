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

class TestCheatsIntegration:
    """Integration tests for cheat functionality with improved SocketIO handling"""
    
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
        
        # Verify connection data structure
        assert 'game_started' in connection_data, "connection_established missing game_started"
        assert 'available_teams' in connection_data, "connection_established missing available_teams"
        
        return client

    def wait_for_event(self, client, event_name, timeout=2.0):
        """Wait for a specific event with improved timing"""
        start_time = time.time()
        while (time.time() - start_time) < timeout:
            eventlet.sleep(0.05)  # Shorter sleep for better responsiveness
            messages = client.get_received()
            for msg in messages:
                if msg.get('name') == event_name:
                    return msg
        return None

    def setup_cheat_team(self, team_name, cheat_type, app_context):
        """Helper to set up a cheat team with proper state management"""
        # Create clients
        client1 = self.create_robust_client()
        client2 = self.create_robust_client()
        
        # Clear any previous messages
        client1.get_received()
        client2.get_received()
        
        # Create team
        client1.emit('create_team', {'team_name': team_name})
        team_created = self.wait_for_event(client1, 'team_created')
        assert team_created is not None, f"Failed to create team {team_name}"
        
        team_data = team_created.get('args', [{}])[0]
        team_id = team_data.get('team_id')
        assert team_id is not None, "Team creation did not return team_id"
        assert team_data.get('cheat_type') == cheat_type, f"Expected cheat_type {cheat_type}, got {team_data.get('cheat_type')}"
        
        # Clear messages after team creation
        client1.get_received()
        client2.get_received()
        
        return client1, client2, team_id

    @pytest.mark.integration
    def test_cheat_com_partner_choice(self, app_context):
        """Test cheat-com functionality: partner choice sharing"""
        team_name = 'cheat-com-test'
        client1, client2, team_id = self.setup_cheat_team(team_name, 'com', app_context)
        
        try:
            # Join second player
            client2.emit('join_team', {'team_name': team_name})
            team_joined = self.wait_for_event(client2, 'team_joined')
            assert team_joined is not None, "Second player failed to join team"
            
            # Clear messages
            client1.get_received()
            client2.get_received()
            
            # Enable game
            state.game_started = True
            
            # Create a test round
            test_round = PairQuestionRounds(
                team_id=team_id,
                round_number_for_team=1,
                player1_item=ItemEnum.A,
                player2_item=ItemEnum.X
            )
            db.session.add(test_round)
            db.session.commit()
            
            # Update team state for the round
            team_info = state.active_teams.get(team_name)
            team_info['current_db_round_id'] = test_round.round_id
            team_info['current_round_number'] = 1
            team_info['status'] = 'active'
            
            # Player 1 submits answer
            client1.emit('submit_answer', {
                'round_id': test_round.round_id,
                'item': 'A',
                'answer': True
            })
            
            # Wait for answer confirmation for player 1
            answer_confirmed = self.wait_for_event(client1, 'answer_confirmed')
            assert answer_confirmed is not None, "Player 1 did not receive answer_confirmed"
            
            # Check if player 2 received partner choice
            # Use longer timeout for cheat events as they may take more time
            partner_choice_event = None
            start_time = time.time()
            while (time.time() - start_time) < 3.0:
                eventlet.sleep(0.05)
                messages = client2.get_received()
                for msg in messages:
                    if msg.get('name') == 'cheat:partner_choice':
                        partner_choice_event = msg
                        break
                if partner_choice_event:
                    break
            
            assert partner_choice_event is not None, "Player 2 did not receive cheat:partner_choice event"
            
            # Verify partner choice data
            choice_data = partner_choice_event.get('args', [{}])[0]
            assert choice_data.get('partnerChoice') is True, f"Expected partnerChoice True, got {choice_data.get('partnerChoice')}"
            assert 'at' in choice_data, "Partner choice event missing timestamp"
            
        finally:
            # Clean up clients
            if client1.connected:
                client1.disconnect()
            if client2.connected:
                client2.disconnect()

    @pytest.mark.integration
    def test_cheat_hint_functionality(self, app_context):
        """Test cheat-hint functionality: hints at round start and after first answer"""
        team_name = 'cheat-hint-test'
        client1, client2, team_id = self.setup_cheat_team(team_name, 'hint', app_context)
        
        try:
            # Join second player
            client2.emit('join_team', {'team_name': team_name})
            team_joined = self.wait_for_event(client2, 'team_joined')
            assert team_joined is not None, "Second player failed to join team"
            
            # Clear messages
            client1.get_received()
            client2.get_received()
            
            # Enable game
            state.game_started = True
            
            # Start a new round (this should trigger hints for hint teams)
            from src.game_logic import start_new_round_for_pair
            start_new_round_for_pair(team_name)
            
            # Collect all events after round start (should include new_question and cheat:hint)
            all_events_1 = []
            all_events_2 = []
            start_time = time.time()
            while (time.time() - start_time) < 5.0:  # Extended timeout
                eventlet.sleep(0.1)
                
                messages_1 = client1.get_received()
                messages_2 = client2.get_received()
                all_events_1.extend(messages_1)
                all_events_2.extend(messages_2)
                
                # Check if we have both new_question and cheat:hint
                new_question_1 = next((msg for msg in all_events_1 if msg.get('name') == 'new_question'), None)
                new_question_2 = next((msg for msg in all_events_2 if msg.get('name') == 'new_question'), None)
                hint_event_1 = next((msg for msg in all_events_1 if msg.get('name') == 'cheat:hint'), None)
                hint_event_2 = next((msg for msg in all_events_2 if msg.get('name') == 'cheat:hint'), None)
                
                if new_question_1 and new_question_2 and hint_event_1 and hint_event_2:
                    break
            
            # Verify new_question events were received
            assert new_question_1 is not None, f"Player 1 did not receive new_question. Events: {[msg.get('name') for msg in all_events_1]}"
            assert new_question_2 is not None, f"Player 2 did not receive new_question. Events: {[msg.get('name') for msg in all_events_2]}"
            
            # Verify hints were received (unless in AQM Joe mode)
            if state.game_mode != 'aqmjoe':
                assert hint_event_1 is not None, f"Player 1 did not receive initial cheat:hint. Events: {[msg.get('name') for msg in all_events_1]}"
                assert hint_event_2 is not None, f"Player 2 did not receive initial cheat:hint. Events: {[msg.get('name') for msg in all_events_2]}"
                
                # Verify hint data structure
                hint_data_1 = hint_event_1.get('args', [{}])[0]
                assert 'recommended' in hint_data_1, "Hint missing recommended field"
                assert 'parity' in hint_data_1, "Hint missing parity field"
                assert 'reason' in hint_data_1, "Hint missing reason field"
                assert 'at' in hint_data_1, "Hint missing timestamp"
            
        finally:
            # Clean up clients
            if client1.connected:
                client1.disconnect()
            if client2.connected:
                client2.disconnect()

    @pytest.mark.integration
    def test_cheat_ban_functionality(self, app_context):
        """Test the cheat ban toggle functionality"""
        # Create a cheat team first
        team_name = 'cheat-com-banned'
        client1, client2, team_id = self.setup_cheat_team(team_name, 'com', app_context)
        
        try:
            # Join second player
            client2.emit('join_team', {'team_name': team_name})
            team_joined = self.wait_for_event(client2, 'team_joined')
            assert team_joined is not None, "Second player failed to join team"
            
            # Verify team is active
            assert team_name in state.active_teams, "Cheat team should be active before ban"
            
            # Create dashboard client
            dashboard_client = SocketIOTestClient(app, server_socketio)
            eventlet.sleep(0.2)  # Allow connection to establish
            dashboard_client.get_received()  # Clear connection messages
            
            # Join as dashboard client
            dashboard_client.emit('dashboard_join')
            eventlet.sleep(0.2)  # Allow dashboard join to complete
            dashboard_client.get_received()  # Clear dashboard join messages
            
            # Enable cheat ban
            dashboard_client.emit('dashboard:toggle_cheats_ban', {'banned': True})
            
            # Wait for ban change event
            ban_event = None
            start_time = time.time()
            while (time.time() - start_time) < 3.0:
                eventlet.sleep(0.05)
                messages = dashboard_client.get_received()
                for msg in messages:
                    if msg.get('name') == 'cheats_ban_changed':
                        ban_event = msg
                        break
                if ban_event:
                    break
            
            assert ban_event is not None, "Dashboard did not receive cheats_ban_changed event"
            
            # Verify ban data
            ban_data = ban_event.get('args', [{}])[0]
            assert ban_data.get('banned') is True, "Ban should be enabled"
            assert ban_data.get('kicked_teams', 0) >= 1, "Should have kicked at least one team"
            
            # Verify cheat team was kicked
            assert state.cheats_banned is True, "Global ban state should be enabled"
            
            # Try to create a new cheat team (should be blocked)
            new_client = SocketIOTestClient(app, server_socketio)
            eventlet.sleep(0.2)
            new_client.get_received()  # Clear connection messages
            
            new_client.emit('create_team', {'team_name': 'cheat-hint-blocked'})
            
            # Should receive error
            error_event = self.wait_for_event(new_client, 'error')
            assert error_event is not None, "Should receive error when creating cheat team while banned"
            
            error_data = error_event.get('args', [{}])[0]
            assert 'banned' in error_data.get('message', '').lower(), "Error message should mention ban"
            
            # Clean up dashboard client
            dashboard_client.disconnect()
            new_client.disconnect()
            
        finally:
            # Clean up clients
            if client1.connected:
                client1.disconnect()
            if client2.connected:
                client2.disconnect()

    @pytest.mark.integration 
    def test_non_cheat_team_unaffected(self, app_context):
        """Test that non-cheat teams are completely unaffected by cheat functionality"""
        team_name = 'normal-team'
        
        # Create normal team
        client1 = self.create_robust_client()
        client2 = self.create_robust_client()
        
        try:
            # Clear initial messages
            client1.get_received()
            client2.get_received()
            
            # Create team
            client1.emit('create_team', {'team_name': team_name})
            team_created = self.wait_for_event(client1, 'team_created')
            assert team_created is not None, "Failed to create normal team"
            
            team_data = team_created.get('args', [{}])[0]
            team_id = team_data.get('team_id')
            assert team_data.get('cheat_type') == 'none', "Normal team should have cheat_type 'none'"
            
            # Join second player
            client1.get_received()  # Clear messages
            client2.emit('join_team', {'team_name': team_name})
            team_joined = self.wait_for_event(client2, 'team_joined')
            assert team_joined is not None, "Second player failed to join normal team"
            
            # Clear messages
            client1.get_received()
            client2.get_received()
            
            # Enable game
            state.game_started = True
            
            # Create a test round
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
            team_info['status'] = 'active'
            
            # Player 1 submits answer
            client1.emit('submit_answer', {
                'round_id': test_round.round_id,
                'item': 'A',
                'answer': True
            })
            
            # Wait for answer confirmation
            answer_confirmed = self.wait_for_event(client1, 'answer_confirmed')
            assert answer_confirmed is not None, "Player 1 should receive answer_confirmed"
            
            # Verify NO cheat events were sent to either player
            all_messages_1 = client1.get_received()
            all_messages_2 = client2.get_received()
            
            # Check that no cheat events were received
            cheat_events_1 = [msg for msg in all_messages_1 if msg.get('name', '').startswith('cheat:')]
            cheat_events_2 = [msg for msg in all_messages_2 if msg.get('name', '').startswith('cheat:')]
            
            assert len(cheat_events_1) == 0, f"Normal team player 1 should not receive cheat events, got: {cheat_events_1}"
            assert len(cheat_events_2) == 0, f"Normal team player 2 should not receive cheat events, got: {cheat_events_2}"
            
        finally:
            # Clean up clients
            if client1.connected:
                client1.disconnect()
            if client2.connected:
                client2.disconnect()