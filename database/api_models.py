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
