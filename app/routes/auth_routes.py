"""
TABLE STACK v4 – AUTH ROUTES
------------------------------------------------------------
Login, logout, and secure session routing.
2FA-ready using auth_service.
------------------------------------------------------------
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session
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
)

auth_bp = Blueprint("auth", __name__)

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to continue."


@login_manager.user_loader
def load_user(user_id):
    return get_login_user(user_id)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect("/dashboard")

    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        user = verify_login_credentials(email, password)

        if not user:
            flash("Invalid email or password.", "error")
            return render_template("login.html")

        if user.get("totp_enabled"):
            session["pending_2fa_user_id"] = user["id"]
            session["remember_login"] = remember
            return redirect(url_for("auth.two_factor"))

        login_user(AuthUser(user), remember=remember)
        return redirect("/dashboard")

    return render_template("login.html")


@auth_bp.route("/2fa", methods=["GET", "POST"])
def two_factor():
    pending_user_id = session.get("pending_2fa_user_id")

    if not pending_user_id:
        return redirect(url_for("auth.login"))

    user = find_user_by_id(pending_user_id)

    if not user:
        session.pop("pending_2fa_user_id", None)
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        code = request.form.get("code", "").strip()
        remember = bool(session.get("remember_login"))

        if verify_totp_code(user, code) or verify_recovery_code(user, code):
            session.pop("pending_2fa_user_id", None)
            session.pop("remember_login", None)
            login_user(AuthUser(user), remember=remember)
            return redirect("/dashboard")

        flash("Invalid authentication code.", "error")

    return render_template("two_factor.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))