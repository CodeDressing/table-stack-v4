"""
TABLE STACK v4 – SCHEDULE ROUTES (PHASE 12 FULL UPGRADE)
================================================================================
PHASE 11/12 – Complete Master Schedule Management + Staffing Entry Flow

Purpose:
- Protected staffing setup with entry dialog (Start New Master / Import Master)
- Master schedule CRUD (save, list, load, delete)
- Full schedule view (editable by day/shift/role)
- Employee availability management
- Secure, logged, and future‑ready

SECTION MAP
01. Imports
02. Blueprint
03. Helpers (date, plan resolution, editor label)
04. Staffing setup page (entry dialog & master flow)
05. Schedule view page
06. Employee availability page
07. Staffing plan API endpoints (list, get, delete, analyze)
08. Master schedule management API endpoints (list, save, get, delete)
09. Master schedule editing endpoints (by day, shift, role)
10. Employee API endpoints
11. Future shift swap/drop endpoints
12. Future expansion blocks
================================================================================
"""

# ==============================================================================
# SECTION 01 — IMPORTS
# ==============================================================================

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from flask import (
    Blueprint,
    jsonify,
    render_template,
    request,
    current_app,
    abort,
)
from flask_login import login_required, current_user

from app.services.employee_service import (
    get_all_employees,
    update_employee,
)
from app.services.schedule_intelligence_service import (
    DAYS,
    SHIFTS,
    ROLES,
    analyze_staffing_plan,
    delete_staffing_plan,
    generate_and_save_master_schedule,
    generate_schedule_from_plan,
    get_default_staffing_plan,
    get_master_schedule_for_week,
    get_staffing_plan_for_week,
    list_staffing_plans,
    load_staffing_plan,
    parse_staffing_plan_from_form,
    save_staffing_plan,
    staffing_field_name,
    update_master_schedule_day,
    update_master_schedule_shift,
    update_master_schedule_role,
)

# ==============================================================================
# SECTION 02 — BLUEPRINT
# ==============================================================================

schedule_bp = Blueprint("schedule", __name__, url_prefix="/schedule")

# ==============================================================================
# SECTION 03 — HELPERS
# ==============================================================================

def get_monday_from_request() -> str:
    """Resolve selected week start and snap it to Monday."""
    week_start_str = request.args.get("week_start", "")
    if week_start_str:
        try:
            selected_date = datetime.strptime(week_start_str, "%Y-%m-%d").date()
        except ValueError:
            selected_date = datetime.now().date()
    else:
        selected_date = datetime.now().date()
    monday = selected_date - timedelta(days=selected_date.weekday())
    return monday.isoformat()

def build_past_weeks_dropdown() -> List[Dict[str, Any]]:
    """Build dropdown options from saved staffing plans."""
    past_weeks = []
    for plan in list_staffing_plans():
        if plan.get("week_start"):
            past_weeks.append({
                "plan_id": plan.get("id"),
                "label": f"Week of {plan.get('week_start')}",
            })
    return past_weeks

def resolve_staffing_plan_for_request(week_start: str) -> Dict[str, Any]:
    """Resolve active plan: copy_plan param, saved plan for week, or default."""
    copy_plan_id = request.args.get("copy_plan", type=int)
    if copy_plan_id:
        copied = load_staffing_plan(copy_plan_id)
        if copied and isinstance(copied, dict):
            return copied.get("plan_data", get_default_staffing_plan())
    saved_for_week = get_staffing_plan_for_week(week_start)
    if saved_for_week:
        return saved_for_week
    return get_default_staffing_plan()

def current_editor_label() -> str:
    """Friendly editor label for audit logs."""
    if current_user and current_user.is_authenticated:
        return getattr(current_user, "email", "authenticated_user")
    return "system"


# ==============================================================================
# SECTION 04 — STAFFING SETUP PAGE (with entry dialog & master flow)
# ==============================================================================

