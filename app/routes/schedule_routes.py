"""
TABLE STACK v4 – SCHEDULE ROUTES
================================================================================
Purpose:
- Protected staffing setup
- Protected schedule viewing
- Employee-aware schedule assignment
- Schedule API endpoints
- Employee availability API endpoints

Architecture Rule:
Routes stay thin.
Employee loading belongs in employee_service.
Schedule analysis/generation belongs in schedule_intelligence_service.

Future Upgrade Pattern:
- Replace SECTION 05 to change setup behavior
- Replace SECTION 06 to upgrade schedule viewing
- Replace SECTION 08 to expand APIs
================================================================================
"""

# ==============================================================================
# SECTION 01 — IMPORTS
# ==============================================================================

from datetime import datetime, timedelta
from typing import Any, Dict, List

from flask import (
    Blueprint,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)

from flask_login import login_required

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
    find_available_employees,
    get_default_staffing_plan,
    get_staffing_plan_for_week,
    list_staffing_plans,
    load_staffing_plan,
    parse_staffing_plan_from_form,
    save_staffing_plan,
    staffing_field_name,
)


# ==============================================================================
# SECTION 02 — BLUEPRINT
# ==============================================================================

schedule_bp = Blueprint(
    "schedule",
    __name__,
    url_prefix="/schedule",
)


# ==============================================================================
# SECTION 03 — DATE / PLAN HELPERS
# ==============================================================================

def get_monday_from_request() -> str:
    """
    Resolve selected week start and snap it to Monday.
    """
    week_start_str = request.args.get("week_start", "")

    if week_start_str:
        try:
            selected_date = datetime.strptime(
                week_start_str,
                "%Y-%m-%d",
            ).date()
        except ValueError:
            selected_date = datetime.now().date()
    else:
        selected_date = datetime.now().date()

    monday = selected_date - timedelta(days=selected_date.weekday())
    return monday.isoformat()


def build_past_weeks_dropdown() -> List[Dict[str, Any]]:
    """
    Build dropdown options from saved staffing plans.
    """
    past_weeks = []

    for plan in list_staffing_plans():
        if plan.get("week_start"):
            past_weeks.append({
                "plan_id": plan.get("id"),
                "label": f"Week of {plan.get('week_start')}",
            })

    return past_weeks


def resolve_staffing_plan_for_request(week_start: str) -> Dict[str, Any]:
    """
    Resolve active plan source:
    1. copy_plan query param
    2. saved plan for week
    3. default plan
    """
    copy_plan_id = request.args.get("copy_plan", type=int)

    if copy_plan_id:
        copied = load_staffing_plan(copy_plan_id)

        if copied and isinstance(copied, dict):
            return copied.get(
                "plan_data",
                get_default_staffing_plan(),
            )

    saved_for_week = get_staffing_plan_for_week(week_start)

    if saved_for_week:
        return saved_for_week

    return get_default_staffing_plan()


# ==============================================================================
# SECTION 04 — SCHEDULE BUILDING HELPER
# ==============================================================================

def build_schedule_from_plan(
    plan: Dict[str, Any],
    employees: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Dict[str, List[Dict[str, Any]]]]]:
    """
    Build full schedule:
        schedule[day][shift][role] = [employee, employee, ...]

    Current assignment logic:
    - Match role
    - Match availability / custom shift window
    - Assign first available employees up to needed count

    Future replacement target:
    Replace this section with fair rotation, hour balancing,
    swap/drop awareness, and manager approval state.
    """
    schedule = {}

    for day in DAYS:
        schedule[day] = {}

        for shift in SHIFTS:
            schedule[day][shift] = {}

            for role in ROLES:
                needed = plan.get(day, {}).get(shift, {}).get(role, 0)

                if needed <= 0:
                    schedule[day][shift][role] = []
                    continue

                available = find_available_employees(
                    employees=employees,
                    role=role,
                    day=day,
                    shift=shift,
                )

                assigned = available[:needed]

                schedule[day][shift][role] = [
                    {
                        "id": employee.get("id"),
                        "name": employee.get("name", "Unnamed Employee"),
                        "role": employee.get("role", role),
                    }
                    for employee in assigned
                ]

    return schedule


# ==============================================================================
# SECTION 05 — SCHEDULE SETUP PAGE
# ==============================================================================

@schedule_bp.route("/setup", methods=["GET", "POST"])
@login_required
def schedule_setup():
    """
    Protected staffing plan setup page.

    GET:
        Load/create plan for selected week.

    POST:
        Save staffing plan and preview analysis.
    """
    week_start = get_monday_from_request()
    past_weeks = build_past_weeks_dropdown()
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
        )

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
    )


# ==============================================================================
# SECTION 06 — SCHEDULE VIEW PAGE
# ==============================================================================

@schedule_bp.route("/view/<int:plan_id>")
@login_required
def view_schedule(plan_id: int):
    """
    Protected schedule view.

    Shows employee names by:
    - Day
    - Shift
    - Role
    """
    plan_data = load_staffing_plan(plan_id)

    if not plan_data:
        return "Plan not found", 404

    employees = get_all_employees()
    plan = plan_data.get("plan_data", {})

    schedule = build_schedule_from_plan(
        plan=plan,
        employees=employees,
    )

    return render_template(
        "schedule_view.html",
        schedule=schedule,
        days=DAYS,
        shifts=SHIFTS,
        roles=ROLES,
        plan_name=plan_data.get("name", f"Plan #{plan_id}"),
        week_start=plan_data.get("week_start", ""),
        plan_id=plan_id,
    )


