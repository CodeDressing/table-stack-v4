"""
TABLE STACK v4 – SCHEDULE INTELLIGENCE SERVICE
================================================================================
Purpose:
- Manager-first schedule intelligence
- Staffing plan defaults
- Staffing form parsing
- Employee availability matching
- Custom shift-window matching
- Labor cost estimation
- Coverage analysis
- Assigned employee previews
- Staffing plan save/load/list/delete stubs
- Future-ready structure for database persistence, shift swaps, drops, approvals

Architecture Rule:
- Keep route files thin.
- Keep employee loading in employee_service.
- Keep schedule logic here.
- Each numbered section is designed to be replaced independently later.

Future Upgrade Pattern:
- Replace SECTION 04 to change shift windows
- Replace SECTION 06 to upgrade employee matching
- Replace SECTION 08 to upgrade staffing analysis
- Replace SECTION 09 to move plan storage into the database
- Replace SECTION 11 to add manager approval workflows
================================================================================
"""

# ==============================================================================
# SECTION 01 — IMPORTS
# ==============================================================================

import os
import copy
import threading
from datetime import datetime, time
from typing import Any, Dict, List, Optional

from app.services.employee_service import (
    DAYS,
    get_all_employees,
    normalize_role,
)


# ==============================================================================
# SECTION 02 — CONFIGURATION
# ==============================================================================

USE_DATABASE = os.getenv("USE_DATABASE", "False").lower() == "true"


# ==============================================================================
# SECTION 03 — CORE CONSTANTS
# ==============================================================================

SHIFTS = [
    "Morning Shift",
    "Dinner Shift",
]

ROLES = [
    "Server",
    "Bartender",
    "Kitchen",
    "Dishwasher",
    "Busser",
    "Runner",
    "Host",
    "Barback",
    "Expo",
    "Manager",
]


# ==============================================================================
# SECTION 04 — SHIFT WINDOWS / TIME LOGIC
# ==============================================================================

SHIFT_WINDOWS = {
    "Morning Shift": (time(9, 0), time(16, 0)),
    "Dinner Shift": (time(16, 0), time(23, 59)),
}


def parse_time_string(value: str) -> Optional[time]:
    """
    Parse HH:MM into a time object.

    Supports:
    - "11:00"
    - "16:30"
    - "00:00"

    Returns None if invalid.
    """
    if not value:
        return None

    try:
        parts = value.strip().split(":")
        hour = int(parts[0]) % 24
        minute = int(parts[1]) if len(parts) > 1 else 0
        return time(hour, minute)
    except (TypeError, ValueError, IndexError):
        return None


def time_windows_overlap(
    employee_start: time,
    employee_end: time,
    shift_start: time,
    shift_end: time,
) -> bool:
    """
    Determine whether employee window overlaps shift window.

    Note:
    Midnight-crossing shifts can be improved later in this section.
    Current logic handles your existing 00:00 values safely enough for v4.
    """
    return employee_start <= shift_end and employee_end >= shift_start


def custom_window_matches_shift(
    employee: Dict[str, Any],
    day: str,
    shift: str,
) -> bool:
    """
    Check whether employee custom shift window overlaps the requested shift.
    """
    shift_windows = employee.get("shift_windows", {})
    day_window = shift_windows.get(day)

    if not day_window:
        return False

    employee_start = parse_time_string(day_window.get("start", ""))
    employee_end = parse_time_string(day_window.get("end", ""))

    if employee_start is None or employee_end is None:
        return True

    shift_start, shift_end = SHIFT_WINDOWS.get(
        shift,
        (time(0, 0), time(23, 59)),
    )

    return time_windows_overlap(
        employee_start=employee_start,
        employee_end=employee_end,
        shift_start=shift_start,
        shift_end=shift_end,
    )


# ==============================================================================
# SECTION 05 — DEFAULT STAFFING PLAN
# ==============================================================================

DEFAULT_STAFFING_PLAN = {
    day: {
        "Morning Shift": {
            "Server": 2,
            "Bartender": 1,
            "Kitchen": 1,
            "Dishwasher": 0,
            "Busser": 1,
            "Runner": 1,
            "Host": 1,
            "Barback": 0,
            "Expo": 1,
            "Manager": 1,
        },
        "Dinner Shift": {
            "Server": 4,
            "Bartender": 2,
            "Kitchen": 2,
            "Dishwasher": 1,
            "Busser": 1,
            "Runner": 2,
            "Host": 1,
            "Barback": 1,
            "Expo": 1,
            "Manager": 1,
        },
    }
    for day in DAYS
}


def get_default_staffing_plan() -> Dict[str, Dict[str, Dict[str, int]]]:
    """
    Return a safe deep copy of the default staffing plan.
    """
    return copy.deepcopy(DEFAULT_STAFFING_PLAN)


