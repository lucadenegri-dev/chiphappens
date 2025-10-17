# models.py
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint

db = SQLAlchemy()

class Player(db.Model):
    __tablename__ = 'players'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False)

class Game(db.Model):
    __tablename__ = 'games'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    buy_in = db.Column(db.Float, nullable=False)
    total_entries = db.Column(db.Integer, nullable=False, default=0)
    prize_pool = db.Column(db.Float, nullable=False, default=0.0)

class Result(db.Model):
    __tablename__ = 'results'
    id = db.Column(db.Integer, primary_key=True)
    game_id = db.Column(db.Integer, db.ForeignKey('games.id', ondelete='CASCADE'), nullable=False)
    player_id = db.Column(db.Integer, db.ForeignKey('players.id', ondelete='RESTRICT'), nullable=False)
    finish = db.Column(db.Integer, nullable=False)  # 1-based rank
    rebuys = db.Column(db.Integer, nullable=False, default=0)
    points = db.Column(db.Integer, nullable=False, default=0)
    cash_delta = db.Column(db.Float, nullable=False, default=0.0)

    __table_args__ = (
        UniqueConstraint('game_id', 'player_id', name='uq_result_game_player'),
    )

    # Relationships (optional lazy='joined' where needed)
    game = db.relationship('Game', backref=db.backref('results', cascade='all, delete-orphan'))
    player = db.relationship('Player', backref=db.backref('results', cascade='all, delete'))