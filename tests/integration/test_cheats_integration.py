import eventlet
eventlet.monkey_patch()  # This must be at the very top

import pytest
import tempfile
import os
from unittest.mock import patch
from src.config import app, db, socketio
from src.state import state
from src.models.quiz_models import Teams, PairQuestionRounds, Answers, ItemEnum
from flask_socketio import SocketIOTestClient
import json


def reset_application_state():
    """Reset the entire application state for clean tests"""
    try:
        with app.app_context():
            # Clear database
            Answers.query.delete()
            PairQuestionRounds.query.delete()
            Teams.query.delete()
            db.session.commit()
            
            # Reset in-memory state
            state.reset()
    except Exception as e:
        raise


@pytest.fixture(autouse=True)
def setup_and_cleanup():
    """Setup and cleanup for each test"""
    reset_application_state()
    yield
    reset_application_state()


@pytest.fixture(scope="session")
def app_context():
    """Create application context for the test session"""
    with app.app_context():
        yield


@pytest.fixture
def socket_client(app_context):
    """Create a test client for SocketIO with proper cleanup"""
    client = None
    try:
        client = SocketIOTestClient(app, socketio)
        yield client
    finally:
        if client and client.connected:
            try:
                client.disconnect()
            except Exception:
                pass


@pytest.fixture
def second_client(app_context):
    """Create a second test client for team interactions"""
    client = None
    try:
        client = SocketIOTestClient(app, socketio)
        yield client
    finally:
        if client and client.connected:
            try:
                client.disconnect()
            except Exception:
                pass


class TestCheatCommunication:
    """Test cheat-com functionality"""
    
    def test_cheat_com_partner_choice_sharing(self, socket_client, second_client):
        """Test that cheat-com teams share partner choices"""
        # Create two socket clients for team members
        client1 = socket_client
        client2 = second_client
        
        # Create cheat-com team
        team_name = "cheat-com-test"
        client1.emit('create_team', {'team_name': team_name})
        client2.emit('join_team', {'team_name': team_name})
        
        # Start game
        state.game_started = True
        
        # Manually create a round for testing
        with app.app_context():
            team_info = state.active_teams[team_name]
            team_id = team_info['team_id']
            
            # Create a round in the database
            round_db = PairQuestionRounds(
                team_id=team_id,
                round_number_for_team=1,
                player1_item=ItemEnum.A,
                player2_item=ItemEnum.X
            )
            db.session.add(round_db)
            db.session.commit()
            
            # Update team state to simulate active round
            team_info['current_round_number'] = 1
            team_info['current_db_round_id'] = round_db.round_id
            team_info['answered_current_round'] = {}
            team_info['status'] = 'active'
            
            # Get player SIDs
            player1_sid = team_info['players'][0]
            player2_sid = team_info['players'][1]
            
            # Player 1 submits answer
            client1.emit('submit_answer', {
                'round_id': round_db.round_id,
                'item': 'A',
                'answer': True
            })
            
            # Check that player 2 received partner choice
            received = client2.get_received()
            partner_choice_events = [r for r in received if r['name'] == 'cheat:partner_choice']
            
            assert len(partner_choice_events) > 0, "Partner choice event should be emitted"
            partner_choice_data = partner_choice_events[0]['args'][0]
            assert partner_choice_data['partnerChoice'] is True
            assert 'at' in partner_choice_data
    
    def test_cheat_com_no_events_for_normal_teams(self, socket_client, second_client):
        """Test that normal teams don't receive cheat events"""
        # Create two socket clients for team members
        client1 = socket_client
        client2 = second_client
        
        # Create normal team (not cheat)
        team_name = "normal-team"
        client1.emit('create_team', {'team_name': team_name})
        client2.emit('join_team', {'team_name': team_name})
        
        # Start game and create round
        state.game_started = True
        
        with app.app_context():
            team_info = state.active_teams[team_name]
            team_id = team_info['team_id']
            
            # Create a round
            round_db = PairQuestionRounds(
                team_id=team_id,
                round_number_for_team=1,
                player1_item=ItemEnum.A,
                player2_item=ItemEnum.X
            )
            db.session.add(round_db)
            db.session.commit()
            
            # Update team state
            team_info['current_round_number'] = 1
            team_info['current_db_round_id'] = round_db.round_id
            team_info['answered_current_round'] = {}
            team_info['status'] = 'active'
            
            # Player 1 submits answer
            client1.emit('submit_answer', {
                'round_id': round_db.round_id,
                'item': 'A',
                'answer': True
            })
            
            # Check that player 2 did NOT receive partner choice
            received = client2.get_received()
            partner_choice_events = [r for r in received if r['name'] == 'cheat:partner_choice']
            
            assert len(partner_choice_events) == 0, "Normal teams should not receive cheat events"


