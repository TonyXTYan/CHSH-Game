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
from src.game_logic import get_required_parity, recommend_answers


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


class TestSinglePlayerTonyAutoComplete:
    """Test cheat-tony single-player auto-complete functionality"""
    
    def test_tony_team_single_player_auto_win(self, socket_client):
        """Test that single-player tony team auto-completes to win"""
        # Create single-player tony team
        client = socket_client
        team_name = "cheat-tony-test"
        client.emit('create_team', {'team_name': team_name})
        
        # Start game
        state.game_started = True
        
        with app.app_context():
            # Manually create a round for testing
            team_info = state.active_teams[team_name]
            team_id = team_info['team_id']
            
            # Create round with specific items for predictable parity
            round_db = PairQuestionRounds(
                team_id=team_id,
                round_number_for_team=1,
                player1_item=ItemEnum.A,  # A-X requires same answers to win
                player2_item=ItemEnum.X
            )
            db.session.add(round_db)
            db.session.commit()
            
            # Update team state
            team_info['current_round_number'] = 1
            team_info['current_db_round_id'] = round_db.round_id
            team_info['answered_current_round'] = {}
            team_info['status'] = 'waiting_pair'  # Single player team
            
            # Player submits answer
            client.emit('submit_answer', {
                'round_id': round_db.round_id,
                'item': 'A',
                'answer': True
            })
            
            # Check that partner answer was auto-filled to win
            answers = Answers.query.filter_by(question_round_id=round_db.round_id).all()
            assert len(answers) == 2, "Should have 2 answers after auto-fill"
            
            # Find the auto-filled answer
            player_answer = None
            auto_answer = None
            for answer in answers:
                if answer.player_session_id.startswith('auto_'):
                    auto_answer = answer
                else:
                    player_answer = answer
            
            assert player_answer is not None, "Player answer should exist"
            assert auto_answer is not None, "Auto-filled answer should exist"
            
            # Verify the auto-fill creates a winning combination
            parity = get_required_parity(round_db.player1_item, round_db.player2_item)
            assert parity == "same", "A-X should require same answers"
            
            # For tony (auto-win), partner answer should match player answer
            assert auto_answer.response_value == player_answer.response_value, "Tony should auto-fill to win (same answers for A-X)"
    
    def test_tony_team_different_parity_auto_win(self, socket_client):
        """Test tony team auto-win with different parity requirement"""
        # Create single-player tony team
        client = socket_client
        team_name = "cheat-tony-test"
        client.emit('create_team', {'team_name': team_name})
        
        # Start game
        state.game_started = True
        
        with app.app_context():
            team_info = state.active_teams[team_name]
            team_id = team_info['team_id']
            
            # Create round with B-Y which requires different answers to win
            round_db = PairQuestionRounds(
                team_id=team_id,
                round_number_for_team=1,
                player1_item=ItemEnum.B,
                player2_item=ItemEnum.Y
            )
            db.session.add(round_db)
            db.session.commit()
            
            # Update team state
            team_info['current_round_number'] = 1
            team_info['current_db_round_id'] = round_db.round_id
            team_info['answered_current_round'] = {}
            team_info['status'] = 'waiting_pair'
            
            # Player submits answer
            client.emit('submit_answer', {
                'round_id': round_db.round_id,
                'item': 'B',
                'answer': True
            })
            
            # Check auto-fill
            answers = Answers.query.filter_by(question_round_id=round_db.round_id).all()
            assert len(answers) == 2, "Should have 2 answers after auto-fill"
            
            # Find answers
            player_answer = None
            auto_answer = None
            for answer in answers:
                if answer.player_session_id.startswith('auto_'):
                    auto_answer = answer
                else:
                    player_answer = answer
            
            # Verify auto-fill for different parity (B-Y requires different to win)
            parity = get_required_parity(round_db.player1_item, round_db.player2_item)
            assert parity == "different", "B-Y should require different answers"
            
            # For tony with different parity, partner should have opposite answer
            assert auto_answer.response_value != player_answer.response_value, "Tony should auto-fill to win (different answers for B-Y)"


