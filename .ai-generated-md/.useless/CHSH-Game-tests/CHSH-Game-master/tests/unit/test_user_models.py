import pytest
from unittest.mock import patch, MagicMock
from src.models.user import User, db

@patch('src.models.user.db')
def test_user_instantiation(mock_db):
    """Test User model creation and attributes"""
    # Create a user
    user = User(
        username="testuser",
        email="test@example.com"
    )
    
    # Check attributes
    assert user.username == "testuser"
    assert user.email == "test@example.com"
    
    # Check id is not set (would be set by database)
    assert user.id is None

@patch('src.models.user.db')
def test_user_repr(mock_db):
    """Test User model's string representation"""
    user = User(username="testuser", email="test@example.com")
    assert str(user) == '<User testuser>'
    assert repr(user) == '<User testuser>'

@patch('src.models.user.db')
def test_user_to_dict(mock_db):
    """Test User model's to_dict method"""
    user = User(username="testuser", email="test@example.com")
    user.id = 1  # Simulate database assignment of ID
    
    expected_dict = {
        'id': 1,
        'username': 'testuser',
        'email': 'test@example.com'
    }
    
    assert user.to_dict() == expected_dict