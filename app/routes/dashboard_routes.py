"""
TABLE STACK v4 – DASHBOARD ROUTES
--------------------------------------------------------------------------------
Purpose: Thin routing layer – all business logic is delegated to services.
Rules: Routes stay small. Each endpoint does only HTTP request/response handling.

Structure:
1. Blueprint definition
2. Main dashboard route (HTML)
3. API endpoints (JSON)
   - Dashboard data
   - Forecast
   - Labor optimizer
4. Placeholder endpoints for future modules (with 501 "Coming Soon")
5. Error handlers

Ready for 10k+ lines: add new API routes at the bottom without breaking existing ones.
--------------------------------------------------------------------------------
"""

from flask import Blueprint, render_template, jsonify, request, current_app
from typing import Dict, Any, Tuple

# Import service layer functions
from app.services.dashboard_service import (
    get_dashboard_context,
    get_forecast_data,
    optimize_labor,
    get_raw_weekly_data
)

# ============================================================
# 1. BLUEPRINT DEFINITION
# ============================================================
dashboard_bp = Blueprint(
    "dashboard",
    __name__,
    url_prefix="/"  # future-proof: can change to "/dashboard" later
)


# ============================================================
# 2. MAIN DASHBOARD ROUTE (HTML)
# ============================================================
@dashboard_bp.route("/")
def home() -> str:
    """Root route – redirects to dashboard (or directly serves it)."""
    return dashboard()


@dashboard_bp.route("/dashboard")
def dashboard() -> str:
    """
    Main dashboard endpoint.
    Keeps route thin by delegating all logic to service layer.
    Optionally accepts query param 'target' to adjust status calculations.
    """
    target_param = request.args.get("target", type=float)
    target_labor = target_param if target_param is not None else 25.0

    # Build context using the service layer
    dashboard_context = get_dashboard_context(target_labor_percent=target_labor)

    return render_template(
        "dashboard.html",
        dashboard=dashboard_context
    )


# ============================================================
# 3. API ENDPOINTS (JSON)
# ============================================================
@dashboard_bp.route("/api/dashboard/data", methods=["GET"])
def api_dashboard_data() -> Tuple[Dict[str, Any], int]:
    """
    Return full dashboard context as JSON.
    Used by frontend for live updates without page reload.
    """
    try:
        target_param = request.args.get("target", type=float, default=25.0)
        context = get_dashboard_context(target_labor_percent=target_param)
        return jsonify(context), 200
    except Exception as e:
        current_app.logger.error(f"Error in api_dashboard_data: {str(e)}")
        return jsonify({"error": "Unable to fetch dashboard data", "detail": str(e)}), 500


@dashboard_bp.route("/api/forecast", methods=["GET"])
def api_forecast() -> Tuple[Dict[str, Any], int]:
    """
    Return forecast data.
    Query param: weeks (int, default=2) – number of weeks ahead.
    """
    try:
        weeks_ahead = request.args.get("weeks", default=2, type=int)
        if weeks_ahead < 1 or weeks_ahead > 12:
            return jsonify({"error": "weeks must be between 1 and 12"}), 400

        forecast = get_forecast_data(weeks_ahead=weeks_ahead)
        return jsonify({"forecast": forecast, "weeks": weeks_ahead}), 200
    except Exception as e:
        current_app.logger.error(f"Error in api_forecast: {str(e)}")
        return jsonify({"error": "Forecast generation failed", "detail": str(e)}), 500


