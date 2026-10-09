from datetime import datetime

from database.database import db


class UptimeMonitor(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    last_status = db.Column(db.String(20), default="Unchecked", nullable=False)
    last_code = db.Column(db.Integer, nullable=True)
    last_response_ms = db.Column(db.Integer, nullable=True)
    last_checked = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class WhatsAppBot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    name = db.Column(db.String(80), nullable=False)
    phone_label = db.Column(db.String(40), default="", nullable=False)
    connection_status = db.Column(db.String(20), default="Not connected", nullable=False)
    hosting_label = db.Column(db.String(120), default="", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
