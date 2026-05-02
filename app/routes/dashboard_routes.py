"""
TABLE STACK v4 – DASHBOARD ROUTES
================================================================================
Purpose:
- Login-first dashboard routing
- Protected dashboard pages and APIs
- Sales/labor/forecast API endpoints
- Secure report upload pipeline
- Background import task tracking
- Future-ready modular route sections

Architecture Rule:
Routes stay thin.
Business logic belongs in app/services/.
Each numbered section is designed to be replaceable later.

Future Upgrade Pattern:
- Replace SECTION 04 to change dashboard routing
- Replace SECTION 05 to upgrade dashboard APIs
- Replace SECTION 06 to upgrade upload/import
- Replace SECTION 08 to upgrade placeholder modules
================================================================================
"""

# ==============================================================================
# SECTION 01 — IMPORTS
# ==============================================================================

import os
import uuid
import threading
from pathlib import Path
from typing import Any, Dict, Tuple

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.services.dashboard_service import (
    get_dashboard_context,
    get_forecast_data,
    get_raw_weekly_data,
    optimize_labor,
)


# ==============================================================================
# SECTION 02 — OPTIONAL SERVICE IMPORTS / SAFE FALLBACKS
# ==============================================================================

try:
    from app.services.import_service import process_uploaded_file, get_import_status
    IMPORT_SERVICE_AVAILABLE = True
except ImportError:
    IMPORT_SERVICE_AVAILABLE = False

    def process_uploaded_file(file_path, file_type, user_id=None):
        return {
            "task_id": str(uuid.uuid4()),
            "status": "queued",
            "message": "Import service not fully installed.",
            "file_path": file_path,
            "file_type": file_type,
            "user_id": user_id,
        }

    def get_import_status(task_id):
        return {
            "status": "pending",
            "progress": 0,
            "task_id": task_id,
        }


# ==============================================================================
# SECTION 03 — CONFIGURATION / CONSTANTS
# ==============================================================================

ALLOWED_EXTENSIONS = {
    "csv",
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "tiff",
}

MAX_FILE_SIZE = int(
    os.getenv("MAX_CONTENT_LENGTH", 16 * 1024 * 1024)
)

UPLOAD_FOLDER = Path(
    os.getenv("UPLOAD_FOLDER", "./uploads")
).resolve()


def allowed_file(filename: str) -> bool:
    """
    Validate upload file extension.
    """
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


def get_file_type(file_extension: str) -> str:
    """
    Map file extension to import type.
    """
    if file_extension == "csv":
        return "csv"

    if file_extension == "pdf":
        return "pdf"

    if file_extension in {"png", "jpg", "jpeg", "tiff"}:
        return "image"

    return "unknown"


def get_current_user_id() -> str | None:
    """
    Safely return current logged-in user ID for task ownership/auditing.
    """
    if current_user and current_user.is_authenticated:
        return str(current_user.get_id())

    return None


# ==============================================================================
# SECTION 04 — BLUEPRINT
# ==============================================================================

dashboard_bp = Blueprint(
    "dashboard",
    __name__,
    url_prefix="/",
)


# ==============================================================================
# SECTION 05 — PAGE ROUTES
# ==============================================================================

@dashboard_bp.route("/")
def home():
    """
    Login-first application front door.

    Logged out:
        / -> /login

    Logged in:
        / -> /dashboard
    """
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.dashboard"))

    return redirect(url_for("auth.login"))


@dashboard_bp.route("/dashboard")
@login_required
def dashboard() -> str:
    """
    Protected main dashboard page.
    """
    target_param = request.args.get("target", type=float)
    target_labor = target_param if target_param is not None else 25.0

    dashboard_context = get_dashboard_context(
        target_labor_percent=target_labor
    )

    return render_template(
        "dashboard.html",
        dashboard=dashboard_context,
        user=current_user,
    )


# ==============================================================================
# SECTION 06 — CORE DASHBOARD API ENDPOINTS
# ==============================================================================

@dashboard_bp.route("/api/dashboard/data", methods=["GET"])
@login_required
def api_dashboard_data() -> Tuple[Dict[str, Any], int]:
    """
    Return full dashboard context as JSON.
    Used by frontend for live updates without page reload.
    """
    try:
        target_param = request.args.get(
            "target",
            type=float,
            default=25.0,
        )

        context = get_dashboard_context(
            target_labor_percent=target_param
        )

        return jsonify(context), 200

    except Exception as error:
        current_app.logger.error(
            f"Error in api_dashboard_data: {str(error)}"
        )
        return jsonify({
            "error": "Unable to fetch dashboard data",
            "detail": str(error),
        }), 500