# ==============================================================================
# SECTION 07 — EMPLOYEE AVAILABILITY PAGE
# ==============================================================================

@schedule_bp.route("/employees")
@login_required
def employee_availability():
    """
    Protected employee availability page.
    """
    employees = get_all_employees()

    return render_template(
        "employee_availability.html",
        employees=employees,
        days=DAYS,
    )


# ==============================================================================
# SECTION 08 — PLAN API ENDPOINTS
# ==============================================================================

@schedule_bp.route("/api/plans", methods=["GET"])
@login_required
def api_plans():
    """
    Return all saved staffing plans.
    """
    return jsonify(list_staffing_plans()), 200


@schedule_bp.route("/api/plans/<int:plan_id>", methods=["GET"])
@login_required
def api_plan(plan_id: int):
    """
    Return one staffing plan with analysis.
    """
    data = load_staffing_plan(plan_id)

    if not data:
        return jsonify({
            "error": "Plan not found"
        }), 404

    analysis = analyze_staffing_plan(
        data.get("plan_data", {})
    )

    return jsonify({
        "id": plan_id,
        "name": data.get("name"),
        "plan_data": data.get("plan_data"),
        "analysis": analysis,
        "week_start": data.get("week_start"),
        "notes": data.get("notes", ""),
    }), 200


@schedule_bp.route("/api/plans/<int:plan_id>", methods=["DELETE"])
@login_required
def api_delete_plan(plan_id: int):
    """
    Delete a saved plan.
    """
    success = delete_staffing_plan(plan_id)

    return jsonify({
        "success": success
    }), 200 if success else 500


@schedule_bp.route("/api/analyze-live", methods=["POST"])
@login_required
def api_analyze_live():
    """
    Analyze a staffing plan without saving it.
    """
    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "error": "No data provided"
        }), 400

    staffing_plan = data.get("staffing_plan", {})
    analysis = analyze_staffing_plan(staffing_plan)

    return jsonify(analysis), 200


# ==============================================================================
# SECTION 09 — RESOLVED SCHEDULE API ENDPOINTS
# ==============================================================================

@schedule_bp.route("/api/schedule/<int:plan_id>", methods=["GET"])
@login_required
def api_schedule(plan_id: int):
    """
    Return fully resolved employee schedule as JSON.
    """
    plan_data = load_staffing_plan(plan_id)

    if not plan_data:
        return jsonify({
            "error": "Plan not found"
        }), 404

    employees = get_all_employees()
    plan = plan_data.get("plan_data", {})

    schedule = build_schedule_from_plan(
        plan=plan,
        employees=employees,
    )

    return jsonify({
        "plan_id": plan_id,
        "plan_name": plan_data.get("name", f"Plan #{plan_id}"),
        "week_start": plan_data.get("week_start", ""),
        "schedule": schedule,
        "days": DAYS,
        "shifts": SHIFTS,
        "roles": ROLES,
    }), 200


# ==============================================================================
# SECTION 10 — EMPLOYEE API ENDPOINTS
# ==============================================================================

@schedule_bp.route("/api/employee/<int:employee_id>", methods=["GET"])
@login_required
def api_get_employee(employee_id: int):
    """
    Return one employee by ID.
    """
    employees = get_all_employees()

    employee = next(
        (
            item for item in employees
            if item.get("id") == employee_id
        ),
        None,
    )

    if not employee:
        return jsonify({
            "error": "Employee not found"
        }), 404

    return jsonify(employee), 200


@schedule_bp.route("/api/employee/<int:employee_id>", methods=["PUT"])
@login_required
def api_update_employee(employee_id: int):
    """
    Update employee availability/preferences.
    """
    data = request.get_json(silent=True)

    if not data:
        return jsonify({
            "error": "No data provided"
        }), 400

    success = update_employee(
        employee_id,
        data,
    )

    return jsonify({
        "success": success
    }), 200 if success else 500


# ==============================================================================
# SECTION 11 — FUTURE SHIFT SWAP / DROP ENDPOINTS
# ==============================================================================

@schedule_bp.route("/api/shifts/swap-request", methods=["POST"])
@login_required
def api_shift_swap_request():
    """
    Future:
    Employee requests a shift swap.
    Manager approval required before finalized.
    """
    return jsonify({
        "status": "coming_soon",
        "message": "Shift swap requests with manager approval will be available in a future phase.",
        "phase": 12,
    }), 501


@schedule_bp.route("/api/shifts/drop-request", methods=["POST"])
@login_required
def api_shift_drop_request():
    """
    Future:
    Employee requests to drop a shift.
    Manager approval required before finalized.
    """
    return jsonify({
        "status": "coming_soon",
        "message": "Shift drop requests with manager approval will be available in a future phase.",
        "phase": 12,
    }), 501


# ==============================================================================
# SECTION 12 — FUTURE EXPANSION BLOCKS
# ==============================================================================
# Future Section Ideas:
#
# SECTION 12A — Manager approval queue
# SECTION 12B — Employee schedule acceptance
# SECTION 12C — Schedule publishing
# SECTION 12D — Shift swap/drop persistence
# SECTION 12E — Per-employee schedule dashboard
#
# Add new blocks below this line without modifying previous sections.
# ==============================================================================