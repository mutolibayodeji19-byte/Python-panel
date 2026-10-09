import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get(
        "SECRET_KEY",
        "change-this-secret-key-later"
    )

    # Set DATABASE_URL for a managed database, or DATABASE_PATH to a
    # persistent disk path such as /var/data/panel.db on Render.
    database_url = os.environ.get("DATABASE_URL", "").strip()
    database_path = os.environ.get("DATABASE_PATH", "").strip()

    if database_url:
        if database_url.startswith("postgres://"):
            database_url = "postgresql://" + database_url[len("postgres://"):]
        SQLALCHEMY_DATABASE_URI = database_url
    elif database_path:
        SQLALCHEMY_DATABASE_URI = "sqlite:///" + os.path.abspath(database_path)
    else:
        SQLALCHEMY_DATABASE_URI = (
            "sqlite:///" + os.path.join(BASE_DIR, "panel.db")
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}
