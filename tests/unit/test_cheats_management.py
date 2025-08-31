import pytest
from unittest.mock import patch, ANY
from flask import request
from src.config import app, socketio, db
from src.state import state


@pytest.fixture
def app_context():
    with app.app_context():
        app.extensions['socketio'] = socketio
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def mock_request_context(app_context):
    ctx = app_context.test_request_context('/')
    ctx.push()
    request.sid = 'sid1'
    request.namespace = '/'
    yield request
    ctx.pop()


@pytest.fixture(autouse=True)
def cleanup_state():
    state.reset()
    yield
    state.reset()


def test_create_cheat_team_stores_type(mock_request_context):
    from src.sockets.team_management import on_create_team
    with patch('src.sockets.team_management.emit') as mock_emit, \
         patch('src.sockets.team_management.socketio.emit'), \
         patch('src.sockets.team_management.join_room'):
        on_create_team({'team_name': 'cheat-com-foo'})
        assert state.active_teams['cheat-com-foo']['cheat_type'] == 'com'
        mock_emit.assert_any_call('team_created', ANY)


def test_create_cheat_team_rejected_when_banned(mock_request_context):
    from src.sockets.team_management import on_create_team
    state.cheats_banned = True
    with patch('src.sockets.team_management.emit') as mock_emit, \
         patch('src.sockets.team_management.join_room'):
        on_create_team({'team_name': 'cheat-hint-bar'})
        assert 'cheat-hint-bar' not in state.active_teams
        args, kwargs = mock_emit.call_args
        assert args[0] == 'error'
        assert 'Cheats' in args[1]['message']


