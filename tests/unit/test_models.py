import pytest
from unittest.mock import patch, MagicMock
from src.models.quiz_models import ItemEnum, Teams, Answers, PairQuestionRounds, db

def test_item_enum():
    """Test ItemEnum values"""
    assert ItemEnum.A.value == 'A'
    assert ItemEnum.B.value == 'B'
    assert ItemEnum.X.value == 'X'
    assert ItemEnum.Y.value == 'Y'
    
    # Test enum conversion
    assert ItemEnum('A') == ItemEnum.A
    assert ItemEnum('B') == ItemEnum.B
    assert ItemEnum('X') == ItemEnum.X
    assert ItemEnum('Y') == ItemEnum.Y
    
    # Test invalid enum value
    with pytest.raises(ValueError):
        ItemEnum('Z')

@patch('src.models.quiz_models.db')
def test_teams_model(mock_db):
    """Test Teams model creation and attributes"""
    # Create a team
    team = Teams(
        team_name="Test Team",
        player1_session_id="player1_sid",
        player2_session_id="player2_sid",
        is_active=True
    )
    
    # Check attributes
    assert team.team_name == "Test Team"
    assert team.player1_session_id == "player1_sid"
    assert team.player2_session_id == "player2_sid"
    assert team.is_active is True
    
    # Check default values
    assert hasattr(team, 'created_at')
    
    # Check relationships
    assert hasattr(team, 'rounds')

@patch('src.models.quiz_models.db')
def test_answers_model(mock_db):
    """Test Answers model creation and attributes"""
    # Create an answer
    answer = Answers(
        team_id=1,
        player_session_id="player_sid",
        question_round_id=1,
        assigned_item=ItemEnum.A,
        response_value=True
    )
    
    # Check attributes
    assert answer.team_id == 1
    assert answer.player_session_id == "player_sid"
    assert answer.question_round_id == 1
    assert answer.assigned_item == ItemEnum.A
    assert answer.response_value is True
    
    # Check default values
    assert hasattr(answer, 'timestamp')

@patch('src.models.quiz_models.db')
def test_pair_question_rounds_model(mock_db):
    """Test PairQuestionRounds model creation and attributes"""
    # Create a round
    round_obj = PairQuestionRounds(
        team_id=1,
        round_number_for_team=1,
        player1_item=ItemEnum.A,
        player2_item=ItemEnum.B
    )
    
    # Check attributes
    assert round_obj.team_id == 1
    assert round_obj.round_number_for_team == 1
    assert round_obj.player1_item == ItemEnum.A
    assert round_obj.player2_item == ItemEnum.B
    
    # Check default values
    assert hasattr(round_obj, 'timestamp_initiated')
    assert round_obj.p1_answered_at is None
    assert round_obj.p2_answered_at is None
    
    # Check relationships
    assert hasattr(round_obj, 'answers')

def test_model_relationships():
    """Test relationships between models"""
    # Create a minimal Flask app for testing
    from flask import Flask
    
    app = Flask(__name__)
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # Initialize the database with the app
    with app.app_context():
        db.init_app(app)
        
        # Create mock objects that can work within the application context
        team = MagicMock(spec=Teams)
        team.team_id = 1
        team.rounds = []
        
        round_obj = MagicMock(spec=PairQuestionRounds)
        round_obj.round_id = 1
        round_obj.team_id = 1
        round_obj.team = team
        round_obj.answers = []
        
        answer = MagicMock(spec=Answers)
        answer.answer_id = 1
        answer.team_id = 1
        answer.question_round_id = 1
        answer.round = round_obj
        
        # Set up relationships
        team.rounds.append(round_obj)
        round_obj.answers.append(answer)
        
        # Test relationships
        assert round_obj in team.rounds
        assert answer in round_obj.answers
        assert answer.round == round_obj
        assert round_obj.team == team
