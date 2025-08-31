import pytest

from src.cheats import parse_cheat_type


@pytest.mark.parametrize(
    'name,expected',
    [
        ('cheat-com', 'com'),
        ('CHEAT-hint-extra', 'hint'),
        ('Cheat-Tony', 'tony'),
        ('cheat-kevin something', 'kevin'),
        ('cheater', 'none'),
        ('', 'none'),
        (None, 'none'),
        ('cheat-unknown', 'none'),
    ],
)
def test_parse_cheat_type(name, expected):
    assert parse_cheat_type(name) == expected
