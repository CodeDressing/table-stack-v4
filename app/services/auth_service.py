"""
TABLE STACK v4 – AUTH SERVICE
------------------------------------------------------------
Secure authentication service with:
- Argon2 password hashing
- JSON-backed user storage for Phase 11
- TOTP 2FA support
- QR-code provisioning URI support
- Hashed recovery codes
- Admin/manager/employee roles

Important:
This is a strong local/early-production foundation.
For long-term production, move users into a real database.
------------------------------------------------------------
"""

import json
import secrets
import string
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask_login import UserMixin


# ============================================================
# 1. CONFIGURATION
# ============================================================

AUTH_DATA_FILE = Path.cwd() / "instance" / "users.json"

PASSWORD_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=2,
    hash_len=32,
    salt_len=16,
)


# ============================================================
# 2. USER CLASS FOR FLASK-LOGIN
# ============================================================

class AuthUser(UserMixin):
    def __init__(self, user_data: Dict[str, Any]):
        self.user_data = user_data
        self.id = str(user_data.get("id"))
        self.email = user_data.get("email")
        self.role = user_data.get("role", "employee")

    def is_admin(self) -> bool:
        return self.role == "admin"

    def is_manager(self) -> bool:
        return self.role in {"admin", "manager"}

    def can_manage_schedules(self) -> bool:
        return self.is_manager()


# ============================================================
# 3. FILE HELPERS
# ============================================================

def ensure_auth_file() -> None:
    AUTH_DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not AUTH_DATA_FILE.exists():
        AUTH_DATA_FILE.write_text(
            json.dumps({"users": [], "last_updated": None}, indent=2),
            encoding="utf-8",
        )


def load_auth_data() -> Dict[str, Any]:
    ensure_auth_file()

    try:
        with AUTH_DATA_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if "users" not in data or not isinstance(data["users"], list):
            data["users"] = []

        return data

    except json.JSONDecodeError:
        return {"users": [], "last_updated": None}


