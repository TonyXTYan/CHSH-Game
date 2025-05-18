from flask_sqlalchemy import SQLAlchemy
import enum

db = SQLAlchemy()

class ItemEnum(enum.Enum):
    A = 'A'
    B = 'B'
    C = 'C'
    D = 'D'

class Teams(db.Model):
    __tablename__ = 'teams'
    team_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_name = db.Column(db.String(100), nullable=False)
    __table_args__ = (db.UniqueConstraint('team_name', 'is_active', name='_team_name_active_uc'),)
    player1_session_id = db.Column(db.String(100), nullable=True) # Stores WebSocket SID
    player2_session_id = db.Column(db.String(100), nullable=True) # Stores WebSocket SID
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    # Relationship to track rounds for this team
    rounds = db.relationship('PairQuestionRounds', backref='team', lazy=True)

class Answers(db.Model):
    __tablename__ = 'answers'
    answer_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.team_id'), nullable=False)
    player_session_id = db.Column(db.String(100), nullable=False)
    question_round_id = db.Column(db.Integer, db.ForeignKey('pair_question_rounds.round_id'), nullable=False)
    assigned_item = db.Column(db.Enum(ItemEnum), nullable=False)
    response_value = db.Column(db.Boolean, nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now())

class PairQuestionRounds(db.Model):
    __tablename__ = 'pair_question_rounds'
    round_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.team_id'), nullable=False)
    round_number_for_team = db.Column(db.Integer, nullable=False)
    player1_item = db.Column(db.Enum(ItemEnum), nullable=True)
    player2_item = db.Column(db.Enum(ItemEnum), nullable=True)
    p1_answered_at = db.Column(db.DateTime, nullable=True)
    p2_answered_at = db.Column(db.DateTime, nullable=True)
    timestamp_initiated = db.Column(db.DateTime, server_default=db.func.now())
    # Relationship to answers for this round
    answers = db.relationship('Answers', backref='round', lazy=True)

    # Unique constraint for team_id and round_number_for_team
    __table_args__ = (db.UniqueConstraint('team_id', 'round_number_for_team', name='_team_round_uc'),)
