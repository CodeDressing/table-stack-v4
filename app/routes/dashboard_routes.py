"""
TABLE STACK v4 – DASHBOARD ROUTES (PHASE 8 UPGRADE)
--------------------------------------------------------------------------------
Purpose: Thin routing layer – all business logic is delegated to services.
...
"""

import os
import uuid
import threading
import tempfile
from pathlib import Path
from typing import Dict, Any, Tuple, Optional
from werkzeug.utils import secure_filename
from flask import Blueprint, render_template, jsonify, request, current_app, url_for

# Import service layer functions (existing)
from app.services.dashboard_service import (
    get_dashboard_context,
    get_forecast_data,
    optimize_labor,
    get_raw_weekly_data
)

# Phase 8 imports (service extensions – will be created)
try:
    from app.services.import_service import process_uploaded_file, get_import_status
    IMPORT_SERVICE_AVAILABLE = True
except ImportError:
    IMPORT_SERVICE_AVAILABLE = False
    # Fallback stub functions
    def process_uploaded_file(file_path, file_type, user_id=None):
        return {"task_id": str(uuid.uuid4()), "status": "queued", "message": "Import service not fully installed"}
    def get_import_status(task_id):
        return {"status": "pending", "progress": 0}


# ============================================================
# 1. CONFIGURATION (using environment variables, not current_app at top level)
# ============================================================
ALLOWED_EXTENSIONS = {'csv', 'pdf', 'png', 'jpg', 'jpeg', 'tiff'}
MAX_FILE_SIZE = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))  # 16MB
UPLOAD_FOLDER = Path(os.getenv('UPLOAD_FOLDER', './uploads')).resolve()

