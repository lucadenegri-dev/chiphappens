import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    # Leggo l'URL del DB dall'ambiente (Render la chiama di solito DATABASE_URL)
    raw_db_url = os.environ.get("DATABASE_URL")

    if raw_db_url:
        # Patch per gestire il prefisso "postgres://" che a volte dà problemi.
        # SQLAlchemy preferisce "postgresql://"
        if raw_db_url.startswith("postgres://"):
            raw_db_url = raw_db_url.replace("postgres://", "postgresql://", 1)

        SQLALCHEMY_DATABASE_URI = raw_db_url
    else:
        # Fallback locale: sqlite nel folder instance
        SQLALCHEMY_DATABASE_URI = "sqlite:///pokergroup.sqlite"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    WTF_CSRF_TIME_LIMIT = None
