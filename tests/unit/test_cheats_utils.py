import pytest
from src.cheats_utils import parse_cheat_type

@pytest.mark.parametrize(
    "name,expected",
    [
        ("cheat-com", "com"),
        ("cheat-COM-extra", "com"),
        ("cheat-hint foo", "hint"),
        ("cheat-tony_bar", "tony"),
        ("  cheat-kevin  ", "kevin"),
        ("CHEAT-KEVIN-BONUS", "kevin"),
        ("cheat-unknown", "none"),
        ("some team", "none"),
        ("", "none"),
        (None, "none"),
    ],
)
def test_parse_cheat_type(name, expected):
    assert parse_cheat_type(name) == expected
