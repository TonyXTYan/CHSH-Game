import os
import sys
import signal
import uuid
import threading
import time
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
    print("Initializing database and cleaning up old data...")
    try:
        # Start transaction
        db.session.begin_nested()

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
        import traceback
        traceback.print_exc()
        db.session.rollback()
        
    finally:
        # Always clear memory state
        state.reset()
        print("Server initialization complete")
        
    # Setup periodic team validation
    try:
        from src.sockets.team_validation import validate_all_teams
        
        # Function to run validation periodically
        def periodic_validation():
            while True:
                time.sleep(60)  # Run every 60 seconds
                try:
                    print("Running periodic team validation...")
                    with app.app_context():
                        validate_all_teams()
                except Exception as e:
                    print(f"Error in periodic validation: {e}")
        
        # Initial validation on first client connect
        @socketio.on('connect')
        def run_initial_validation():
            # Perform validation when the first client connects
            if not hasattr(state, 'validation_performed'):
                print("Running initial team validation...")
                validate_all_teams()
                state.validation_performed = True
                
                # Start the periodic validation thread
                validation_thread = threading.Thread(target=periodic_validation, daemon=True)
                validation_thread.start()
                print("Started periodic validation thread")
    except ImportError:
        print("Warning: Team validation module not available")

# Import all route handlers and socket event handlers
from src.routes.static import serve

@app.route('/api/server/id')
def get_server_id():
    return {'instance_id': server_instance_id}
from src.sockets import dashboard
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
