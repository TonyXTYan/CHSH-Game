import os
import sys
import signal
import uuid
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Unique ID for server instance
server_instance_id = str(uuid.uuid4())

def handle_shutdown(signum, frame):
    print("\nServer shutting down gracefully...")
    # Notify all clients
    socketio.emit('server_shutdown')
    # Clean up resources
    state.reset()
    sys.exit(0)

from src.config import app, socketio, db
from src.models.quiz_models import Teams, Answers, PairQuestionRounds
from src.state import state

# Initialize the database tables
with app.app_context():
    db.create_all()
    # Reset all teams to inactive and clear all data on server start
    try:
        # Delete all answers first to avoid foreign key constraints
        Answers.query.delete()
        # Delete all question rounds
        PairQuestionRounds.query.delete()
        # Now handle teams
        active_teams_query = Teams.query.filter_by(is_active=True)
        teams = active_teams_query.all()
        for team in teams:
            # First check if there's already an inactive team with same name
            existing_inactive = Teams.query.filter_by(team_name=team.team_name, is_active=False).first()
            if existing_inactive:
                # If exists, we need to give this team a unique name before deactivating
                team.team_name = f"{team.team_name}_{team.team_id}"
            team.is_active = False
            db.session.flush()  # Flush changes for each team individually
        db.session.commit()
        
        # Notify dashboard clients of reset
        socketio.emit('game_reset_complete')
    except Exception as e:
        print(f"Error resetting data: {str(e)}")
        db.session.rollback()
    # Clear memory state
    state.reset()

# Import all route handlers and socket event handlers
from src.routes.static import serve

@app.route('/api/server/id')
def get_server_id():
    return {'instance_id': server_instance_id}
from src.sockets.dashboard import on_dashboard_join, on_start_game, get_dashboard_data
from src.sockets.team_management import (
    handle_connect, 
    handle_disconnect, 
    on_create_team, 
    on_join_team, 
    on_leave_team
)
from src.sockets.game import (
    on_submit_answer, 
    on_verify_team_membership, 
    on_rejoin_team
)

if __name__ == '__main__':
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, use_reloader=False)
