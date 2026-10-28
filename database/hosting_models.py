from datetime import datetime
from database.database import db


class HostingServer(db.Model):
    __tablename__ = "hosting_servers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False)
    runtime = db.Column(db.String(20), nullable=False)
    owner_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )
    startup_command = db.Column(
        db.String(500),
        nullable=False,
        default=""
    )

    # Link this project to a real Pterodactyl server.
    pterodactyl_identifier = db.Column(
        db.String(64),
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        nullable=False
    )
