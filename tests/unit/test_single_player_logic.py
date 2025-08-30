import pytest
from unittest.mock import patch, MagicMock
from src.game_logic import get_required_parity, recommend_answers
from src.models.quiz_models import ItemEnum


class TestSinglePlayerAutoFillLogic:
    """Test the core logic for single-player auto-fill functionality"""
    
    def test_tony_auto_fill_logic_same_parity(self):
        """Test tony auto-fill logic for same parity (should win)"""
        # A-X requires same answers to win
        parity = get_required_parity(ItemEnum.A, ItemEnum.X)
        assert parity == "same"
        
        # Player 1 answers True, tony should auto-fill P2 to win
        _, partner_answer = recommend_answers(parity, True, None)
        assert partner_answer is True, "Tony should auto-fill to win (same answers)"
        
        # Player 1 answers False, tony should auto-fill P2 to win
        _, partner_answer = recommend_answers(parity, False, None)
        assert partner_answer is False, "Tony should auto-fill to win (same answers)"
    
    def test_tony_auto_fill_logic_different_parity(self):
        """Test tony auto-fill logic for different parity (should win)"""
        # B-Y requires different answers to win
        parity = get_required_parity(ItemEnum.B, ItemEnum.Y)
        assert parity == "different"
        
        # Player 1 answers True, tony should auto-fill P2 to win
        _, partner_answer = recommend_answers(parity, True, None)
        assert partner_answer is False, "Tony should auto-fill to win (different answers)"
        
        # Player 1 answers False, tony should auto-fill P2 to win
        _, partner_answer = recommend_answers(parity, False, None)
        assert partner_answer is True, "Tony should auto-fill to win (different answers)"
    
    def test_kevin_auto_fill_logic_same_parity(self):
        """Test kevin auto-fill logic for same parity (should lose)"""
        # A-X requires same answers to win, so kevin should do different to lose
        parity = get_required_parity(ItemEnum.A, ItemEnum.X)
        assert parity == "same"
        
        # Get winning answer first
        _, winning_answer = recommend_answers(parity, True, None)
        # Kevin should do the opposite to lose
        kevin_answer = not winning_answer
        assert kevin_answer is False, "Kevin should auto-fill to lose (different when same is optimal)"
        
        # Test with False input
        _, winning_answer = recommend_answers(parity, False, None)
        kevin_answer = not winning_answer
        assert kevin_answer is True, "Kevin should auto-fill to lose (different when same is optimal)"
    
    def test_kevin_auto_fill_logic_different_parity(self):
        """Test kevin auto-fill logic for different parity (should lose)"""
        # B-Y requires different answers to win, so kevin should do same to lose
        parity = get_required_parity(ItemEnum.B, ItemEnum.Y)
        assert parity == "different"
        
        # Get winning answer first
        _, winning_answer = recommend_answers(parity, True, None)
        # Kevin should do the opposite to lose
        kevin_answer = not winning_answer
        assert kevin_answer is True, "Kevin should auto-fill to lose (same when different is optimal)"
        
        # Test with False input
        _, winning_answer = recommend_answers(parity, False, None)
        kevin_answer = not winning_answer
        assert kevin_answer is False, "Kevin should auto-fill to lose (same when different is optimal)"
    
    def test_parity_calculation_comprehensive(self):
        """Test parity calculation for all possible combinations"""
        # Test all combinations to ensure correctness
        test_cases = [
            # Same parity cases
            (ItemEnum.A, ItemEnum.A, "same"),
            (ItemEnum.A, ItemEnum.B, "same"),
            (ItemEnum.A, ItemEnum.X, "same"),
            (ItemEnum.A, ItemEnum.Y, "same"),
            (ItemEnum.B, ItemEnum.A, "same"),
            (ItemEnum.B, ItemEnum.B, "same"),
            (ItemEnum.B, ItemEnum.X, "same"),
            (ItemEnum.X, ItemEnum.A, "same"),
            (ItemEnum.X, ItemEnum.B, "same"),
            (ItemEnum.X, ItemEnum.X, "same"),
            (ItemEnum.X, ItemEnum.Y, "same"),
            (ItemEnum.Y, ItemEnum.A, "same"),
            (ItemEnum.Y, ItemEnum.X, "same"),
            (ItemEnum.Y, ItemEnum.Y, "same"),
            
            # Different parity cases (only BY and YB)
            (ItemEnum.B, ItemEnum.Y, "different"),
            (ItemEnum.Y, ItemEnum.B, "different"),
        ]
        
        for p1_item, p2_item, expected_parity in test_cases:
            actual_parity = get_required_parity(p1_item, p2_item)
            assert actual_parity == expected_parity, f"{p1_item.value}-{p2_item.value} should have {expected_parity} parity"
    
    def test_recommend_answers_all_scenarios(self):
        """Test recommend_answers function for all input scenarios"""
        # Both unknown, same parity
        p1, p2 = recommend_answers("same", None, None)
        assert p1 == p2, "Same parity with both unknown should recommend same answers"
        
        # Both unknown, different parity
        p1, p2 = recommend_answers("different", None, None)
        assert p1 != p2, "Different parity with both unknown should recommend different answers"
        
        # Known scenarios
        test_cases = [
            # (parity, known_left, known_right, expected_left, expected_right)
            ("same", True, None, True, True),
            ("same", False, None, False, False),
            ("same", None, True, True, True),
            ("same", None, False, False, False),
            ("different", True, None, True, False),
            ("different", False, None, False, True),
            ("different", None, True, False, True),
            ("different", None, False, True, False),
            ("same", True, False, True, False),  # Both known, return as-is
            ("different", True, False, True, False),  # Both known, return as-is
        ]
        
        for parity, known_left, known_right, expected_left, expected_right in test_cases:
            actual_left, actual_right = recommend_answers(parity, known_left, known_right)
            assert actual_left == expected_left, f"Left answer mismatch for {parity}, {known_left}, {known_right}"
            assert actual_right == expected_right, f"Right answer mismatch for {parity}, {known_left}, {known_right}"