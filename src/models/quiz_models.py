from flask_sqlalchemy import SQLAlchemy
import enum

db = SQLAlchemy()

class ItemEnum(enum.Enum):
    A = 'A'
    B = 'B'
    X = 'X'
    Y = 'Y'

class Teams(db.Model):
    __tablename__ = 'teams'
    team_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_name = db.Column(db.String(100), nullable=False, index=True)
    player1_session_id = db.Column(db.String(100), nullable=True) # Stores WebSocket SID
    player2_session_id = db.Column(db.String(100), nullable=True) # Stores WebSocket SID
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, server_default=db.func.now(), index=True)
    # Relationship to track rounds for this team
    rounds = db.relationship('PairQuestionRounds', backref='team', lazy=True)
    
    __table_args__ = (
        db.UniqueConstraint('team_name', 'is_active', name='_team_name_active_uc'),
        db.Index('idx_teams_active_created', 'is_active', 'created_at'),
    )

class Answers(db.Model):
    __tablename__ = 'answers'
    answer_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.team_id'), nullable=False, index=True)
    player_session_id = db.Column(db.String(100), nullable=False, index=True)
    question_round_id = db.Column(db.Integer, db.ForeignKey('pair_question_rounds.round_id'), nullable=False, index=True)
    assigned_item = db.Column(db.Enum(ItemEnum), nullable=False, index=True)
    response_value = db.Column(db.Boolean, nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.now(), index=True)
    
    __table_args__ = (
        db.Index('idx_answers_team_timestamp', 'team_id', 'timestamp'),
        db.Index('idx_answers_round_team', 'question_round_id', 'team_id'),
        db.Index('idx_answers_team_item', 'team_id', 'assigned_item'),
    )

class PairQuestionRounds(db.Model):
    __tablename__ = 'pair_question_rounds'
    round_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.team_id'), nullable=False, index=True)
    round_number_for_team = db.Column(db.Integer, nullable=False, index=True)
    player1_item = db.Column(db.Enum(ItemEnum), nullable=True, index=True)
    player2_item = db.Column(db.Enum(ItemEnum), nullable=True, index=True)
    p1_answered_at = db.Column(db.DateTime, nullable=True)
    p2_answered_at = db.Column(db.DateTime, nullable=True)
    timestamp_initiated = db.Column(db.DateTime, server_default=db.func.now(), index=True)
    # Relationship to answers for this round
    answers = db.relationship('Answers', backref='round', lazy=True)

    __table_args__ = (
        db.UniqueConstraint('team_id', 'round_number_for_team', name='_team_round_uc'),
        db.Index('idx_rounds_team_timestamp', 'team_id', 'timestamp_initiated'),
        db.Index('idx_rounds_team_items', 'team_id', 'player1_item', 'player2_item'),
    )