# ==============================================================================
# SECTION 06 — FORM PARSING
# ==============================================================================

def staffing_field_name(day: str, shift: str, role: str) -> str:
    """
    Predictable form field name.

    Example:
        staffing__Monday__Dinner Shift__Server
    """
    return f"staffing__{day}__{shift}__{role}"


def parse_staffing_plan_from_form(
    form_data: Dict[str, Any],
) -> Dict[str, Dict[str, Dict[str, int]]]:
    """
    Parse submitted staffing numbers from schedule_setup.html.
    """
    plan = get_default_staffing_plan()

    for day in DAYS:
        for shift in SHIFTS:
            for role in ROLES:
                field = staffing_field_name(day, shift, role)

                try:
                    value = int(form_data.get(field, 0))
                except (TypeError, ValueError):
                    value = 0

                plan[day][shift][role] = max(0, value)

    return plan


# ==============================================================================
# SECTION 07 — EMPLOYEE AVAILABILITY / MATCHING
# ==============================================================================

def employee_can_work_day(
    employee: Dict[str, Any],
    day: str,
) -> bool:
    """
    Check if employee is available at all on a day.
    """
    availability = employee.get("availability", {})
    value = availability.get(day, "Off")

    return value in {
        "Both",
        "Morning",
        "Dinner",
        "Custom",
    }


def employee_can_work_shift(
    employee: Dict[str, Any],
    day: str,
    shift: str,
) -> bool:
    """
    Check if employee can work a specific day and shift.

    Supports:
    - Off
    - Both
    - Morning
    - Dinner
    - Custom shift windows
    """
    availability = employee.get("availability", {})
    value = availability.get(day, "Off")

    if value == "Off":
        return False

    if value == "Both":
        return True

    if value == "Morning" and shift == "Morning Shift":
        return True

    if value == "Dinner" and shift == "Dinner Shift":
        return True

    if value == "Custom":
        return custom_window_matches_shift(
            employee=employee,
            day=day,
            shift=shift,
        )

    return False


def find_available_employees(
    employees: List[Dict[str, Any]],
    role: str,
    day: str,
    shift: str,
) -> List[Dict[str, Any]]:
    """
    Return employees matching:
    - normalized role
    - day availability
    - shift availability/custom window

    Uses all provided employees. The caller decides whether that is all employees
    or only active employees.
    """
    normalized_role = normalize_role(role)

    return [
        employee for employee in employees
        if normalize_role(employee.get("role", "")) == normalized_role
        and employee_can_work_shift(
            employee=employee,
            day=day,
            shift=shift,
        )
    ]


def assign_employees_for_role(
    employees: List[Dict[str, Any]],
    role: str,
    day: str,
    shift: str,
    needed_count: int,
) -> List[Dict[str, Any]]:
    """
    Assign employees for one day/shift/role.

    Current assignment logic:
    - first available employees up to needed count

    Future replacement:
    - balance target hours
    - avoid doubles
    - rotate fairly
    - respect approved swaps/drops
    """
    if needed_count <= 0:
        return []

    available = find_available_employees(
        employees=employees,
        role=role,
        day=day,
        shift=shift,
    )

    return [
        {
            "id": employee.get("id"),
            "name": employee.get("name", "Unnamed Employee"),
            "role": employee.get("role", role),
            "hourly_rate": employee.get("hourly_rate", 0),
            "preference": employee.get("preference", "Any"),
        }
        for employee in available[:needed_count]
    ]


# ==============================================================================
# SECTION 08 — LABOR COST ESTIMATION
# ==============================================================================

def estimate_shift_hours(shift: str) -> float:
    """
    Basic hours by shift.

    Future:
    Replace with shift templates from DB.
    """
    if shift == "Morning Shift":
        return 5.0

    if shift == "Dinner Shift":
        return 6.0

    return 5.0


def estimate_role_labor_cost(
    available_employees: List[Dict[str, Any]],
    needed_count: int,
    shift: str,
) -> float:
    """
    Estimate role labor cost using average rate of available employees.
    """
    if needed_count <= 0 or not available_employees:
        return 0.0

    average_rate = sum(
        employee.get("hourly_rate", 0)
        for employee in available_employees
    ) / len(available_employees)

    return average_rate * estimate_shift_hours(shift) * needed_count


# ==============================================================================
# SECTION 09 — STAFFING ANALYSIS ENGINE
# ==============================================================================