class TestCheatHints:
    """Test cheat-hint functionality"""
    
    def test_cheat_hint_round_start_emission(self, socket_client, second_client):
        """Test that cheat-hint teams receive hints at round start"""
        # Create two socket clients
        client1 = socket_client
        client2 = second_client
        
        # Create cheat-hint team
        team_name = "cheat-hint-test"
        client1.emit('create_team', {'team_name': team_name})
        client2.emit('join_team', {'team_name': team_name})
        
        # Start game
        state.game_started = True
        state.game_mode = 'classic'  # Not AQM Joe
        
        with app.app_context():
            # Trigger round start
            from src.game_logic import start_new_round_for_pair
            start_new_round_for_pair(team_name)
            
            # Check that both players received hints
            received1 = client1.get_received()
            received2 = client2.get_received()
            
            hint_events1 = [r for r in received1 if r['name'] == 'cheat:hint']
            hint_events2 = [r for r in received2 if r['name'] == 'cheat:hint']
            
            assert len(hint_events1) > 0, "Player 1 should receive hint"
            assert len(hint_events2) > 0, "Player 2 should receive hint"
            
            # Check hint data structure
            hint_data1 = hint_events1[0]['args'][0]
            assert 'recommended' in hint_data1
            assert 'parity' in hint_data1
            assert 'reason' in hint_data1
            assert 'at' in hint_data1
            assert hint_data1['parity'] in ['same', 'different']
    
    def test_cheat_hint_updated_after_first_answer(self, socket_client, second_client):
        """Test that hints are updated after first player answers"""
        # Create two socket clients
        client1 = socket_client
        client2 = second_client
        
        # Create cheat-hint team
        team_name = "cheat-hint-test"
        client1.emit('create_team', {'team_name': team_name})
        client2.emit('join_team', {'team_name': team_name})
        
        # Start game
        state.game_started = True
        state.game_mode = 'classic'
        
        with app.app_context():
            # Start round
            from src.game_logic import start_new_round_for_pair
            start_new_round_for_pair(team_name)
            
            # Clear received events
            client1.get_received()
            client2.get_received()
            
            team_info = state.active_teams[team_name]
            round_id = team_info['current_db_round_id']
            
            # Player 1 submits answer
            client1.emit('submit_answer', {
                'round_id': round_id,
                'item': 'A',  # Assuming player 1 got item A
                'answer': True
            })
            
            # Check that player 2 received updated hint
            received2 = client2.get_received()
            hint_events = [r for r in received2 if r['name'] == 'cheat:hint']
            
            assert len(hint_events) > 0, "Player 2 should receive updated hint"
            hint_data = hint_events[0]['args'][0]
            assert 'Updated hint' in hint_data['reason']
    
    def test_cheat_hint_disabled_in_aqmjoe_mode(self, socket_client, second_client):
        """Test that hints are disabled in AQM Joe mode"""
        # Create two socket clients
        client1 = socket_client
        client2 = second_client
        
        # Create cheat-hint team
        team_name = "cheat-hint-test"
        client1.emit('create_team', {'team_name': team_name})
        client2.emit('join_team', {'team_name': team_name})
        
        # Start game in AQM Joe mode
        state.game_started = True
        state.game_mode = 'aqmjoe'
        
        with app.app_context():
            # Start round
            from src.game_logic import start_new_round_for_pair
            start_new_round_for_pair(team_name)
            
            # Check that no hints were emitted
            received1 = client1.get_received()
            received2 = client2.get_received()
            
            hint_events1 = [r for r in received1 if r['name'] == 'cheat:hint']
            hint_events2 = [r for r in received2 if r['name'] == 'cheat:hint']
            
            assert len(hint_events1) == 0, "No hints should be emitted in AQM Joe mode"
            assert len(hint_events2) == 0, "No hints should be emitted in AQM Joe mode"
            
            # But partner choice should still work if they submit answers
            team_info = state.active_teams[team_name]
            round_id = team_info['current_db_round_id']
            
            # Clear received events
            client1.get_received()
            client2.get_received()
            
            # Player 1 submits answer
            client1.emit('submit_answer', {
                'round_id': round_id,
                'item': 'A',
                'answer': True
            })
            
            # Check that partner choice still works
            received2 = client2.get_received()
            partner_choice_events = [r for r in received2 if r['name'] == 'cheat:partner_choice']
            
            assert len(partner_choice_events) > 0, "Partner choice should still work in AQM Joe mode"


