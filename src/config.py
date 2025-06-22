import os
import eventlet
eventlet.monkey_patch()

from flask import Flask
from flask_socketio import SocketIO
from src.models.quiz_models import db

app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'asdf#FGSgvasgf$5$WGT')

# Fix for SQLite URL format in render.com
database_url = os.environ.get('DATABASE_URL')
if database_url and database_url.startswith('postgres://'):
    database_url = database_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = database_url or 'sqlite:///' + os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'quiz_app.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
# Optimized ping settings for highly interactive gameplay
# ping_timeout: How long to wait for pong response (15 seconds for quick detection of disconnections)
# ping_interval: How often to send ping (3 seconds for responsive connection monitoring)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', 
                   ping_timeout=15, ping_interval=3, 
                   max_http_buffer_size=100000000,  # 100MB buffer
                   logger=False, engineio_logger=False)
                #    logger=True, engineio_logger=True)


# Import routes to register them
from src.routes import static

# Import socket handlers to register them
from src.sockets.team_management import handle_connect, handle_disconnect
from src.sockets import game

# Create database tables
with app.app_context():
    db.create_all()