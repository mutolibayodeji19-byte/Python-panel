from flask import Flask
from flask_login import LoginManager

from config import Config
from database.database import db
from database.models import User
from database.api_models import APIKey


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

app.register_blueprint(auth)
app.register_blueprint(dashboard)
app.register_blueprint(admin)
app.register_blueprint(api_keys)


with app.app_context():
    db.create_all()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
