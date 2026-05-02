"""
TABLE STACK v4 – SCHEDULE ROUTES (PHASE 8 UPGRADE)
------------------------------------------------------------
Handles:
- Schedule setup page (week selection, past plans, save)
- Schedule view page (employee assignments by name, shift, day)
- Employee availability page
- API endpoints for plans, schedule data, and employee updates

UPGRADED:
- view_schedule now uses get_all_employees() — no employee dropped
  due to zero hours or missing active flag
- Schedule view passes assigned employee names per role/shift/day
- New API endpoint: GET /api/schedule/<plan_id> for JSON schedule
- New API endpoint: GET /api/employee/<emp_id> for single employee
- All existing functions and routes preserved
------------------------------------------------------------
"""

from flask import Blueprint, render_template, request, jsonify
from datetime import datetime, timedelta

from app.services.schedule_intelligence_service import (
    DAYS,
    SHIFTS,
    ROLES,
    get_default_staffing_plan,
    parse_staffing_plan_from_form,
    staffing_field_name,
    analyze_staffing_plan,
    save_staffing_plan,
    load_staffing_plan,
    list_staffing_plans,
    delete_staffing_plan,
    get_staffing_plan_for_week,
    find_available_employees,
)
from app.services.employee_service import (
    get_all_employees,
    get_active_employees,
    update_employee,
)

schedule_bp = Blueprint("schedule", __name__, url_prefix="/schedule")


