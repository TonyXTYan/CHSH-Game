"""
Unit tests for AQM Joe theme functionality.
"""
import pytest
import sys
import os
from unittest.mock import patch, MagicMock

# Add the src directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from sockets.dashboard import _aqmjoe_label, _is_aqmjoe_success


class TestAqmJoeTheme:
    """Tests for AQM Joe theme functions."""
    
    def test_aqmjoe_label_color_questions(self):
        """Test _aqmjoe_label for color questions (A, B)."""
        assert _aqmjoe_label('A', True) == 'Green'
        assert _aqmjoe_label('A', False) == 'Red'
        assert _aqmjoe_label('B', True) == 'Green'
        assert _aqmjoe_label('B', False) == 'Red'
    
    def test_aqmjoe_label_food_questions(self):
        """Test _aqmjoe_label for food questions (X, Y)."""
        assert _aqmjoe_label('X', True) == 'Peas'
        assert _aqmjoe_label('X', False) == 'Carrots'
        assert _aqmjoe_label('Y', True) == 'Peas'
        assert _aqmjoe_label('Y', False) == 'Carrots'
    
    def test_aqmjoe_success_food_food_combinations(self):
        """Test _is_aqmjoe_success for Food-Food combinations."""
        # Rule: success if NOT both "Peas"
        assert _is_aqmjoe_success('X', 'Y', True, True) == False  # Both Peas
        assert _is_aqmjoe_success('X', 'Y', True, False) == True  # Peas-Carrots
        assert _is_aqmjoe_success('X', 'Y', False, True) == True  # Carrots-Peas
        assert _is_aqmjoe_success('X', 'Y', False, False) == True  # Both Carrots
        
        # Test with reversed order
        assert _is_aqmjoe_success('Y', 'X', True, True) == False  # Both Peas
        assert _is_aqmjoe_success('Y', 'X', True, False) == True  # Peas-Carrots
    
    def test_aqmjoe_success_color_food_combinations(self):
        """Test _is_aqmjoe_success for Color-Food combinations."""
        # Rule: Green → Peas (success), Red → Carrots (success with symmetry)
        
        # Player 1 has color, Player 2 has food
        assert _is_aqmjoe_success('A', 'X', True, True) == True   # Green-Peas
        assert _is_aqmjoe_success('A', 'X', True, False) == False # Green-Carrots
        assert _is_aqmjoe_success('A', 'X', False, True) == False # Red-Peas
        assert _is_aqmjoe_success('A', 'X', False, False) == True # Red-Carrots
        
        # Player 2 has color, Player 1 has food
        assert _is_aqmjoe_success('X', 'A', True, True) == True   # Peas-Green
        assert _is_aqmjoe_success('X', 'A', False, True) == False # Carrots-Green
        assert _is_aqmjoe_success('X', 'A', True, False) == False # Peas-Red
        assert _is_aqmjoe_success('X', 'A', False, False) == True # Carrots-Red
        
        # Test with B and Y
        assert _is_aqmjoe_success('B', 'Y', True, True) == True   # Green-Peas
        assert _is_aqmjoe_success('B', 'Y', False, False) == True # Red-Carrots
    
    def test_aqmjoe_success_color_color_combinations(self):
        """Test _is_aqmjoe_success for Color-Color combinations."""
        # Rule: always successful (neutral for success rate)
        assert _is_aqmjoe_success('A', 'B', True, True) == True
        assert _is_aqmjoe_success('A', 'B', True, False) == True
        assert _is_aqmjoe_success('A', 'B', False, True) == True
        assert _is_aqmjoe_success('A', 'B', False, False) == True
        
        # Test same items
        assert _is_aqmjoe_success('A', 'A', True, False) == True
        assert _is_aqmjoe_success('B', 'B', False, True) == True

    @patch('src.state.state')
    def test_aqmjoe_success_integration_with_new_mode(self, mock_state):
        """Test that AQM Joe success logic is used when theme is aqmjoe and mode is new."""
        # This is more of an integration test to verify the logic paths
        mock_state.game_mode = 'new'
        mock_state.game_theme = 'aqmjoe'
        
        # Test specific AQM Joe scenarios
        test_cases = [
            # (p1_item, p2_item, p1_answer, p2_answer, expected_success)
            ('X', 'Y', True, True, False),   # Food-Food, both Peas (fail)
            ('X', 'Y', True, False, True),   # Food-Food, Peas-Carrots (success)
            ('A', 'X', True, True, True),    # Color-Food, Green-Peas (success)
            ('A', 'X', True, False, False),  # Color-Food, Green-Carrots (fail)
            ('A', 'X', False, False, True),  # Color-Food, Red-Carrots (success)
            ('A', 'B', True, False, True),   # Color-Color (always success)
        ]
        
        for p1_item, p2_item, p1_answer, p2_answer, expected in test_cases:
            result = _is_aqmjoe_success(p1_item, p2_item, p1_answer, p2_answer)
            assert result == expected, f"Failed for {p1_item}-{p2_item}, {p1_answer}-{p2_answer}: expected {expected}, got {result}"

    def test_aqmjoe_constraints_specification_compliance(self):
        """Test that the implementation follows the specific constraints from the design document."""
        
        # Constraint 1: If one answers "green" then the other always answers "peas", if the food question is asked
        # Testing Color→Food constraint
        assert _is_aqmjoe_success('A', 'X', True, True) == True   # Green→Peas (correct)
        assert _is_aqmjoe_success('A', 'X', True, False) == False # Green→Carrots (violates constraint)
        assert _is_aqmjoe_success('B', 'Y', True, True) == True   # Green→Peas (correct) 
        assert _is_aqmjoe_success('B', 'Y', True, False) == False # Green→Carrots (violates constraint)
        
        # Testing Food→Color constraint (symmetric)
        assert _is_aqmjoe_success('X', 'A', True, True) == True   # Peas→Green (correct)
        assert _is_aqmjoe_success('X', 'A', True, False) == False # Peas→Red (violates constraint)
        
        # Constraint 2: When both are asked the colour question, sometimes both answer "green"
        # This should be allowed (always successful for Color-Color pairs)
        assert _is_aqmjoe_success('A', 'B', True, True) == True   # Both Green (allowed)
        assert _is_aqmjoe_success('A', 'B', False, False) == True # Both Red (allowed)
        assert _is_aqmjoe_success('A', 'B', True, False) == True  # Green-Red (allowed)
        
        # Constraint 3: If both are asked the food question they never both answer "peas"
        assert _is_aqmjoe_success('X', 'Y', True, True) == False  # Both Peas (violates constraint)
        assert _is_aqmjoe_success('X', 'Y', True, False) == True  # Peas-Carrots (allowed)
        assert _is_aqmjoe_success('X', 'Y', False, True) == True  # Carrots-Peas (allowed)
        assert _is_aqmjoe_success('X', 'Y', False, False) == True # Both Carrots (allowed)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])