import eventlet
eventlet.monkey_patch()
import signal
from functools import partial

from src.main import app, socketio, handle_shutdown

def gunicorn_shutdown(signal, frame, server):
    print("\nGunicorn worker shutting down gracefully...")
    handle_shutdown(signal, frame)
    server.stop()

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0')
else:
    # For production with Gunicorn
    app.app_context().push()  # Ensure app context is available
    # Setup signal handlers for gunicorn
    server = socketio.server
    signal.signal(signal.SIGTERM, partial(gunicorn_shutdown, server=server))
    signal.signal(signal.SIGINT, partial(gunicorn_shutdown, server=server))
