import eventlet

# Patch sockets for eventlet
eventlet.monkey_patch()

import pytest
from flask_socketio import SocketIOTestClient
from src.config import app, socketio as server_socketio
from src.state import state
from src.models.quiz_models import Teams, PairQuestionRounds, Answers, db


def reset_application_state():
    with app.app_context():
        Answers.query.delete()
        PairQuestionRounds.query.delete()
        Teams.query.delete()
        db.session.commit()
    state.reset()


def test_cheat_team_creation_parses_type():
    reset_application_state()
    client = SocketIOTestClient(app, server_socketio)
    client.emit("create_team", {"team_name": "cheat-com-foo"})
    eventlet.sleep(0)
    assert "cheat-com-foo" in state.active_teams
    assert state.active_teams["cheat-com-foo"]["cheat_type"] == "com"
    client.disconnect()


def test_cheats_banned_blocks_cheat_teams():
    reset_application_state()
    state.cheats_banned = True
    client = SocketIOTestClient(app, server_socketio)
    client.emit("create_team", {"team_name": "cheat-hint-team"})
    eventlet.sleep(0)
    messages = client.get_received()
    assert any(m["name"] == "error" for m in messages)

    # Non-cheat team should still be allowed
    client.emit("create_team", {"team_name": "honest-team"})
    eventlet.sleep(0)
    assert "honest-team" in state.active_teams
    client.disconnect()

    # Ban also blocks joining existing cheat teams
    reset_application_state()
    client1 = SocketIOTestClient(app, server_socketio)
    client1.emit("create_team", {"team_name": "cheat-tony-foo"})
    eventlet.sleep(0)
    assert "cheat-tony-foo" in state.active_teams
    state.cheats_banned = True
    client2 = SocketIOTestClient(app, server_socketio)
    client2.emit("join_team", {"team_name": "cheat-tony-foo"})
    eventlet.sleep(0)
    messages = client2.get_received()
    assert any(m["name"] == "error" for m in messages)
    client1.disconnect()
    client2.disconnect()
