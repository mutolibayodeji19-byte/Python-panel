from datetime import datetime

from .database import db


class APIKey(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    key = db.Column(db.String(100), unique=True, nullable=False)

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    name = db.Column(db.String(80), default="Default")

    is_active = db.Column(db.Boolean, default=True)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow
    )

    last_used = db.Column(
        db.DateTime,
        nullable=True
    )


class APIUsage(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    api_key_id = db.Column(
        db.Integer,
        db.ForeignKey("api_key.id"),
        nullable=False,
        index=True
    )

    endpoint = db.Column(db.String(120), nullable=False)
    status_code = db.Column(db.Integer, nullable=False)

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False,
        index=True
    )
