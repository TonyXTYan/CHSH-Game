import eventlet
eventlet.monkey_patch()
import signal
from functools import partial
import logging

# Configure logging
logging.basicConfig(level=logging.INFO,
                   format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

from src.main import app, socketio, handle_shutdown

def gunicorn_shutdown(signal, frame, server):
    logger.info("Gunicorn worker shutting down gracefully...")
    handle_shutdown(signal, frame)
    server.stop()

def when_ready(server):
    logger.info("Gunicorn worker ready")

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0')
else:
    # For production with Gunicorn
    try:
        app.app_context().push()  # Ensure app context is available
        # Setup signal handlers for gunicorn
        server = socketio.server
        signal.signal(signal.SIGTERM, partial(gunicorn_shutdown, server=server))
        signal.signal(signal.SIGINT, partial(gunicorn_shutdown, server=server))
        logger.info("Gunicorn worker initialized successfully")
    except Exception as e:
        logger.error(f"Error initializing gunicorn worker: {e}")
        import traceback
        logger.error(traceback.format_exc())
        raise