class TestSinglePlayerKevinAutoComplete:
    """Test cheat-kevin single-player auto-complete functionality"""
    
    def test_kevin_team_single_player_auto_lose(self, socket_client):
        """Test that single-player kevin team auto-completes to lose"""
        # Create single-player kevin team
        client = socket_client
        team_name = "cheat-kevin-test"
        client.emit('create_team', {'team_name': team_name})
        
        # Start game
        state.game_started = True
        
        with app.app_context():
            team_info = state.active_teams[team_name]
            team_id = team_info['team_id']
            
            # Create round with A-X (requires same answers to win)
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
            team_info['status'] = 'waiting_pair'
            
            # Player submits answer
            client.emit('submit_answer', {
                'round_id': round_db.round_id,
                'item': 'A',
                'answer': True
            })
            
            # Check auto-fill
            answers = Answers.query.filter_by(question_round_id=round_db.round_id).all()
            assert len(answers) == 2, "Should have 2 answers after auto-fill"
            
            # Find answers
            player_answer = None
            auto_answer = None
            for answer in answers:
                if answer.player_session_id.startswith('auto_'):
                    auto_answer = answer
                else:
                    player_answer = answer
            
            # Verify auto-fill for kevin (should lose)
            parity = get_required_parity(round_db.player1_item, round_db.player2_item)
            assert parity == "same", "A-X should require same answers to win"
            
            # For kevin, should auto-fill to lose (opposite of winning strategy)
            assert auto_answer.response_value != player_answer.response_value, "Kevin should auto-fill to lose (different answers when same is optimal)"
    
    def test_kevin_team_different_parity_auto_lose(self, socket_client):
        """Test kevin team auto-lose with different parity requirement"""
        # Create single-player kevin team
        client = socket_client
        team_name = "cheat-kevin-test"
        client.emit('create_team', {'team_name': team_name})
        
        # Start game
        state.game_started = True
        
        with app.app_context():
            team_info = state.active_teams[team_name]
            team_id = team_info['team_id']
            
            # Create round with B-Y (requires different answers to win)
            round_db = PairQuestionRounds(
                team_id=team_id,
                round_number_for_team=1,
                player1_item=ItemEnum.B,
                player2_item=ItemEnum.Y
            )
            db.session.add(round_db)
            db.session.commit()
            
            # Update team state
            team_info['current_round_number'] = 1
            team_info['current_db_round_id'] = round_db.round_id
            team_info['answered_current_round'] = {}
            team_info['status'] = 'waiting_pair'
            
            # Player submits answer
            client.emit('submit_answer', {
                'round_id': round_db.round_id,
                'item': 'B',
                'answer': False
            })
            
            # Check auto-fill
            answers = Answers.query.filter_by(question_round_id=round_db.round_id).all()
            assert len(answers) == 2, "Should have 2 answers after auto-fill"
            
            # Find answers
            player_answer = None
            auto_answer = None
            for answer in answers:
                if answer.player_session_id.startswith('auto_'):
                    auto_answer = answer
                else:
                    player_answer = answer
            
            # Verify auto-fill for kevin with different parity
            parity = get_required_parity(round_db.player1_item, round_db.player2_item)
            assert parity == "different", "B-Y should require different answers to win"
            
            # For kevin with different parity, should auto-fill to lose (same when different is optimal)
            assert auto_answer.response_value == player_answer.response_value, "Kevin should auto-fill to lose (same answers when different is optimal)"


