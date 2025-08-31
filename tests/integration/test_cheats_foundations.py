import eventlet
eventlet.monkey_patch()

from flask_socketio import SocketIOTestClient
from src.config import app, socketio as server_socketio
from src.state import state
from src.models.quiz_models import Teams, PairQuestionRounds, Answers, db


def reset_state():
    with app.app_context():
        Answers.query.delete()
        PairQuestionRounds.query.delete()
        Teams.query.delete()
        db.session.commit()
    state.reset()


def test_non_cheat_team_receives_no_cheat_events():
    reset_state()
    client1 = SocketIOTestClient(app, server_socketio)
    client2 = SocketIOTestClient(app, server_socketio)

    client1.emit('create_team', {'team_name': 'honest'})
    client2.emit('join_team', {'team_name': 'honest'})

    for event in client1.get_received() + client2.get_received():
        assert not event['name'].startswith('cheat')

    client1.disconnect()
    client2.disconnect()