# ============================================================
# INTERNAL HELPER: Build full schedule with assigned names
# ============================================================
def _build_schedule(plan: dict, employees: list) -> dict:
    """
    Build the full schedule dict: schedule[day][shift][role] = list of assigned employees.
    Uses find_available_employees() with preference and time-window matching.
    Employees are assigned in order of availability — first come, first assigned.
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
                else:
                    available = find_available_employees(employees, role, day, shift)
                    assigned = available[:needed]
                    schedule[day][shift][role] = [
                        {"name": e["name"], "id": e["id"], "role": e.get("role", role)}
                        for e in assigned
                    ]
    return schedule


# ============================================================
# 1. SCHEDULE SETUP (week selector, past plans, save)
# ============================================================
@schedule_bp.route("/setup", methods=["GET", "POST"])
def schedule_setup():
    # Determine week start — always snap to Monday
    week_start_str = request.args.get("week_start", "")
    if week_start_str:
        try:
            week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
        except ValueError:
            week_start = datetime.now().date()
    else:
        week_start = datetime.now().date()

    start_of_week = week_start - timedelta(days=week_start.weekday())
    week_start_str = start_of_week.isoformat()

    # Build past weeks dropdown
    past_plans = list_staffing_plans()
    past_weeks = []
    for plan in past_plans:
        if plan.get("week_start"):
            past_weeks.append({
                "plan_id": plan["id"],
                "label": f"Week of {plan['week_start']}"
            })

    # Copy from a past plan if requested
    copy_plan_id = request.args.get("copy_plan", type=int)
    if copy_plan_id:
        copied = load_staffing_plan(copy_plan_id)
        staffing_plan = (
            copied.get("plan_data", get_default_staffing_plan())
            if copied else get_default_staffing_plan()
        )
    else:
        staffing_plan = get_staffing_plan_for_week(week_start_str) or get_default_staffing_plan()

    if request.method == "POST":
        staffing_plan = parse_staffing_plan_from_form(request.form)
        plan_id = save_staffing_plan(
            staffing_plan,
            name=f"Plan {week_start_str}",
            notes="",
            set_active=False,
            week_start=week_start_str,
        )
        analysis = analyze_staffing_plan(staffing_plan)
        # Preserve gaps/warnings from analysis (don't wipe them)
        return render_template(
            "schedule_setup.html",
            days=DAYS,
            shifts=SHIFTS,
            roles=ROLES,
            staffing_plan=staffing_plan,
            staffing_field_name=staffing_field_name,
            analysis=analysis,
            week_start=week_start_str,
            past_weeks=past_weeks,
            plan_id=plan_id,
        )
    else:
        return render_template(
            "schedule_setup.html",
            days=DAYS,
            shifts=SHIFTS,
            roles=ROLES,
            staffing_plan=staffing_plan,
            staffing_field_name=staffing_field_name,
            analysis=None,
            week_start=week_start_str,
            past_weeks=past_weeks,
        )


# ============================================================
# 2. SCHEDULE VIEW (employee assignments by name, shift, day)
# ============================================================
@schedule_bp.route("/view/<int:plan_id>")
def view_schedule(plan_id):
    plan_data = load_staffing_plan(plan_id)
    if not plan_data:
        return "Plan not found", 404

    # Use ALL employees — not just active — so preference-only
    # staff (0 hours, custom times) are included in assignment
    employees = get_all_employees()
    plan = plan_data.get("plan_data", {})

    schedule = _build_schedule(plan, employees)

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


# ============================================================
# 3. EMPLOYEE AVAILABILITY PAGE
# ============================================================
@schedule_bp.route("/employees")
def employee_availability():
    employees = get_all_employees()
    return render_template(
        "employee_availability.html",
        employees=employees,
        days=DAYS,
    )


# ============================================================
# 4. API ENDPOINTS
# ============================================================

# GET all plans
@schedule_bp.route("/api/plans", methods=["GET"])
def api_plans():
    return jsonify(list_staffing_plans()), 200


# GET single plan by ID (with analysis)
@schedule_bp.route("/api/plans/<int:plan_id>", methods=["GET"])
def api_plan(plan_id):
    data = load_staffing_plan(plan_id)
    if not data:
        return jsonify({"error": "Not found"}), 404
    analysis = analyze_staffing_plan(data.get("plan_data", {}))
    return jsonify({
        "id": plan_id,
        "name": data.get("name"),
        "plan_data": data.get("plan_data"),
        "analysis": analysis,
        "week_start": data.get("week_start"),
        "notes": data.get("notes", ""),
    }), 200


# DELETE a plan
@schedule_bp.route("/api/plans/<int:plan_id>", methods=["DELETE"])
def api_delete_plan(plan_id):
    success = delete_staffing_plan(plan_id)
    return jsonify({"success": success}), 200 if success else 500


# GET full built schedule (assigned names per shift/day/role) as JSON
@schedule_bp.route("/api/schedule/<int:plan_id>", methods=["GET"])
def api_schedule(plan_id):
    """
    Returns the fully resolved schedule as JSON.
    Each cell: { day: { shift: { role: [ {id, name, role}, ... ] } } }
    Useful for frontend dynamic rendering without a page reload.
    """
    plan_data = load_staffing_plan(plan_id)
    if not plan_data:
        return jsonify({"error": "Plan not found"}), 404
    employees = get_all_employees()
    plan = plan_data.get("plan_data", {})
    schedule = _build_schedule(plan, employees)
    return jsonify({
        "plan_id": plan_id,
        "plan_name": plan_data.get("name", f"Plan #{plan_id}"),
        "week_start": plan_data.get("week_start", ""),
        "schedule": schedule,
        "days": DAYS,
        "shifts": SHIFTS,
        "roles": ROLES,
    }), 200


# POST live analysis of a staffing plan (no save)
@schedule_bp.route("/api/analyze-live", methods=["POST"])
def api_analyze_live():
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    staffing_plan = data.get("staffing_plan", {})
    analysis = analyze_staffing_plan(staffing_plan)
    return jsonify(analysis), 200


# GET single employee by ID
@schedule_bp.route("/api/employee/<int:emp_id>", methods=["GET"])
def api_get_employee(emp_id):
    employees = get_all_employees()
    emp = next((e for e in employees if e.get("id") == emp_id), None)
    if not emp:
        return jsonify({"error": "Employee not found"}), 404
    return jsonify(emp), 200


# PUT update employee by ID
@schedule_bp.route("/api/employee/<int:emp_id>", methods=["PUT"])
def api_update_employee(emp_id):
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400
    success = update_employee(emp_id, data)
    return jsonify({"success": success}), 200 if success else 500