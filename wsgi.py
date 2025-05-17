import eventlet
eventlet.monkey_patch()

from src.main import app, socketio

if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0')
else:
    # For production with Gunicorn
    app.app_context().push()  # Ensure app context is available