def save_auth_data(data: Dict[str, Any]) -> bool:
    ensure_auth_file()

    data["last_updated"] = datetime.now().isoformat()

    with AUTH_DATA_FILE.open("w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)

    return True


# ============================================================
# 4. USER LOOKUP
# ============================================================

def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def find_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    email = normalize_email(email)
    data = load_auth_data()

    for user in data["users"]:
        if normalize_email(user.get("email")) == email:
            return user

    return None


def find_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    data = load_auth_data()

    for user in data["users"]:
        if str(user.get("id")) == str(user_id):
            return user

    return None


def get_login_user(user_id: str) -> Optional[AuthUser]:
    user = find_user_by_id(user_id)

    if not user:
        return None

    return AuthUser(user)


# ============================================================
# 5. PASSWORD HELPERS
# ============================================================

def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def password_needs_rehash(password_hash: str) -> bool:
    try:
        return PASSWORD_HASHER.check_needs_rehash(password_hash)
    except Exception:
        return False


# ============================================================
# 6. USER CREATION / SEEDING
# ============================================================

def create_user(
    email: str,
    password: str,
    role: str = "employee",
    force: bool = False,
) -> Optional[Dict[str, Any]]:
    """
    Create a user.

    force=False prevents duplicates.
    """
    email = normalize_email(email)

    if not email or not password:
        return None

    data = load_auth_data()

    existing = find_user_by_email(email)

    if existing and not force:
        return existing

    if existing and force:
        data["users"] = [
            user for user in data["users"]
            if normalize_email(user.get("email")) != email
        ]

    user = {
        "id": str(uuid.uuid4()),
        "email": email,
        "password_hash": hash_password(password),
        "role": role,
        "totp_secret": None,
        "totp_enabled": False,
        "recovery_codes": [],
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }

    data["users"].append(user)
    save_auth_data(data)

    return user


def seed_default_managers() -> None:
    """
    Creates Ryan/Admin and Mike/Manager only if they do not exist.

    IMPORTANT:
    Change these passwords immediately after first successful login.
    """
    create_user(
        email="ryan@tablestack.local",
        password="ChangeMeRyan123!",
        role="admin",
    )

    create_user(
        email="mike@tablestack.local",
        password="ChangeMeMike123!",
        role="manager",
    )


# ============================================================
# 7. LOGIN VERIFICATION
# ============================================================

def verify_login_credentials(email: str, password: str) -> Optional[Dict[str, Any]]:
    user = find_user_by_email(email)

    if not user:
        return None

    if not verify_password(user.get("password_hash", ""), password):
        return None

    if password_needs_rehash(user.get("password_hash", "")):
        user["password_hash"] = hash_password(password)
        update_user(user)

    return user


def update_user(updated_user: Dict[str, Any]) -> bool:
    data = load_auth_data()

    for index, user in enumerate(data["users"]):
        if str(user.get("id")) == str(updated_user.get("id")):
            updated_user["updated_at"] = datetime.now().isoformat()
            data["users"][index] = updated_user
            return save_auth_data(data)

    return False


# ============================================================
# 8. TOTP / 2FA HELPERS
# ============================================================

def generate_totp_secret() -> str:
    return pyotp.random_base32()


def get_totp_provisioning_uri(user: Dict[str, Any]) -> str:
    """
    URI consumed by Google Authenticator/Authy.
    """
    secret = user.get("totp_secret")

    if not secret:
        raise ValueError("User does not have a TOTP secret.")

    totp = pyotp.TOTP(secret)

    return totp.provisioning_uri(
        name=user.get("email"),
        issuer_name="TableStack v4",
    )


def verify_totp_code(user: Dict[str, Any], code: str) -> bool:
    secret = user.get("totp_secret")

    if not secret or not code:
        return False

    totp = pyotp.TOTP(secret)

    return bool(totp.verify(str(code).strip(), valid_window=1))


def begin_2fa_setup(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Creates a secret but does NOT enable 2FA yet.
    User must confirm with a valid TOTP code.
    """
    user = find_user_by_id(user_id)

    if not user:
        return None

    user["totp_secret"] = generate_totp_secret()
    user["totp_enabled"] = False

    update_user(user)

    return user


def confirm_2fa_setup(user_id: str, code: str) -> Tuple[bool, List[str]]:
    """
    Enables 2FA after code confirmation.
    Returns:
        success, plaintext recovery codes
    """
    user = find_user_by_id(user_id)

    if not user:
        return False, []

    if not verify_totp_code(user, code):
        return False, []

    recovery_codes = generate_recovery_codes()
    user["recovery_codes"] = hash_recovery_codes(recovery_codes)
    user["totp_enabled"] = True

    update_user(user)

    return True, recovery_codes


def disable_2fa(user_id: str, password: str) -> bool:
    """
    Disable 2FA only after password confirmation.
    """
    user = find_user_by_id(user_id)

    if not user:
        return False

    if not verify_password(user.get("password_hash", ""), password):
        return False

    user["totp_enabled"] = False
    user["totp_secret"] = None
    user["recovery_codes"] = []

    return update_user(user)


# ============================================================
# 9. RECOVERY CODES
# ============================================================

def generate_single_recovery_code(length: int = 10) -> str:
    alphabet = string.ascii_uppercase + string.digits
    raw = "".join(secrets.choice(alphabet) for _ in range(length))
    return f"{raw[:5]}-{raw[5:]}"


def generate_recovery_codes(count: int = 10) -> List[str]:
    return [generate_single_recovery_code() for _ in range(count)]


def hash_recovery_codes(codes: List[str]) -> List[str]:
    return [hash_password(code) for code in codes]


def verify_recovery_code(user: Dict[str, Any], submitted_code: str) -> bool:
    """
    One-time use recovery code verification.
    Removes used code if valid.
    """
    submitted_code = (submitted_code or "").strip().upper()

    if not submitted_code:
        return False

    recovery_hashes = user.get("recovery_codes", [])

    for code_hash in recovery_hashes:
        if verify_password(code_hash, submitted_code):
            user["recovery_codes"] = [
                existing_hash for existing_hash in recovery_hashes
                if existing_hash != code_hash
            ]
            update_user(user)
            return True

    return False


# ============================================================
# 10. ROLE HELPERS
# ============================================================

def user_is_manager(user: AuthUser) -> bool:
    return bool(user and user.is_manager())


def user_is_admin(user: AuthUser) -> bool:
    return bool(user and user.is_admin())