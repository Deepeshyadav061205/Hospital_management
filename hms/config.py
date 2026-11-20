import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    """Application configuration with SQLite default and optional MySQL via DATABASE_URL."""

    SECRET_KEY = os.environ.get("SECRET_KEY", "citycare-hms-dev-secret-key")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'hms.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CSRF_ENABLED = True
    AUTO_SEED = True
