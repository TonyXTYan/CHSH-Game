# Add throttling constant to config.py
from flask import Flask
from flask_socketio import SocketIO
from flask_sqlalchemy import SQLAlchemy
import os

# Create Flask app
app = Flask(__name__)

# Configure database
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///chsh_game.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Configure SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25)

# Dashboard update throttling configuration (1Hz maximum)
DASHBOARD_UPDATE_THROTTLE_RATE = 1.0  # Maximum updates per second (1Hz)
DASHBOARD_MIN_UPDATE_INTERVAL = 1.0 / DASHBOARD_UPDATE_THROTTLE_RATE  # Minimum time between updates in seconds