class TestSinglePlayerEdgeCases:
    """Test edge cases for single-player auto-complete"""
    
    def test_no_auto_fill_when_second_player_present(self, socket_client):
        """Test that auto-fill doesn't happen when second player is present"""
        # Create tony team with two players
        client1 = socket_client
        client2 = SocketIOTestClient(app, socketio)
        
        team_name = "cheat-tony-test"
        client1.emit('create_team', {'team_name': team_name})
        client2.emit('join_team', {'team_name': team_name})
        
        # Start game
        state.game_started = True
        
        with app.app_context():
            team_info = state.active_teams[team_name]
            team_id = team_info['team_id']
            
            # Create round
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
            team_info['status'] = 'active'  # Two players = active
            
            # Player 1 submits answer
            client1.emit('submit_answer', {
                'round_id': round_db.round_id,
                'item': 'A',
                'answer': True
            })
            
            # Should NOT auto-fill because two players are present
            answers = Answers.query.filter_by(question_round_id=round_db.round_id).all()
            assert len(answers) == 1, "Should have only 1 answer when two players present"
            
            # The single answer should be from the real player, not auto-filled
            answer = answers[0]
            assert not answer.player_session_id.startswith('auto_'), "Should not auto-fill when two players present"
    
    def test_concurrent_submission_safety(self, socket_client):
        """Test that concurrent submissions are handled safely"""
        # This test verifies the database consistency safeguards
        client = socket_client
        team_name = "cheat-tony-test"
        client.emit('create_team', {'team_name': team_name})
        
        # Start game
        state.game_started = True
        
        with app.app_context():
            team_info = state.active_teams[team_name]
            team_id = team_info['team_id']
            
            # Create round
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
            team_info['status'] = 'waiting_pair'
            
            # Manually create a second answer to simulate concurrent submission
            existing_answer = Answers(
                team_id=team_id,
                player_session_id='other_player',
                question_round_id=round_db.round_id,
                assigned_item=ItemEnum.X,
                response_value=False
            )
            db.session.add(existing_answer)
            db.session.commit()
            
            # Now submit from the client
            client.emit('submit_answer', {
                'round_id': round_db.round_id,
                'item': 'A',
                'answer': True
            })
            
            # Should not auto-fill because partner answer already exists
            answers = Answers.query.filter_by(question_round_id=round_db.round_id).all()
            assert len(answers) == 2, "Should have exactly 2 answers"
            
            # No auto-filled answer should be created
            auto_answers = [a for a in answers if a.player_session_id.startswith('auto_')]
            assert len(auto_answers) == 0, "Should not auto-fill when partner answer already exists"


class TestSinglePlayerDatabaseConsistency:
    """Test database consistency for single-player auto-complete"""
    
    def test_max_two_answers_per_round(self, socket_client):
        """Test that at most two answers are created per round"""
        client = socket_client
        team_name = "cheat-tony-test"
        client.emit('create_team', {'team_name': team_name})
        
        # Start game
        state.game_started = True
        
        with app.app_context():
            team_info = state.active_teams[team_name]
            team_id = team_info['team_id']
            
            # Create round
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
            team_info['status'] = 'waiting_pair'
            
            # Submit answer
            client.emit('submit_answer', {
                'round_id': round_db.round_id,
                'item': 'A',
                'answer': True
            })
            
            # Verify exactly 2 answers exist
            answers = Answers.query.filter_by(question_round_id=round_db.round_id).all()
            assert len(answers) == 2, "Should have exactly 2 answers"
            
            # Verify one PairQuestionRounds entry
            rounds = PairQuestionRounds.query.filter_by(team_id=team_id).all()
            assert len(rounds) == 1, "Should have exactly 1 round entry"
    
    def test_round_completion_triggers_after_auto_fill(self, socket_client):
        """Test that round completion logic works with auto-filled answers"""
        client = socket_client
        team_name = "cheat-tony-test"
        client.emit('create_team', {'team_name': team_name})
        
        # Start game
        state.game_started = True
        
        with app.app_context():
            team_info = state.active_teams[team_name]
            team_id = team_info['team_id']
            
            # Create round
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
            team_info['status'] = 'waiting_pair'
            
            # Submit answer
            client.emit('submit_answer', {
                'round_id': round_db.round_id,
                'item': 'A',
                'answer': True
            })
            
            # Check that round completion was triggered
            received = client.get_received()
            round_complete_events = [r for r in received if r['name'] == 'round_complete']
            
            assert len(round_complete_events) > 0, "Round completion should be triggered after auto-fill"
            
            # Verify round completion data
            round_data = round_complete_events[0]['args'][0]
            assert round_data['team_name'] == team_name
            assert round_data['round_number'] == 1
            assert 'last_round_details' in round_data