@schedule_bp.route("/setup", methods=["GET", "POST"])
@login_required
def schedule_setup():
    """
    Staffing plan setup page with entry decision:
    - ?reset=true forces reset to defaults
    - ?master_id=123 loads a saved master
    - Otherwise uses normal plan resolution (week based)
    """
    week_start = get_monday_from_request()
    past_weeks = build_past_weeks_dropdown()

    # Check for reset or master load
    reset = request.args.get("reset", "").lower() == "true"
    master_id = request.args.get("master_id", type=int)

    if reset:
        staffing_plan = get_default_staffing_plan()
    elif master_id:
        master = load_staffing_plan(master_id)
        if master and master.get("is_master", False):
            staffing_plan = master.get("plan_data", get_default_staffing_plan())
        else:
            staffing_plan = get_default_staffing_plan()
    else:
        staffing_plan = resolve_staffing_plan_for_request(week_start)

    if request.method == "POST":
        staffing_plan = parse_staffing_plan_from_form(request.form)
        plan_id = save_staffing_plan(
            staffing_plan,
            name=f"Plan {week_start}",
            notes="",
            set_active=False,
            week_start=week_start,
        )
        master_schedule = generate_and_save_master_schedule(
            week_start=week_start,
            staffing_plan=staffing_plan,
            source_plan_id=plan_id,
        )
        analysis = analyze_staffing_plan(staffing_plan)
        return render_template(
            "schedule_setup.html",
            days=DAYS,
            shifts=SHIFTS,
            roles=ROLES,
            staffing_plan=staffing_plan,
            staffing_field_name=staffing_field_name,
            analysis=analysis,
            week_start=week_start,
            past_weeks=past_weeks,
            plan_id=plan_id,
            master_schedule=master_schedule,
        )

    master_schedule = get_master_schedule_for_week(week_start)
    return render_template(
        "schedule_setup.html",
        days=DAYS,
        shifts=SHIFTS,
        roles=ROLES,
        staffing_plan=staffing_plan,
        staffing_field_name=staffing_field_name,
        analysis=None,
        week_start=week_start,
        past_weeks=past_weeks,
        master_schedule=master_schedule,
    )


# ==============================================================================
# SECTION 05 — SCHEDULE VIEW PAGE
# ==============================================================================

@schedule_bp.route("/view/<int:plan_id>")
@login_required
def view_schedule(plan_id: int):
    """Display full editable master schedule for a given plan."""
    plan_data = load_staffing_plan(plan_id)
    if not plan_data:
        abort(404, description="Plan not found")

    week_start = plan_data.get("week_start", "")
    master_schedule = get_master_schedule_for_week(week_start) if week_start else None

    if master_schedule:
        schedule = master_schedule.get("schedule", {})
    else:
        plan = plan_data.get("plan_data", {})
        schedule = generate_schedule_from_plan(plan)

    return render_template(
        "schedule_view.html",
        schedule=schedule,
        days=DAYS,
        shifts=SHIFTS,
        roles=ROLES,
        plan_name=plan_data.get("name", f"Plan #{plan_id}"),
        week_start=week_start,
        plan_id=plan_id,
        master_schedule=master_schedule,
    )


# ==============================================================================
# SECTION 06 — EMPLOYEE AVAILABILITY PAGE
# ==============================================================================

@schedule_bp.route("/employees")
@login_required
def employee_availability():
    """Employee availability and preferences editor."""
    employees = get_all_employees()
    return render_template("employee_availability.html", employees=employees, days=DAYS)


# ==============================================================================
# SECTION 07 — STAFFING PLAN API (legacy & general)
# ==============================================================================

@schedule_bp.route("/api/plans", methods=["GET"])
@login_required
def api_plans():
    """List all staffing plans (not only masters)."""
    return jsonify(list_staffing_plans()), 200

@schedule_bp.route("/api/plans/<int:plan_id>", methods=["GET"])
@login_required
def api_plan(plan_id: int):
    """Get one plan with analysis."""
    data = load_staffing_plan(plan_id)
    if not data:
        return jsonify({"error": "Plan not found"}), 404
    analysis = analyze_staffing_plan(data.get("plan_data", {}))
    return jsonify({
        "id": plan_id,
        "name": data.get("name"),
        "plan_data": data.get("plan_data"),
        "analysis": analysis,
        "week_start": data.get("week_start"),
        "notes": data.get("notes", ""),
        "is_master": data.get("is_master", False),
    }), 200

