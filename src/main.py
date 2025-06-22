import os
import sys
import signal
import uuid
import logging

# Configure logging for main module
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.config import app, socketio, db
from src.models.quiz_models import Teams, Answers, PairQuestionRounds
from src.state import state

# Unique ID for server instance
server_instance_id = str(uuid.uuid4())

# Signal handler for graceful shutdown
def handle_shutdown(signum, frame):
    logger.info("Server shutting down gracefully...")
    try:
        # Notify all connected clients about the shutdown
        socketio.emit('server_shutdown')
        socketio.sleep(1)  # Allow time for clients to receive the message
        # Close the socket connections
        socketio.stop()
        logger.info("Socket connections closed.")
    except Exception as e:
        logger.error(f"Error during socket shutdown: {e}")
    try:
        # Reset the in-memory state
        logger.info("Resetting in-memory state...")
        if hasattr(state, 'reset'): # Ensure reset method exists
            state.reset()
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    finally:
        sys.exit(0)

# Initialize the database tables
with app.app_context():
    db.create_all()
    logger.info("Initializing database and cleaning up old data...")
    try:
        # Start transaction
        db.session.begin_nested()

        # Delete all answers first to avoid foreign key constraints
        answers_count = Answers.query.delete()
        logger.info(f"Deleted {answers_count} answers")

        # Delete all question rounds
        rounds_count = PairQuestionRounds.query.delete()
        logger.info(f"Deleted {rounds_count} question rounds")

        # Delete all inactive teams
        inactive_count = Teams.query.filter_by(is_active=False).delete()
        logger.info(f"Deleted {inactive_count} inactive teams")

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
        logger.info(f"Deactivated {deactivated_count} active teams (renamed {renamed_count} due to conflicts)")

        # Notify any connected dashboard clients
        socketio.emit('game_reset_complete')
        
    except Exception as e:
        logger.error(f"Error resetting database: {str(e)}", exc_info=True)
        db.session.rollback()
        
    finally:
        # Always clear memory state
        state.reset()
        logger.info("Server initialization complete")

# Import all route handlers and socket event handlers
from src.routes.static import serve
from src.sockets import dashboard
from src.sockets.team_management import (
    handle_connect, 
    handle_disconnect, 
    on_create_team, 
    on_join_team, 
    on_leave_team
)
from src.sockets.game import (
    on_submit_answer
)

if __name__ == '__main__':
    # Register signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    socketio.run(app, host='0.0.0.0', port=8080, debug=True, use_reloader=False)