@dashboard_bp.route("/api/optimize-labor", methods=["POST"])
def api_optimize_labor() -> Tuple[Dict[str, Any], int]:
    """
    Accept target labor % and return schedule optimization suggestions.
    Expects JSON body: { "target_labor_percent": 25.0 }
    """
    try:
        data = request.get_json(silent=True)
        if not data:
            return jsonify({"error": "Missing JSON body"}), 400

        target = data.get("target_labor_percent")
        if target is None:
            return jsonify({"error": "Missing 'target_labor_percent' field"}), 400

        if not isinstance(target, (int, float)) or target < 10 or target > 50:
            return jsonify({"error": "target_labor_percent must be between 10 and 50"}), 400

        result = optimize_labor(target_labor_percent=target)
        return jsonify(result), 200
    except Exception as e:
        current_app.logger.error(f"Error in api_optimize_labor: {str(e)}")
        return jsonify({"error": "Optimization failed", "detail": str(e)}), 500


@dashboard_bp.route("/api/raw-weekly-data", methods=["GET"])
def api_raw_weekly_data() -> Tuple[Dict[str, Any], int]:
    """
    Return raw weekly data (unformatted) for advanced exports or debugging.
    """
    try:
        data = get_raw_weekly_data()
        return jsonify({"data": data}), 200
    except Exception as e:
        current_app.logger.error(f"Error in api_raw_weekly_data: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ============================================================
# 4. PLACEHOLDER ENDPOINTS (Future Phases)
#    All return 501 Not Implemented with clear phase info
# ============================================================
@dashboard_bp.route("/api/import-report", methods=["POST"])
def api_import_report() -> Tuple[Dict[str, Any], int]:
    """
    Phase 8: Accept uploaded sales report (CSV, PDF, image) and run OCR/extraction.
    Currently placeholder.
    """
    return jsonify({
        "status": "coming_soon",
        "message": "Report import with OCR will be available in Phase 8",
        "phase": 8,
        "estimated_features": ["CSV import", "PDF sales report extraction", "Image OCR"]
    }), 501


@dashboard_bp.route("/api/generate-insights", methods=["POST"])
def api_generate_insights() -> Tuple[Dict[str, Any], int]:
    """
    Phase 9: AI-powered deep insights (beyond basic recommendations).
    Placeholder.
    """
    return jsonify({
        "status": "coming_soon",
        "message": "Advanced AI insights (trend detection, anomaly alerts) in Phase 9",
        "phase": 9
    }), 501


@dashboard_bp.route("/api/export-pdf", methods=["POST"])
def api_export_pdf() -> Tuple[Dict[str, Any], int]:
    """
    Phase 10: Generate PDF report of dashboard.
    Placeholder.
    """
    return jsonify({
        "status": "coming_soon",
        "message": "PDF export with all charts and tables will be available in Phase 10",
        "phase": 10
    }), 501


@dashboard_bp.route("/api/schedule/optimize", methods=["POST"])
def api_schedule_optimize() -> Tuple[Dict[str, Any], int]:
    """
    Phase 11: Full staff schedule optimization (hour by hour, employee level).
    Placeholder.
    """
    return jsonify({
        "status": "coming_soon",
        "message": "Advanced schedule optimizer (employee-level) in Phase 11",
        "phase": 11
    }), 501


# ============================================================
# 5. ERROR HANDLERS (Blueprint-specific)
# ============================================================
@dashboard_bp.errorhandler(404)
def handle_not_found(e) -> Tuple[Dict[str, Any], int]:
    """Return JSON for API 404 errors, but for routes it's handled globally."""
    if request.path.startswith("/api/"):
        return jsonify({"error": "API endpoint not found"}), 404
    # For non-API, let the global handler manage (or return basic)
    return render_template("404.html"), 404


@dashboard_bp.errorhandler(500)
def handle_server_error(e) -> Tuple[Dict[str, Any], int]:
    current_app.logger.error(f"Server error: {str(e)}")
    if request.path.startswith("/api/"):
        return jsonify({"error": "Internal server error"}), 500
    return render_template("500.html"), 500

# ============================================================
# FUTURE EXPANSION BLOCKS (add new API routes below)
# ============================================================
# Example: 
# @dashboard_bp.route("/api/weather-forecast", methods=["GET"])
# def api_weather_forecast():
#     """Phase 9: integrate with weather API."""
#     pass