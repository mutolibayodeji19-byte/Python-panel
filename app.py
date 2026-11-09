
import os

from flask import Flask, render_template_string
from flask_login import LoginManager

from config import Config
from database.database import db
from database.models import User
from database.api_models import APIKey
from database.feature_models import UptimeMonitor, WhatsAppBot

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


from routes.auth import auth
from routes.dashboard import dashboard
from routes.admin import admin
from routes.api_keys import api_keys
from routes.api import api
from routes.features import features
from routes.worker import worker
from routes.hosting import hosting
from routes.control_access import control_access

app.register_blueprint(auth)
app.register_blueprint(dashboard)
app.register_blueprint(admin)
app.register_blueprint(api_keys)
app.register_blueprint(api)
app.register_blueprint(features)
app.register_blueprint(worker)
app.register_blueprint(hosting)
app.register_blueprint(control_access)


@app.route("/version", methods=["GET"])
def version():
    return {
        "service": "PRIME ZENITH",
        "deployed_commit": os.environ.get(
            "RENDER_GIT_COMMIT"
        ) or __import__("subprocess").getoutput(
            "git rev-parse HEAD"
        ).strip() or "unknown"
    }, 200


@app.route("/verify-owner", methods=["GET"])
def verify_owner():
    username = os.environ.get("OWNER_USERNAME")

    if not username:
        return "Owner configuration unavailable", 503

    owner = User.query.filter_by(
        username=username,
        is_admin=True,
        is_active_user=True,
        plan="OWNER"
    ).first()

    if owner is None:
        return "Owner verification failed", 404

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <title>PRIME ZENITH - Owner Verification</title>
        <style>
            body {
                background: #050807;
                color: white;
                font-family: Arial, sans-serif;
                display: flex;
                justify-content: center;
                align-items: center;
                min-height: 100vh;
                margin: 0;
            }
            .card {
                background: #101914;
                border: 1px solid #20d879;
                border-radius: 20px;
                padding: 30px;
                width: 85%;
                max-width: 420px;
                text-align: center;
                box-shadow: 0 0 25px #20d87933;
            }
            .brand {
                color: #20d879;
                letter-spacing: 3px;
                font-weight: bold;
            }
            .verified {
                color: #20d879;
                font-weight: bold;
                margin: 25px 0;
            }
            .owner {
                font-size: 28px;
                font-weight: bold;
            }
            .detail {
                color: #aaa;
            }
            .footer {
                color: #777;
                font-size: 12px;
                margin-top: 25px;
            }
        </style>
    </head>
    <body>
        <div class="card">
            <div class="brand">PRIME ZENITH</div>
            <h2>OWNER VERIFICATION</h2>
            <div class="verified">✓ OWNER VERIFIED</div>
            <div class="owner">{{ username }}</div>
            <p class="detail">OFFICIAL PROJECT OWNER</p>
            <hr>
            <p>Project: PRIME ZENITH PYTHON PANEL</p>
            <p>Role: OWNER / ROOT ADMIN</p>
            <p>Status: ACTIVE</p>
            <div class="footer">
                Verified against live database<br>
                PRIME ZENITH © 2026
            </div>
        </div>
    </body>
    </html>
    """, username=owner.username)


def create_owner():
    username = os.environ.get("OWNER_USERNAME")
    email = os.environ.get("OWNER_EMAIL")
    password = os.environ.get("OWNER_PASSWORD")

    if not username or not email or not password:
        return

    owner = User.query.filter_by(username=username).first()

    if owner is None:
        owner = User(
            username=username,
            email=email,
            is_admin=True,
            is_active_user=True,
            plan="OWNER"
        )

        owner.set_password(password)
        db.session.add(owner)
        db.session.commit()

        print(f"OWNER CREATED: {username}")

    else:
        changed = False

        if not owner.is_admin:
            owner.is_admin = True
            changed = True

        if not owner.is_active_user:
            owner.is_active_user = True
            changed = True

        if owner.plan != "OWNER":
            owner.plan = "OWNER"
            changed = True

        if changed:
            db.session.commit()

        print(f"OWNER VERIFIED: {username}")


with app.app_context():
    db.create_all()
    create_owner()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
)
