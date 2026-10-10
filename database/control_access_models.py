from datetime import datetime
from .database import db


class ControlAccessRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)
    requested_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    passkey_hash = db.Column(db.String(255), nullable=True)
    passkey_expires_at = db.Column(db.DateTime, nullable=True)
    passkey_used_at = db.Column(db.DateTime, nullable=True)
    access_expires_at = db.Column(db.DateTime, nullable=True)
