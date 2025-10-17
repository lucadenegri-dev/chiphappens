# auth.py
import os
from flask_login import UserMixin
from werkzeug.security import generate_password_hash

class AdminUser(UserMixin):
    """Single-admin user backed by environment variable ADMIN_PASSWORD_HASH or ADMIN_PASSWORD.
    Create a hashed value automatically at runtime if only ADMIN_PASSWORD is provided.
    """
    def __init__(self):
        self.id = "admin"
        env_hash = os.environ.get("ADMIN_PASSWORD_HASH")
        env_plain = os.environ.get("ADMIN_PASSWORD")
        if env_hash:
            self.password_hash = env_hash
        elif env_plain:
            self.password_hash = generate_password_hash(env_plain)
        else:
            # In dev only: default password 'admin' (strongly recommend setting env vars)
            self.password_hash = generate_password_hash("admin")