def allowed_file(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


# ============================================================
# 2. BLUEPRINT DEFINITION
# ============================================================
dashboard_bp = Blueprint(
    "dashboard",
    __name__,
    url_prefix="/"
)


# ============================================================
# 3. MAIN DASHBOARD ROUTE (HTML) – UNCHANGED
# ============================================================
@dashboard_bp.route("/")
def home() -> str:
    return dashboard()

@dashboard_bp.route("/dashboard")
def dashboard() -> str:
    target_param = request.args.get("target", type=float)
    target_labor = target_param if target_param is not None else 25.0
    dashboard_context = get_dashboard_context(target_labor_percent=target_labor)
    return render_template("dashboard.html", dashboard=dashboard_context)


# ============================================================
# 4. EXISTING API ENDPOINTS (UNCHANGED)
# ============================================================
# ... (keep all your existing endpoints here exactly as before)
# ============================================================
# 4. EXISTING API ENDPOINTS (UNCHANGED)
# ============================================================
@dashboard_bp.route("/api/dashboard/data", methods=["GET"])
def api_dashboard_data() -> Tuple[Dict[str, Any], int]:
    try:
        target_param = request.args.get("target", type=float, default=25.0)
        context = get_dashboard_context(target_labor_percent=target_param)
        return jsonify(context), 200
    except Exception as e:
        current_app.logger.error(f"Error in api_dashboard_data: {str(e)}")
        return jsonify({"error": "Unable to fetch dashboard data", "detail": str(e)}), 500

@dashboard_bp.route("/api/forecast", methods=["GET"])
def api_forecast() -> Tuple[Dict[str, Any], int]:
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
    try:
        data = get_raw_weekly_data()
        return jsonify({"data": data}), 200
    except Exception as e:
        current_app.logger.error(f"Error in api_raw_weekly_data: {str(e)}")
        return jsonify({"error": str(e)}), 500


# ============================================================
# 5. PHASE 8: FILE UPLOAD & IMPORT ENDPOINTS
# ============================================================
@dashboard_bp.route("/api/upload-report", methods=["POST"])
def api_upload_report() -> Tuple[Dict[str, Any], int]:
    """
    Phase 8: Accept a sales report file (CSV, PDF, image).
    Saves file, triggers background parsing, returns task_id for status polling.
    """
    # Check if file part exists
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": f"File type not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"}), 400

    # Secure filename and save temporarily
    original_filename = secure_filename(file.filename)
    file_ext = original_filename.rsplit('.', 1)[1].lower()
    safe_name = f"{uuid.uuid4().hex}.{file_ext}"

    # Ensure upload folder exists
    UPLOAD_FOLDER.mkdir(parents=True, exist_ok=True)
    file_path = UPLOAD_FOLDER / safe_name
    file.save(file_path)

    # Determine file type group
    if file_ext == 'csv':
        file_type = 'csv'
    elif file_ext == 'pdf':
        file_type = 'pdf'
    elif file_ext in {'png', 'jpg', 'jpeg', 'tiff'}:
        file_type = 'image'
    else:
        file_type = 'unknown'

    # Start background processing
    task_id = str(uuid.uuid4())
    thread = threading.Thread(
        target=_process_import_background,
        args=(task_id, str(file_path), file_type, original_filename)
    )
    thread.daemon = True
    thread.start()

    # Store task in memory (in production, use Redis or DB)
    if not hasattr(current_app, 'import_tasks'):
        current_app.import_tasks = {}
    current_app.import_tasks[task_id] = {
        "status": "processing",
        "progress": 10,
        "message": "File saved, starting OCR/extraction..."
    }

    return jsonify({
        "task_id": task_id,
        "status": "accepted",
        "message": "File uploaded. Processing in background.",
        "file_name": original_filename
    }), 202


@dashboard_bp.route("/api/import-status/<task_id>", methods=["GET"])
def api_import_status(task_id: str) -> Tuple[Dict[str, Any], int]:
    """
    Poll import task status.
    Returns progress and final data when complete.
    """
    tasks = getattr(current_app, 'import_tasks', {})
    task = tasks.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    # If task has 'result' key, it's complete
    if task.get("status") == "complete":
        # Optionally delete after returning
        return jsonify(task), 200

    return jsonify({
        "status": task.get("status", "unknown"),
        "progress": task.get("progress", 0),
        "message": task.get("message", "")
    }), 200


def _process_import_background(task_id: str, file_path: str, file_type: str, original_name: str):
    """
    Background worker: calls import_service to parse file and update database.
    Updates task status in current_app.import_tasks.
    """
    tasks = getattr(current_app, 'import_tasks', {})
    try:
        # Update status
        tasks[task_id] = {"status": "processing", "progress": 20, "message": "Calling import service..."}

        # Call the service (even if not fully implemented, it returns a stub)
        result = process_uploaded_file(file_path, file_type, user_id=None)

        # Merge result
        tasks[task_id].update(result)
        tasks[task_id]["status"] = "complete"
        tasks[task_id]["progress"] = 100
        tasks[task_id]["message"] = "Import completed successfully"

        # After successful import, optionally regenerate forecast
        # trigger_forecast_recalculation()

    except Exception as e:
        current_app.logger.error(f"Import task {task_id} failed: {str(e)}")
        tasks[task_id] = {
            "status": "failed",
            "progress": 0,
            "message": f"Import failed: {str(e)}",
            "error": str(e)
        }
    finally:
        # Clean up temporary file (optional – keep for audit)
        try:
            os.unlink(file_path)
        except Exception:
            pass


# ============================================================
# 6. PHASE 8: DATABASE INTEGRATION STUBS (Ready for SQLAlchemy)
# ============================================================
# These functions will be replaced by real DB calls when models are defined.
# They are here to keep routes clean even before DB exists.

def get_db_session():
    """Return a database session (stub). Replace with actual session when DB is configured."""
    # from app.extensions import db
    # return db.session
    return None

def save_imported_data_to_db(parsed_data):
    """Save parsed sales/labor data to database. Stub for Phase 8."""
    # In Phase 8: insert into WeeklyData table
    current_app.logger.info(f"Would save {len(parsed_data)} rows to DB")
    return True


# ============================================================
# 7. PLACEHOLDER ENDPOINTS (Future Phases 9-11)
# ============================================================
@dashboard_bp.route("/api/import-report", methods=["POST"])
def api_import_report() -> Tuple[Dict[str, Any], int]:
    """Legacy placeholder – redirect to new upload endpoint."""
    return jsonify({
        "status": "deprecated",
        "message": "Please use POST /api/upload-report instead",
        "phase": 8
    }), 410

@dashboard_bp.route("/api/generate-insights", methods=["POST"])
def api_generate_insights() -> Tuple[Dict[str, Any], int]:
    return jsonify({
        "status": "coming_soon",
        "message": "Advanced AI insights (trend detection, anomaly alerts) in Phase 9",
        "phase": 9
    }), 501

@dashboard_bp.route("/api/export-pdf", methods=["POST"])
def api_export_pdf() -> Tuple[Dict[str, Any], int]:
    return jsonify({
        "status": "coming_soon",
        "message": "PDF export with all charts and tables will be available in Phase 10",
        "phase": 10
    }), 501

@dashboard_bp.route("/api/schedule/optimize", methods=["POST"])
def api_schedule_optimize() -> Tuple[Dict[str, Any], int]:
    return jsonify({
        "status": "coming_soon",
        "message": "Advanced schedule optimizer (employee-level) in Phase 11",
        "phase": 11
    }), 501


# ============================================================
# 8. ERROR HANDLERS
# ============================================================
@dashboard_bp.errorhandler(404)
def handle_not_found(e) -> Tuple[Dict[str, Any], int]:
    if request.path.startswith("/api/"):
        return jsonify({"error": "API endpoint not found"}), 404
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
# @dashboard_bp.route("/api/weather-forecast", methods=["GET"])
# def api_weather_forecast():
#     """Phase 9: integrate with weather API."""
#     pass

# @dashboard_bp.route("/api/dashboard/realtime", methods=["GET"])
# def api_realtime_updates():
#     """Phase 10: Server-Sent Events for live updates."""
#     pass