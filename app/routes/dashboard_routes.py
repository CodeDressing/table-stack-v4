from flask import Blueprint, render_template

from app.services.dashboard_service import get_dashboard_context


dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
def home():
    return dashboard()


@dashboard_bp.route("/dashboard")
def dashboard():
    dashboard_context = get_dashboard_context()

    return render_template(
        "dashboard.html",
        dashboard=dashboard_context
    )