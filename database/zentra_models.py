from datetime import datetime

from database.database import db


class ZentraPlayer(db.Model):
    __tablename__ = "zentra_player"

    id = db.Column(db.Integer, primary_key=True)
    platform_id = db.Column(db.String(120), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(80), nullable=False)
    balance = db.Column(db.Integer, nullable=False, default=500)
    last_daily = db.Column(db.DateTime, nullable=True)
    last_work = db.Column(db.DateTime, nullable=True)
    last_heist = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class ZentraMarriage(db.Model):
    __tablename__ = "zentra_marriage"

    id = db.Column(db.Integer, primary_key=True)
    proposer_id = db.Column(
        db.Integer, db.ForeignKey("zentra_player.id"), nullable=False
    )
    target_id = db.Column(
        db.Integer, db.ForeignKey("zentra_player.id"), nullable=False
    )
    accepted = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


class ZentraTransaction(db.Model):
    __tablename__ = "zentra_transaction"

    id = db.Column(db.Integer, primary_key=True)
    player_id = db.Column(
        db.Integer, db.ForeignKey("zentra_player.id"), nullable=False, index=True
    )
    action = db.Column(db.String(40), nullable=False)
    amount = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    other_player_id = db.Column(
        db.Integer, db.ForeignKey("zentra_player.id"), nullable=True
    )
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
