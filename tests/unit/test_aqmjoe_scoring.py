import pytest
from src.sockets.dashboard import _aqmjoe_label, _is_aqmjoe_success


class TestAqmJoeScoring:
    """Test AQM Joe scoring functions."""
    
    def test_aqmjoe_label_color_questions(self):
        """Test color question labeling (A/B items)."""
        assert _aqmjoe_label('A', True) == 'Green'
        assert _aqmjoe_label('A', False) == 'Red'
        assert _aqmjoe_label('B', True) == 'Green'
        assert _aqmjoe_label('B', False) == 'Red'
    
    def test_aqmjoe_label_food_questions(self):
        """Test food question labeling (X/Y items)."""
        assert _aqmjoe_label('X', True) == 'Peas'
        assert _aqmjoe_label('X', False) == 'Carrots'
        assert _aqmjoe_label('Y', True) == 'Peas'
        assert _aqmjoe_label('Y', False) == 'Carrots'
    
    def test_aqmjoe_success_food_food_rule(self):
        """Test Rule 3: Food-Food never both Peas."""
        # Both food, both Peas -> failure
        assert _is_aqmjoe_success('X', 'Y', True, True) == False
        
        # Both food, one Peas one Carrots -> success
        assert _is_aqmjoe_success('X', 'Y', True, False) == True
        assert _is_aqmjoe_success('X', 'Y', False, True) == True
        
        # Both food, both Carrots -> success
        assert _is_aqmjoe_success('X', 'Y', False, False) == True
    
    def test_aqmjoe_success_mixed_color_food_rule(self):
        """Test Rule 1: Color Green -> Food must be Peas."""
        # Color is Green, Food is Peas -> success
        assert _is_aqmjoe_success('A', 'X', True, True) == True
        assert _is_aqmjoe_success('B', 'Y', True, True) == True
        
        # Color is Green, Food is Carrots -> failure
        assert _is_aqmjoe_success('A', 'X', True, False) == False
        assert _is_aqmjoe_success('B', 'Y', True, False) == False
        
        # Color is Red, Food is Carrots -> success (symmetry rule)
        assert _is_aqmjoe_success('A', 'X', False, False) == True
        assert _is_aqmjoe_success('B', 'Y', False, False) == True
        
        # Color is Red, Food is Peas -> failure
        assert _is_aqmjoe_success('A', 'X', False, True) == False
        assert _is_aqmjoe_success('B', 'Y', False, True) == False
    
    def test_aqmjoe_success_mixed_food_color_rule(self):
        """Test Rule 1 reversed: Food player first, Color player second."""
        # Food is Peas, Color is Green -> success
        assert _is_aqmjoe_success('X', 'A', True, True) == True
        assert _is_aqmjoe_success('Y', 'B', True, True) == True
        
        # Food is Carrots, Color is Red -> success (symmetry)
        assert _is_aqmjoe_success('X', 'A', False, False) == True
        assert _is_aqmjoe_success('Y', 'B', False, False) == True
        
        # Food is Peas, Color is Red -> failure
        assert _is_aqmjoe_success('X', 'A', True, False) == False
        assert _is_aqmjoe_success('Y', 'B', True, False) == False
        
        # Food is Carrots, Color is Green -> failure
        assert _is_aqmjoe_success('X', 'A', False, True) == False
        assert _is_aqmjoe_success('Y', 'B', False, True) == False
    
    def test_aqmjoe_success_color_color_rule(self):
        """Test Rule 2: Color-Color no constraint (always success)."""
        # All combinations should succeed for color-color
        assert _is_aqmjoe_success('A', 'B', True, True) == True
        assert _is_aqmjoe_success('A', 'B', True, False) == True
        assert _is_aqmjoe_success('A', 'B', False, True) == True
        assert _is_aqmjoe_success('A', 'B', False, False) == True
        
        assert _is_aqmjoe_success('B', 'A', True, True) == True
        assert _is_aqmjoe_success('B', 'A', True, False) == True
        assert _is_aqmjoe_success('B', 'A', False, True) == True
        assert _is_aqmjoe_success('B', 'A', False, False) == True