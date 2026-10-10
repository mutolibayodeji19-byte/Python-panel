import os

from flask import Flask
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

app.register_blueprint(auth)
app.register_blueprint(dashboard)
app.register_blueprint(admin)
app.register_blueprint(api_keys)
app.register_blueprint(api)
app.register_blueprint(features)


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
