from flask import Blueprint, render_template

from app.services.dashboard_service import get_dashboard_context


dashboard_bp = Blueprint(
    "dashboard",
    __name__,
    url_prefix="/"  # future-proofing for modular routing
)


@dashboard_bp.route("/")
def home():
    """
    Entry route.
    Can later redirect to user-specific dashboards or login.
    """
    return dashboard()


@dashboard_bp.route("/dashboard")
def dashboard():
    """
    Main dashboard endpoint.

    Keeps route thin by delegating all logic to service layer.
    """

    dashboard_context = get_dashboard_context()

    return render_template(
        "dashboard.html",
        dashboard=dashboard_context
    )