@schedule_bp.route("/api/plans/<int:plan_id>", methods=["DELETE"])
@login_required
def api_delete_plan(plan_id: int):
    """Delete a staffing plan."""
    success = delete_staffing_plan(plan_id)
    return jsonify({"success": success}), 200 if success else 500

@schedule_bp.route("/api/analyze-live", methods=["POST"])
@login_required
def api_analyze_live():
    """Analyze a staffing plan without saving."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400
    staffing_plan = data.get("staffing_plan", {})
    analysis = analyze_staffing_plan(staffing_plan)
    return jsonify(analysis), 200


# ==============================================================================
# SECTION 08 — MASTER SCHEDULE MANAGEMENT (Phase 12 + Most Recent)
# ==============================================================================

@schedule_bp.route("/api/masters", methods=["GET"])
@login_required
def api_list_masters():
    """Return all saved master schedules (plans with is_master=True)."""
    all_plans = list_staffing_plans()
    masters = [p for p in all_plans if p.get("is_master", False)]
    return jsonify(masters), 200

@schedule_bp.route("/api/masters/recent", methods=["GET"])
@login_required
def api_most_recent_master():
    """Return the most recently updated master schedule."""
    all_plans = list_staffing_plans()
    masters = [p for p in all_plans if p.get("is_master", False)]
    if not masters:
        return jsonify({"error": "No master schedules found"}), 404
    # Sort by updated_at descending, then created_at
    recent = max(masters, key=lambda p: (p.get("updated_at") or "", p.get("created_at") or ""))
    return jsonify(recent), 200

@schedule_bp.route("/api/masters", methods=["POST"])
@login_required
def api_save_master():
    """Save current staffing plan as a master schedule."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400

    staffing_plan = data.get("staffing_plan")
    if not staffing_plan:
        return jsonify({"error": "Missing staffing_plan"}), 400

    name = data.get("name", f"Master {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    week_start = data.get("week_start", get_monday_from_request())

    plan_id = save_staffing_plan(
        plan_data=staffing_plan,
        name=name,
        notes="Master schedule saved from UI",
        is_master=True,
        week_start=week_start,
    )
    return jsonify({"success": True, "plan_id": plan_id}), 201

@schedule_bp.route("/api/masters/<int:master_id>", methods=["GET"])
@login_required
def api_get_master(master_id: int):
    """Load a master schedule by ID."""
    master = load_staffing_plan(master_id)
    if not master or not master.get("is_master", False):
        return jsonify({"error": "Master schedule not found"}), 404
    return jsonify(master), 200

@schedule_bp.route("/api/masters/<int:master_id>", methods=["DELETE"])
@login_required
def api_delete_master(master_id: int):
    """Delete a master schedule."""
    success = delete_staffing_plan(master_id)
    return jsonify({"success": success}), 200 if success else 500
# ==============================================================================
# SECTION 09 — RESOLVED SCHEDULE & EDITING ENDPOINTS
# ==============================================================================

@schedule_bp.route("/api/schedule/<int:plan_id>", methods=["GET"])
@login_required
def api_schedule(plan_id: int):
    """Return fully resolved schedule for a plan (prefer master schedule)."""
    plan_data = load_staffing_plan(plan_id)
    if not plan_data:
        return jsonify({"error": "Plan not found"}), 404

    week_start = plan_data.get("week_start", "")
    master_schedule = get_master_schedule_for_week(week_start) if week_start else None

    if master_schedule:
        schedule = master_schedule.get("schedule", {})
        source = "master_schedule"
    else:
        schedule = generate_schedule_from_plan(plan_data.get("plan_data", {}))
        source = "generated_plan"

    return jsonify({
        "plan_id": plan_id,
        "plan_name": plan_data.get("name", f"Plan #{plan_id}"),
        "week_start": week_start,
        "source": source,
        "master_schedule": master_schedule,
        "schedule": schedule,
        "days": DAYS,
        "shifts": SHIFTS,
        "roles": ROLES,
    }), 200

@schedule_bp.route("/api/master-schedule/<week_start>", methods=["GET"])
@login_required
def api_get_master_schedule(week_start: str):
    """Get current master schedule for week."""
    master = get_master_schedule_for_week(week_start)
    if not master:
        return jsonify({"error": "Master schedule not found", "week_start": week_start}), 404
    return jsonify(master), 200

@schedule_bp.route("/api/master-schedule/<week_start>/day/<day>", methods=["PUT"])
@login_required
def api_update_master_day(week_start: str, day: str):
    """Update full day (both shifts)."""
    data = request.get_json(silent=True) or {}
    day_payload = data.get("day_payload", data)
    updated = update_master_schedule_day(
        week_start=week_start,
        day=day,
        day_payload=day_payload,
        edited_by=current_editor_label(),
    )
    if not updated:
        return jsonify({"error": "Update failed"}), 400
    return jsonify({"success": True, "master_schedule": updated}), 200

@schedule_bp.route("/api/master-schedule/<week_start>/day/<day>/shift/<shift>", methods=["PUT"])
@login_required
def api_update_master_shift(week_start: str, day: str, shift: str):
    """Update one shift (all roles)."""
    data = request.get_json(silent=True) or {}
    shift_payload = data.get("shift_payload", data)
    updated = update_master_schedule_shift(
        week_start=week_start,
        day=day,
        shift=shift,
        shift_payload=shift_payload,
        edited_by=current_editor_label(),
    )
    if not updated:
        return jsonify({"error": "Update failed"}), 400
    return jsonify({"success": True, "master_schedule": updated}), 200

@schedule_bp.route("/api/master-schedule/<week_start>/day/<day>/shift/<shift>/role/<role>", methods=["PUT"])
@login_required
def api_update_master_role(week_start: str, day: str, shift: str, role: str):
    """Update one specific role assignment."""
    data = request.get_json(silent=True) or {}
    assignments = data.get("assignments", [])
    updated = update_master_schedule_role(
        week_start=week_start,
        day=day,
        shift=shift,
        role=role,
        assignments=assignments,
        edited_by=current_editor_label(),
    )
    if not updated:
        return jsonify({"error": "Update failed"}), 400
    return jsonify({"success": True, "master_schedule": updated}), 200


# ==============================================================================
# SECTION 10 — EMPLOYEE API ENDPOINTS
# ==============================================================================

@schedule_bp.route("/api/employee/<int:employee_id>", methods=["GET"])
@login_required
def api_get_employee(employee_id: int):
    """Get one employee by ID."""
    employees = get_all_employees()
    employee = next((e for e in employees if e.get("id") == employee_id), None)
    if not employee:
        return jsonify({"error": "Employee not found"}), 404
    return jsonify(employee), 200

@schedule_bp.route("/api/employee/<int:employee_id>", methods=["PUT"])
@login_required
def api_update_employee(employee_id: int):
    """Update employee availability/preferences."""
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data provided"}), 400
    success = update_employee(employee_id, data)
    return jsonify({"success": success}), 200 if success else 500


# ==============================================================================
# SECTION 11 — FUTURE SHIFT SWAP / DROP ENDPOINTS (stubs)
# ==============================================================================

@schedule_bp.route("/api/shifts/swap-request", methods=["POST"])
@login_required
def api_shift_swap_request():
    """Placeholder for employee shift swap request."""
    return jsonify({
        "status": "coming_soon",
        "message": "Shift swap requests with manager approval in Phase 13.",
        "phase": 13,
    }), 501

@schedule_bp.route("/api/shifts/drop-request", methods=["POST"])
@login_required
def api_shift_drop_request():
    """Placeholder for employee shift drop request."""
    return jsonify({
        "status": "coming_soon",
        "message": "Shift drop requests with manager approval in Phase 13.",
        "phase": 13,
    }), 501


# ==============================================================================
# SECTION 12 — FUTURE EXPANSION BLOCKS
# ==============================================================================
# - Manager approval queue for swaps/drops
# - Employee schedule acceptance
# - Schedule publishing (PDF/email)
# - Shift swap/drop persistence
# - Per-employee schedule dashboard
# - Real‑time notifications (WebSockets)
# ==============================================================================