def analyze_staffing_plan(
    staffing_plan: Dict[str, Dict[str, Dict[str, int]]],
) -> Dict[str, Any]:
    """
    Analyze staffing plan against employee availability.

    Returns:
    - coverage rows
    - gaps
    - warnings
    - estimated labor
    - assigned employee preview
    """
    employees = get_all_employees()

    coverage_rows = []
    gaps = []
    warnings = []
    estimated_labor = 0.0

    for day in DAYS:
        for shift in SHIFTS:
            for role in ROLES:
                needed = staffing_plan.get(day, {}).get(shift, {}).get(role, 0)

                if needed <= 0:
                    continue

                available = find_available_employees(
                    employees=employees,
                    role=role,
                    day=day,
                    shift=shift,
                )

                available_count = len(available)
                gap = max(0, needed - available_count)

                assigned = [
                    {
                        "id": employee.get("id"),
                        "name": employee.get("name", "Unnamed Employee"),
                        "role": employee.get("role", role),
                    }
                    for employee in available[:needed]
                ]

                role_labor_cost = estimate_role_labor_cost(
                    available_employees=available,
                    needed_count=min(needed, available_count),
                    shift=shift,
                )

                estimated_labor += role_labor_cost

                status = "covered"

                if gap > 0:
                    status = "gap"
                    gaps.append({
                        "day": day,
                        "shift": shift,
                        "role": role,
                        "needed": needed,
                        "available": available_count,
                        "gap": gap,
                        "message": (
                            f"{day} {shift}: need {needed} {role}, "
                            f"only {available_count} available."
                        ),
                    })

                elif available_count == needed:
                    status = "tight"
                    warnings.append({
                        "day": day,
                        "shift": shift,
                        "role": role,
                        "message": (
                            f"{day} {shift}: {role} coverage is exact "
                            f"with no backup."
                        ),
                    })

                coverage_rows.append({
                    "day": day,
                    "shift": shift,
                    "role": role,
                    "needed": needed,
                    "available": available_count,
                    "gap": gap,
                    "status": status,
                    "available_employee_names": [
                        employee.get("name", "Unnamed Employee")
                        for employee in available
                    ],
                    "assigned_employees": assigned,
                    "estimated_labor_cost": round(role_labor_cost, 2),
                })

    return {
        "coverage_rows": coverage_rows,
        "gaps": gaps,
        "warnings": warnings,
        "estimated_labor": round(estimated_labor, 2),
        "summary": {
            "total_gaps": len(gaps),
            "total_warnings": len(warnings),
            "coverage_status": "Needs Attention" if gaps else "Covered",
        },
    }


# ==============================================================================
# SECTION 10 — SCHEDULE GENERATION ENGINE
# ==============================================================================

def generate_schedule_from_plan(
    staffing_plan: Dict[str, Dict[str, Dict[str, int]]],
    employees: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """
    Generate final schedule using employee names.

    Output:
        schedule[day][shift][role] = [employee, employee, ...]

    Current logic:
    - role match
    - availability match
    - first available employees

    Future:
    - fair balancing
    - manager approval states
    - shift accept/drop/swap logic
    """
    if employees is None:
        employees = get_all_employees()

    schedule = {}

    for day in DAYS:
        schedule[day] = {}

        for shift in SHIFTS:
            schedule[day][shift] = {}

            for role in ROLES:
                needed = staffing_plan.get(day, {}).get(shift, {}).get(role, 0)

                schedule[day][shift][role] = assign_employees_for_role(
                    employees=employees,
                    role=role,
                    day=day,
                    shift=shift,
                    needed_count=needed,
                )

    return schedule


# ==============================================================================
# SECTION 11 — OPTIONAL DATABASE MODEL STUB
# ==============================================================================

try:
    from flask_sqlalchemy import SQLAlchemy
    from sqlalchemy.types import JSON

    db = SQLAlchemy()

    class StaffingPlan(db.Model):
        __tablename__ = "staffing_plans"

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(100), nullable=False)
        plan_data = db.Column(JSON, nullable=False)
        week_start = db.Column(db.String(20), nullable=True)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
        is_active = db.Column(db.Boolean, default=False)
        version = db.Column(db.Integer, default=1)
        notes = db.Column(db.Text)

    MODELS_AVAILABLE = True

except ImportError:
    db = None
    StaffingPlan = None
    MODELS_AVAILABLE = False


def get_db():
    return db if MODELS_AVAILABLE else None


# ==============================================================================
# SECTION 12 — TEMPORARY PLAN STORAGE / CRUD
# ==============================================================================

_STAFFING_PLANS: Dict[int, Dict[str, Any]] = {}
_PLAN_COUNTER = 1


def save_staffing_plan(
    plan_data: Dict[str, Any],
    name: str,
    notes: Optional[str] = None,
    set_active: bool = False,
    week_start: Optional[str] = None,
) -> Optional[int]:
    """
    Save staffing plan.

    Current:
    - in-memory plan storage

    Future:
    - database persistence
    """
    global _PLAN_COUNTER

    plan_id = _PLAN_COUNTER
    _PLAN_COUNTER += 1

    now = datetime.utcnow().isoformat()

    if set_active:
        for existing_plan in _STAFFING_PLANS.values():
            existing_plan["is_active"] = False

    _STAFFING_PLANS[plan_id] = {
        "id": plan_id,
        "name": name or f"Plan {plan_id}",
        "plan_data": plan_data,
        "week_start": week_start,
        "created_at": now,
        "updated_at": now,
        "is_active": set_active,
        "version": 1,
        "notes": notes or "",
    }

    return plan_id


