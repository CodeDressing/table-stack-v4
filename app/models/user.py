from datetime import datetime
from flask_login import UserMixin

try:
    from app.services.employee_service import db  # if using SQLAlchemy later
except:
    db = None


class User(UserMixin):
    def __init__(self, id, email, password_hash, role="employee", totp_secret=None, totp_enabled=False):
        self.id = id
        self.email = email
        self.password_hash = password_hash
        self.role = role
        self.totp_secret = totp_secret
        self.totp_enabled = totp_enabled

    def is_admin(self):
        return self.role == "admin"

    def is_manager(self):
        return self.role in ["admin", "manager"]