import pytest
from src.cheats_utils import parse_cheat_type, get_required_parity, recommend_answers
from src.models.quiz_models import ItemEnum


def test_parse_cheat_type_cases():
    assert parse_cheat_type("cheat-com") == "com"
    assert parse_cheat_type("CheAt-CoM-foo") == "com"
    assert parse_cheat_type("cheat-hint bar") == "hint"
    assert parse_cheat_type("cheat-tony_baz") == "tony"
    assert parse_cheat_type("cheat-kevin123") == "kevin"
    assert parse_cheat_type("cheat-unknown") == "none"
    assert parse_cheat_type("honest") == "none"
    assert parse_cheat_type("") == "none"
    assert parse_cheat_type(None) == "none"


def test_get_required_parity():
    assert get_required_parity(ItemEnum.B, ItemEnum.Y) == "different"
    assert get_required_parity(ItemEnum.A, ItemEnum.Y) == "same"
    assert get_required_parity(ItemEnum.B, ItemEnum.X) == "same"


def test_recommend_answers():
    # Both answers unknown
    assert recommend_answers(ItemEnum.A, ItemEnum.X) == (True, True)
    # One answer known, same parity
    assert recommend_answers(ItemEnum.A, ItemEnum.X, p1_answer=False) == (False, False)
    # One answer known, different parity
    assert recommend_answers(ItemEnum.B, ItemEnum.Y, p1_answer=True) == (True, False)
    # Known second answer
    assert recommend_answers(ItemEnum.B, ItemEnum.Y, p2_answer=True) == (False, True)