def load_staffing_plan(plan_id: int) -> Optional[Dict[str, Any]]:
    """
    Load staffing plan by ID.

    plan_id=1 fallback returns the default plan if no in-memory plan exists.
    """
    if plan_id in _STAFFING_PLANS:
        return _STAFFING_PLANS[plan_id]

    if plan_id == 1:
        return {
            "id": 1,
            "name": "Default Staffing Plan",
            "plan_data": get_default_staffing_plan(),
            "week_start": None,
            "created_at": None,
            "updated_at": None,
            "is_active": False,
            "version": 1,
            "notes": "",
        }

    return None


def list_staffing_plans() -> List[Dict[str, Any]]:
    """
    List saved plans.
    """
    return list(_STAFFING_PLANS.values())


def delete_staffing_plan(plan_id: int) -> bool:
    """
    Delete saved plan.
    """
    if plan_id in _STAFFING_PLANS:
        del _STAFFING_PLANS[plan_id]
        return True

    return False


def get_staffing_plan_for_week(
    week_start: str,
) -> Optional[Dict[str, Any]]:
    """
    Get plan data for a specific week.
    """
    for plan in _STAFFING_PLANS.values():
        if plan.get("week_start") == week_start:
            return plan.get("plan_data")

    return None


# ==============================================================================
# SECTION 13 — AVAILABILITY CACHE / BACKGROUND REANALYSIS
# ==============================================================================

_AVAILABILITY_CACHE: Dict[str, Any] = {}
_CACHE_LOCK = threading.Lock()


def make_availability_cache_key(
    role: str,
    day: str,
    shift: str,
) -> str:
    return f"{normalize_role(role)}|{day}|{shift}"


def invalidate_availability_cache() -> None:
    with _CACHE_LOCK:
        _AVAILABILITY_CACHE.clear()


def get_cached_available_employees(
    role: str,
    day: str,
    shift: str,
) -> Optional[List[Dict[str, Any]]]:
    key = make_availability_cache_key(role, day, shift)

    with _CACHE_LOCK:
        return _AVAILABILITY_CACHE.get(key)


def set_cached_available_employees(
    role: str,
    day: str,
    shift: str,
    employees: List[Dict[str, Any]],
) -> None:
    key = make_availability_cache_key(role, day, shift)

    with _CACHE_LOCK:
        _AVAILABILITY_CACHE[key] = employees


def find_available_employees_cached(
    employees: List[Dict[str, Any]],
    role: str,
    day: str,
    shift: str,
) -> List[Dict[str, Any]]:
    cached = get_cached_available_employees(
        role=role,
        day=day,
        shift=shift,
    )

    if cached is not None:
        return cached

    result = find_available_employees(
        employees=employees,
        role=role,
        day=day,
        shift=shift,
    )

    set_cached_available_employees(
        role=role,
        day=day,
        shift=shift,
        employees=result,
    )

    return result


def trigger_background_reanalysis(plan_id: int) -> None:
    """
    Future hook for reanalysis when employee availability changes.
    """
    def reanalyze() -> None:
        plan = load_staffing_plan(plan_id)

        if plan:
            analyze_staffing_plan(
                plan.get("plan_data", get_default_staffing_plan())
            )

    threading.Thread(
        target=reanalyze,
        daemon=True,
    ).start()


# ==============================================================================
# SECTION 14 — FUTURE SHIFT SWAP / DROP / APPROVAL STRUCTURES
# ==============================================================================

def build_shift_change_request_stub(
    request_type: str,
    employee_id: int,
    day: str,
    shift: str,
    role: str,
    target_employee_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Future structure for:
    - shift drops
    - shift swaps
    - manager approvals
    """
    return {
        "request_type": request_type,
        "status": "pending_manager_approval",
        "employee_id": employee_id,
        "target_employee_id": target_employee_id,
        "day": day,
        "shift": shift,
        "role": role,
        "created_at": datetime.utcnow().isoformat(),
    }


# ==============================================================================
# SECTION 15 — FUTURE EXPANSION BLOCKS
# ==============================================================================
# Future Section Ideas:
#
# SECTION 15A — Real database-backed StaffingPlan CRUD
# SECTION 15B — Fair schedule rotation / hour balancing
# SECTION 15C — Manager approval queue logic
# SECTION 15D — Employee shift acceptance workflow
# SECTION 15E — Schedule publishing history
# SECTION 15F — Auto-save persisted schedules
#
# Add new blocks below this line without modifying previous sections.
# ==============================================================================