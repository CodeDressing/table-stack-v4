from flask import Blueprint, render_template

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/")
def home():
    return render_template("dashboard.html")

@dashboard_bp.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")