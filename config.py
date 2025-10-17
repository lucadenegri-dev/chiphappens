import os
from datetime import timedelta

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "sqlite:///"  # replaced below with instance-based path if missing scheme
    )
    # Use instance/pokergroup.sqlite by default
    if SQLALCHEMY_DATABASE_URI == "sqlite:///":
        # instance_relative_config=True in app ensures instance path exists
        SQLALCHEMY_DATABASE_URI = "sqlite:///pokergroup.sqlite"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    WTF_CSRF_TIME_LIMIT = None