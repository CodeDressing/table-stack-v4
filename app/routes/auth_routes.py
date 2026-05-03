"""
TABLE STACK v4 – AUTH ROUTES
============================================================
PHASE 11 PART 1 OF 8
Account access, login, logout, 2FA routing, and security page
foundation.

SECTION MAP
1. Imports
2. Blueprint + Login Manager
3. Role Decorators
4. Login / 2FA Login Flow
5. Logout
6. Security Profile Page
7. 2FA Enable / Confirm / Disable Routes
8. Future Expansion Blocks
============================================================
"""

import base64
from io import BytesIO
from functools import wraps

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    session,
    abort,
)
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)

from app.services.auth_service import (
    AuthUser,
    get_login_user,
    verify_login_credentials,
    verify_totp_code,
    verify_recovery_code,
    find_user_by_id,
    begin_2fa_setup,
    confirm_2fa_setup,
    disable_2fa,
    get_totp_provisioning_uri,
)


# ============================================================
# 1. BLUEPRINT + LOGIN MANAGER
# ============================================================

auth_bp = Blueprint("auth", __name__)

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to continue."
login_manager.login_message_category = "warning"


@login_manager.user_loader
def load_user(user_id):
    """Load user for Flask-Login."""
    return get_login_user(user_id)


# ============================================================
# 2. ROLE DECORATORS
# ============================================================

def manager_required(view_func):
    """
    Require admin or manager access.
    Use this later on scheduling/admin routes.
    """
    @wraps(view_func)
    @login_required
    def wrapped_view(*args, **kwargs):
        if not current_user.is_manager():
            abort(403)
        return view_func(*args, **kwargs)

    return wrapped_view


def admin_required(view_func):
    """
    Require admin-only access.
    """
    @wraps(view_func)
    @login_required
    def wrapped_view(*args, **kwargs):
        if not current_user.is_admin():
            abort(403)
        return view_func(*args, **kwargs)

    return wrapped_view


# ============================================================
# 3. LOGIN / 2FA LOGIN FLOW
# ============================================================

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """
    Login step 1:
    - Verify email + password
    - If 2FA enabled, redirect to 2FA challenge
    - If not, log in directly
    """
    if current_user.is_authenticated:
        return redirect("/dashboard")

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        user = verify_login_credentials(email, password)

        if not user:
            flash("Invalid email or password.", "error")
            return render_template("login.html")

        if user.get("totp_enabled"):
            session["pending_2fa_user_id"] = user["id"]
            session["remember_login"] = remember
            flash("Enter your 2FA code to continue.", "info")
            return redirect(url_for("auth.two_factor"))

        login_user(AuthUser(user), remember=remember)
        flash("Logged in successfully.", "success")
        return redirect("/dashboard")

    return render_template("login.html")


@auth_bp.route("/2fa", methods=["GET", "POST"])
def two_factor():
    """
    Login step 2:
    - Verify TOTP code
    - Or verify one-time recovery code
    """
    pending_user_id = session.get("pending_2fa_user_id")

    if not pending_user_id:
        return redirect(url_for("auth.login"))

    user = find_user_by_id(pending_user_id)

    if not user:
        session.pop("pending_2fa_user_id", None)
        session.pop("remember_login", None)
        flash("Login session expired. Please log in again.", "warning")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        remember = bool(session.get("remember_login"))

        if verify_totp_code(user, code) or verify_recovery_code(user, code):
            session.pop("pending_2fa_user_id", None)
            session.pop("remember_login", None)

            login_user(AuthUser(user), remember=remember)
            flash("Two-factor authentication verified.", "success")
            return redirect("/dashboard")

        flash("Invalid authentication code.", "error")

    return render_template("two_factor.html")


# ============================================================
# 4. LOGOUT
# ============================================================

@auth_bp.route("/logout")
@login_required
def logout():
    """
    Securely log out the current user.
    Clears both Flask-Login and session state.
    """
    logout_user()
    session.clear()
    flash("You have been logged out.", "success")
    return redirect(url_for("auth.login"))


# ============================================================
# 5. SECURITY PROFILE PAGE
# ============================================================

@auth_bp.route("/security", methods=["GET"])
@login_required
def security_settings():
    """
    Account security page.
    Shows role, account email, and 2FA status.
    """
    user = find_user_by_id(current_user.id)

    if not user:
        abort(401)

    return render_template(
        "profile_security.html",
        user=user,
        current_user=current_user,
        recovery_codes=None,
        qr_code_data=None,
    )


# ============================================================
# 6. 2FA ENABLE / CONFIRM / DISABLE ROUTES
# ============================================================

def build_qr_code_data_uri(provisioning_uri: str) -> str:
    """
    Convert TOTP provisioning URI into a base64 QR image.
    """
    try:
        import qrcode

        qr_image = qrcode.make(provisioning_uri)
        buffer = BytesIO()
        qr_image.save(buffer, format="PNG")
        encoded = base64.b64encode(buffer.getvalue()).decode("utf-8")
        return f"data:image/png;base64,{encoded}"

    except Exception:
        return ""


@auth_bp.route("/security/2fa/start", methods=["POST"])
@login_required
def start_2fa_setup():
    """
    Begin 2FA setup.
    Creates a secret, displays QR code, but does not enable 2FA yet.
    """
    user = begin_2fa_setup(current_user.id)

    if not user:
        flash("Unable to start 2FA setup.", "error")
        return redirect(url_for("auth.security_settings"))

    provisioning_uri = get_totp_provisioning_uri(user)
    qr_code_data = build_qr_code_data_uri(provisioning_uri)

    return render_template(
        "profile_security.html",
        user=user,
        current_user=current_user,
        qr_code_data=qr_code_data,
        recovery_codes=None,
        show_2fa_confirm=True,
    )


@auth_bp.route("/security/2fa/confirm", methods=["POST"])
@login_required
def confirm_2fa():
    """
    Confirm 2FA activation with a valid TOTP code.
    Recovery codes are shown once.
    """
    code = request.form.get("code", "").strip()

    success, recovery_codes = confirm_2fa_setup(current_user.id, code)

    user = find_user_by_id(current_user.id)

    if not success:
        flash("Invalid 2FA code. Please scan the QR code and try again.", "error")
        return redirect(url_for("auth.security_settings"))

    flash("2FA enabled successfully. Save your recovery codes now.", "success")

    return render_template(
        "profile_security.html",
        user=user,
        current_user=current_user,
        qr_code_data=None,
        recovery_codes=recovery_codes,
        show_2fa_confirm=False,
    )


@auth_bp.route("/security/2fa/disable", methods=["POST"])
@login_required
def disable_2fa_route():
    """
    Disable 2FA after password confirmation.
    """
    password = request.form.get("password", "")

    if disable_2fa(current_user.id, password):
        flash("2FA disabled.", "success")
    else:
        flash("Could not disable 2FA. Check your password.", "error")

    return redirect(url_for("auth.security_settings"))


# ============================================================
# 7. FUTURE EXPANSION BLOCKS
# ============================================================
# Phase 11 Part 2:
# - Protected dashboard/schedule route enforcement
# - Employee-only schedule views
#
# Phase 11 Part 3:
# - Password reset/change password
# - Manager-created accounts
#
# Phase 11 Part 4:
# - Rate limiting
# - Login audit trail
#
# Phase 11 Part 5+:
# - Shift swap/drop approval workflow
# - Employee portal
# - Manager approval queue