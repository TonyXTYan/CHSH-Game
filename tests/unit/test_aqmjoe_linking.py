import pytest
from unittest.mock import patch, MagicMock

from src.sockets.dashboard import on_toggle_game_mode, on_set_theme_and_mode


class MockSet:
    def __init__(self, initial=None):
        self._s = set(initial or [])
    def add(self, x):
        self._s.add(x)
    def discard(self, x):
        self._s.discard(x)
    def remove(self, x):
        self._s.remove(x)
    def __contains__(self, x):
        return x in self._s
    def __iter__(self):
        return iter(self._s)
    def __len__(self):
        return len(self._s)


@pytest.fixture
def mock_request():
    mock_req = MagicMock()
    mock_req.sid = 'dash1'
    with patch('src.sockets.dashboard.request', mock_req):
        yield mock_req


@pytest.fixture
def mock_state():
    with patch('src.sockets.dashboard.state') as mock_state:
        mock_state.dashboard_clients = MockSet(['dash1'])
        mock_state.game_mode = 'aqmjoe'
        mock_state.game_theme = 'aqmjoe'
        yield mock_state


@pytest.fixture
def mock_socketio():
    with patch('src.sockets.dashboard.socketio') as mock_io:
        yield mock_io


@pytest.fixture
def mock_emit():
    with patch('src.sockets.dashboard.emit') as mock_emit:
        yield mock_emit


def test_toggle_from_aqmjoe_leaves_theme_unchanged(mock_request, mock_state, mock_socketio, mock_emit):
    # Act: toggle mode while in aqmjoe
    on_toggle_game_mode()

    # Assert state: mode switched to simplified; theme not mutated by toggle handler
    assert mock_state.game_mode == 'simplified'
    # theme remains whatever mock state had (aqmjoe), linking is done via set_theme_and_mode/theme change
    assert mock_state.game_theme == 'aqmjoe'

    # Assert emits include mode change only (legacy behavior expected by other tests)
    mock_socketio.emit.assert_any_call('game_mode_changed', {'mode': 'simplified'})


def test_set_theme_and_mode_enforces_iff_rules(mock_request, mock_state, mock_socketio, mock_emit):
    # Case 1: Any side requests aqmjoe → both aqmjoe
    on_set_theme_and_mode({'theme': 'aqmjoe', 'mode': 'simplified'})
    assert mock_state.game_theme == 'aqmjoe'
    assert mock_state.game_mode == 'aqmjoe'

    on_set_theme_and_mode({'theme': 'food', 'mode': 'aqmjoe'})
    assert mock_state.game_theme == 'aqmjoe'
    assert mock_state.game_mode == 'aqmjoe'

    # Case 2: Neither is aqmjoe → keep as requested
    on_set_theme_and_mode({'theme': 'classic', 'mode': 'simplified'})
    assert mock_state.game_theme == 'classic'
    assert mock_state.game_mode == 'simplified'

    on_set_theme_and_mode({'theme': 'food', 'mode': 'classic'})
    assert mock_state.game_theme == 'food'
    assert mock_state.game_mode == 'classic'

    # Case 3: Alias 'new' → normalized to simplified
    on_set_theme_and_mode({'theme': 'food', 'mode': 'new'})
    assert mock_state.game_theme == 'food'
    assert mock_state.game_mode == 'simplified'

# (Removed duplicate outdated block that expected on_toggle_game_mode to change theme.)