@dashboard_bp.route("/api/forecast", methods=["GET"])
@login_required
def api_forecast() -> Tuple[Dict[str, Any], int]:
    """
    Return forecast data.

    Query:
        weeks: int between 1 and 12
    """
    try:
        weeks_ahead = request.args.get(
            "weeks",
            default=2,
            type=int,
        )

        if weeks_ahead < 1 or weeks_ahead > 12:
            return jsonify({
                "error": "weeks must be between 1 and 12"
            }), 400

        forecast = get_forecast_data(
            weeks_ahead=weeks_ahead
        )

        return jsonify({
            "forecast": forecast,
            "weeks": weeks_ahead,
        }), 200

    except Exception as error:
        current_app.logger.error(
            f"Error in api_forecast: {str(error)}"
        )
        return jsonify({
            "error": "Forecast generation failed",
            "detail": str(error),
        }), 500


@dashboard_bp.route("/api/optimize-labor", methods=["POST"])
@login_required
def api_optimize_labor() -> Tuple[Dict[str, Any], int]:
    """
    Accept target labor % and return labor optimization suggestions.

    Expected JSON:
        {
            "target_labor_percent": 25.0
        }
    """
    try:
        data = request.get_json(silent=True)

        if not data:
            return jsonify({
                "error": "Missing JSON body"
            }), 400

        target = data.get("target_labor_percent")

        if target is None:
            return jsonify({
                "error": "Missing 'target_labor_percent' field"
            }), 400

        if not isinstance(target, (int, float)) or target < 10 or target > 50:
            return jsonify({
                "error": "target_labor_percent must be between 10 and 50"
            }), 400

        result = optimize_labor(
            target_labor_percent=target
        )

        return jsonify(result), 200

    except Exception as error:
        current_app.logger.error(
            f"Error in api_optimize_labor: {str(error)}"
        )
        return jsonify({
            "error": "Optimization failed",
            "detail": str(error),
        }), 500


@dashboard_bp.route("/api/raw-weekly-data", methods=["GET"])
@login_required
def api_raw_weekly_data() -> Tuple[Dict[str, Any], int]:
    """
    Return raw weekly data for advanced exports/debugging.
    """
    try:
        data = get_raw_weekly_data()
        return jsonify({"data": data}), 200

    except Exception as error:
        current_app.logger.error(
            f"Error in api_raw_weekly_data: {str(error)}"
        )
        return jsonify({
            "error": str(error)
        }), 500


# ==============================================================================
# SECTION 07 — REPORT UPLOAD / IMPORT PIPELINE
# ==============================================================================

@dashboard_bp.route("/api/upload-report", methods=["POST"])
@login_required
def api_upload_report() -> Tuple[Dict[str, Any], int]:
    """
    Upload a sales/labor report file.

    Accepted:
    - CSV
    - PDF
    - Image files

    Returns:
    - task_id for polling
    """
    if "file" not in request.files:
        return jsonify({
            "error": "No file part"
        }), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({
            "error": "No selected file"
        }), 400

    if not allowed_file(file.filename):
        return jsonify({
            "error": "File type not allowed",
            "allowed": sorted(ALLOWED_EXTENSIONS),
        }), 400

    original_filename = secure_filename(file.filename)
    file_extension = original_filename.rsplit(".", 1)[1].lower()
    file_type = get_file_type(file_extension)

    safe_name = f"{uuid.uuid4().hex}.{file_extension}"

    UPLOAD_FOLDER.mkdir(
        parents=True,
        exist_ok=True,
    )

    file_path = UPLOAD_FOLDER / safe_name
    file.save(file_path)

    task_id = str(uuid.uuid4())
    user_id = get_current_user_id()

    app = current_app._get_current_object()

    if not hasattr(app, "import_tasks"):
        app.import_tasks = {}

    app.import_tasks[task_id] = {
        "task_id": task_id,
        "status": "processing",
        "progress": 10,
        "message": "File saved. Starting extraction...",
        "file_name": original_filename,
        "file_type": file_type,
        "user_id": user_id,
    }

    thread = threading.Thread(
        target=_process_import_background,
        args=(
            app,
            task_id,
            str(file_path),
            file_type,
            original_filename,
            user_id,
        ),
        daemon=True,
    )
    thread.start()

    return jsonify({
        "task_id": task_id,
        "status": "accepted",
        "message": "File uploaded. Processing in background.",
        "file_name": original_filename,
        "file_type": file_type,
    }), 202


@dashboard_bp.route("/api/import-status/<task_id>", methods=["GET"])
@login_required
def api_import_status(task_id: str) -> Tuple[Dict[str, Any], int]:
    """
    Poll import task status.
    """
    tasks = getattr(current_app, "import_tasks", {})
    task = tasks.get(task_id)

    if not task:
        return jsonify({
            "error": "Task not found"
        }), 404

    return jsonify(task), 200


