import os
import sys
import signal
import uuid
import traceback
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# Unique ID for server instance
server_instance_id = str(uuid.uuid4())

def handle_shutdown(signum, frame):
    """
    Handle graceful shutdown of the server.
    Notifies clients and cleans up resources.
    """
    print("\nServer shutting down gracefully...")
    try:
        # Notify all clients
        socketio.emit('server_shutdown')
        # Clean up resources
        state.reset()
        # Close database connections
        try:
            db.session.remove()
            db.engine.dispose()
        except Exception as db_error:
            print(f"Error closing database connections: {str(db_error)}")
    except Exception as e:
        print(f"Error during shutdown: {str(e)}")
    finally:
        sys.exit(0)

from src.config import app, socketio, db, DEBUG, PORT, HOST
from src.models.quiz_models import Teams, Answers, PairQuestionRounds
from src.state import state

# Initialize the database tables
with app.app_context():
    db.create_all()
    print("Initializing database and cleaning up old data...")
    try:
        # Start transaction
        db.session.begin()

        # Delete all answers first to avoid foreign key constraints
        answers_count = Answers.query.delete()
        print(f"Deleted {answers_count} answers")

        # Delete all question rounds
        rounds_count = PairQuestionRounds.query.delete()
        print(f"Deleted {rounds_count} question rounds")

        # Delete all inactive teams
        inactive_count = Teams.query.filter_by(is_active=False).delete()
        print(f"Deleted {inactive_count} inactive teams")

        # Mark all remaining teams as inactive and rename if needed
        active_teams = Teams.query.filter_by(is_active=True).all()
        renamed_count = 0
        deactivated_count = 0

        for team in active_teams:
            team.is_active = False
            deactivated_count += 1
            
            # Check for name conflicts with other active teams being deactivated
            conflicting_teams = [t for t in active_teams if t != team and t.team_name == team.team_name]
            if conflicting_teams:
                team.team_name = f"{team.team_name}_{team.team_id}"
                renamed_count += 1
            
            db.session.flush()

        db.session.commit()
        print(f"Deactivated {deactivated_count} active teams (renamed {renamed_count} due to conflicts)")

        # Notify any connected dashboard clients
        socketio.emit('game_reset_complete')
        
    except Exception as e:
        print(f"Error resetting database: {str(e)}")
        traceback.print_exc()
        db.session.rollback()
        
    finally:
        # Always clear memory state
        state.reset()
        print("Server initialization complete")

# Import all route handlers and socket event handlers
from src.routes.static import serve

@app.route('/api/server/id')
def get_server_id():
    """Return the unique server instance ID."""
    return {'instance_id': server_instance_id}

# Import socket handlers
from src.sockets import dashboard
from src.sockets.team_management import (
    handle_connect, 
    handle_disconnect, 
    on_create_team, 
    on_join_team, 
    on_leave_team,
    on_reactivate_team
)
from src.sockets.game import (
    on_submit_answer
)

if __name__ == '__main__':
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    # Run the server with configuration from config.py
    socketio.run(
        app, 
        host=HOST, 
        port=PORT, 
        debug=DEBUG, 
        use_reloader=False,
        allow_unsafe_werkzeug=DEBUG  # Only allow in debug mode
    )
