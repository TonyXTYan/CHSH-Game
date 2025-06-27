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
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet', ping_timeout=30, ping_interval=5)

# Import routes to register them
from src.routes import static
from src.routes.user import user_bp
app.register_blueprint(user_bp)

# Create database tables
with app.app_context():
    db.create_all()

# Socket handlers are automatically registered when their modules are imported in main.py
# The @socketio.on() decorators in each module register the handlers with the socketio instance