def _process_import_background(
    app,
    task_id: str,
    file_path: str,
    file_type: str,
    original_name: str,
    user_id: str | None,
) -> None:
    """
    Background import worker.

    Important:
    Runs inside app.app_context() so logging/current_app work safely.
    """
    with app.app_context():
        tasks = getattr(app, "import_tasks", {})

        try:
            tasks[task_id] = {
                "task_id": task_id,
                "status": "processing",
                "progress": 25,
                "message": "Calling import service...",
                "file_name": original_name,
                "file_type": file_type,
                "user_id": user_id,
            }

            result = process_uploaded_file(
                file_path=file_path,
                file_type=file_type,
                user_id=user_id,
            )

            tasks[task_id].update(result)
            tasks[task_id]["status"] = "complete"
            tasks[task_id]["progress"] = 100
            tasks[task_id]["message"] = "Import completed successfully."

        except Exception as error:
            app.logger.error(
                f"Import task {task_id} failed: {str(error)}"
            )
            tasks[task_id] = {
                "task_id": task_id,
                "status": "failed",
                "progress": 0,
                "message": f"Import failed: {str(error)}",
                "error": str(error),
                "file_name": original_name,
                "file_type": file_type,
                "user_id": user_id,
            }

        finally:
            try:
                os.unlink(file_path)
            except Exception:
                pass


# ==============================================================================
# SECTION 08 — DATABASE / IMPORT HELPERS
# ==============================================================================

def get_db_session():
    """
    Future DB session hook.

    Replace this section when real DB extension is finalized.
    """
    return None


def save_imported_data_to_db(parsed_data):
    """
    Future imported-data persistence hook.
    """
    try:
        count = len(parsed_data)
    except TypeError:
        count = 0

    current_app.logger.info(
        f"Would save {count} imported rows to DB."
    )

    return True


# ==============================================================================
# SECTION 09 — FUTURE / PLACEHOLDER API ENDPOINTS
# ==============================================================================

@dashboard_bp.route("/api/import-report", methods=["POST"])
@login_required
def api_import_report() -> Tuple[Dict[str, Any], int]:
    """
    Legacy import endpoint.

    Kept for frontend compatibility.
    """
    return jsonify({
        "status": "deprecated",
        "message": "Please use POST /api/upload-report instead.",
        "phase": 8,
    }), 410


@dashboard_bp.route("/api/generate-insights", methods=["POST"])
@login_required
def api_generate_insights() -> Tuple[Dict[str, Any], int]:
    """
    Future advanced AI insights endpoint.
    """
    return jsonify({
        "status": "coming_soon",
        "message": "Advanced AI insights will be available in a future phase.",
        "phase": 11,
    }), 501


@dashboard_bp.route("/api/export-pdf", methods=["POST"])
@login_required
def api_export_pdf() -> Tuple[Dict[str, Any], int]:
    """
    Future PDF export endpoint.
    """
    return jsonify({
        "status": "coming_soon",
        "message": "PDF export will be available in a future phase.",
        "phase": 11,
    }), 501


@dashboard_bp.route("/api/schedule/optimize", methods=["POST"])
@login_required
def api_schedule_optimize() -> Tuple[Dict[str, Any], int]:
    """
    Future employee-level schedule optimizer endpoint.
    """
    return jsonify({
        "status": "coming_soon",
        "message": "Advanced employee-level schedule optimization will be available in a future phase.",
        "phase": 11,
    }), 501


# ==============================================================================
# SECTION 10 — ERROR HANDLERS
# ==============================================================================

@dashboard_bp.errorhandler(404)
def handle_not_found(error):
    """
    Dashboard blueprint 404 handler.
    """
    if request.path.startswith("/api/"):
        return jsonify({
            "error": "API endpoint not found"
        }), 404

    return render_template("404.html"), 404


@dashboard_bp.errorhandler(500)
def handle_server_error(error):
    """
    Dashboard blueprint 500 handler.
    """
    current_app.logger.error(
        f"Dashboard server error: {str(error)}"
    )

    if request.path.startswith("/api/"):
        return jsonify({
            "error": "Internal server error"
        }), 500

    return render_template("500.html"), 500


# ==============================================================================
# SECTION 11 — FUTURE EXPANSION BLOCKS
# ==============================================================================
# Future Section Ideas:
#
# SECTION 11A — Weather forecast API
# SECTION 11B — Server-Sent Events / live dashboard updates
# SECTION 11C — PDF export implementation
# SECTION 11D — Sales report OCR finalization
# SECTION 11E — Manager-only dashboard admin tools
#
# Add new blocks below this line without modifying previous sections.
# ==============================================================================