import pytest
from src.cheats import parse_cheat_type, get_required_parity, recommend_answers
from src.models.quiz_models import ItemEnum


def test_parse_cheat_type_cases():
    assert parse_cheat_type("cheat-com-team") == "com"
    assert parse_cheat_type("CHEAT-HINT foo") == "hint"
    assert parse_cheat_type("cheat-tony") == "tony"
    assert parse_cheat_type("cheat-kevin_bar") == "kevin"
    assert parse_cheat_type("cheater") == "none"
    assert parse_cheat_type("") == "none"
    assert parse_cheat_type(None) == "none"


def test_get_required_parity():
    assert get_required_parity(ItemEnum.B, ItemEnum.Y) == "different"
    assert get_required_parity(ItemEnum.Y, ItemEnum.B) == "different"
    assert get_required_parity(ItemEnum.A, ItemEnum.X) == "same"


def test_recommend_answers_defaults():
    assert recommend_answers("same") == (True, True)
    assert recommend_answers("different") == (True, False)


def test_recommend_answers_with_known():
    assert recommend_answers("same", known_left=True) == (True, True)
    assert recommend_answers("different", known_left=True) == (True, False)
    assert recommend_answers("same", known_right=False) == (False, False)
    assert recommend_answers("different", known_right=False) == (True, False)