class TestCheatParityHelpers:
    """Test the parity and recommendation helper functions"""
    
    def test_get_required_parity(self):
        """Test parity calculation for different item combinations"""
        from src.game_logic import get_required_parity
        
        # BY and YB should require different
        assert get_required_parity(ItemEnum.B, ItemEnum.Y) == "different"
        assert get_required_parity(ItemEnum.Y, ItemEnum.B) == "different"
        
        # All others should require same
        assert get_required_parity(ItemEnum.A, ItemEnum.X) == "same"
        assert get_required_parity(ItemEnum.A, ItemEnum.Y) == "same"
        assert get_required_parity(ItemEnum.B, ItemEnum.X) == "same"
        assert get_required_parity(ItemEnum.X, ItemEnum.A) == "same"
        assert get_required_parity(ItemEnum.A, ItemEnum.A) == "same"
    
    def test_recommend_answers(self):
        """Test answer recommendation logic"""
        from src.game_logic import recommend_answers
        
        # Both unknown, same parity
        p1, p2 = recommend_answers("same", None, None)
        assert p1 == p2, "Same parity should recommend same answers"
        
        # Both unknown, different parity
        p1, p2 = recommend_answers("different", None, None)
        assert p1 != p2, "Different parity should recommend different answers"
        
        # Left known, same parity
        p1, p2 = recommend_answers("same", True, None)
        assert p1 is True and p2 is True, "Same parity with known left True should recommend True for both"
        
        # Left known, different parity
        p1, p2 = recommend_answers("different", True, None)
        assert p1 is True and p2 is False, "Different parity with known left True should recommend False for right"
        
        # Right known, same parity
        p1, p2 = recommend_answers("same", None, False)
        assert p1 is False and p2 is False, "Same parity with known right False should recommend False for both"
        
        # Right known, different parity
        p1, p2 = recommend_answers("different", None, False)
        assert p1 is True and p2 is False, "Different parity with known right False should recommend True for left"
        
        # Both known, return as-is
        p1, p2 = recommend_answers("same", True, False)
        assert p1 is True and p2 is False, "Both known should return as-is regardless of parity"


class TestCheatBanIntegration:
    """Test integration with the cheat ban system from Step 1"""
    
    def test_banned_cheat_teams_cannot_be_created(self, socket_client):
        """Test that cheat teams cannot be created when banned"""
        import time
        
        # Ban cheats
        state.cheats_banned = True
        
        # Try to create cheat team
        client = socket_client
        client.emit('create_team', {'team_name': 'cheat-com-test'})
        
        # Wait a bit for the response
        time.sleep(0.1)
        
        # Should receive error
        received = client.get_received()
        print(f"DEBUG: Received events: {received}")
        error_events = [r for r in received if r['name'] == 'error']
        
        assert len(error_events) > 0, "Should receive error when creating banned cheat team"
        assert 'banned' in error_events[0]['args'][0]['message'].lower()
    
    def test_normal_teams_work_when_cheats_banned(self, socket_client):
        """Test that normal teams still work when cheats are banned"""
        # Ban cheats
        state.cheats_banned = True
        
        # Create normal team
        client = socket_client
        client.emit('create_team', {'team_name': 'normal-team'})
        
        # Should succeed
        received = client.get_received()
        team_created_events = [r for r in received if r['name'] == 'team_created']
        
        assert len(team_created_events) > 0, "Normal teams should work when cheats are banned"
        assert team_created_events[0]['args'][0]['team_name'] == 'normal-team'