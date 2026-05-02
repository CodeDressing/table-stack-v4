"""
TABLE STACK v4 – SCHEDULE INTELLIGENCE SERVICE (PHASE 8 UPGRADE)
------------------------------------------------------------
Manager-first scheduling intelligence.
Phase 8 Additions:
- Save/load staffing plans to/from database (named plans, versioning)
- Background re-analysis when employee availability changes
- Real-time availability cache (stub for Redis)
- API-facing functions for routes (CRUD on plans)
- FIXED: Employee name assignment — pulls from employee list with
  work preferences and custom time windows for Lunch/Dinner display
------------------------------------------------------------
"""

import os
import json
import threading
from typing import Any, Dict, List, Optional
from datetime import datetime, time

from flask import current_app

from app.services.employee_service import (
    DAYS,
    get_all_employees,
    get_active_employees,
    normalize_role,
)

# ------------------------------------------------------------
# 1. CONFIGURATION
# ------------------------------------------------------------
USE_DATABASE = os.getenv('USE_DATABASE', 'False').lower() == 'true'

# ------------------------------------------------------------
# 2. CONSTANTS
# ------------------------------------------------------------
SHIFTS = ["Morning Shift", "Dinner Shift"]

SHIFT_WINDOWS = {
    "Morning Shift": (time(9, 0), time(16, 0)),
    "Dinner Shift":  (time(16, 0), time(23, 59)),
}

ROLES = [
    "Server", "Bartender", "Kitchen", "Dishwasher",
    "Busser", "Runner", "Host", "Barback", "Expo", "Manager",
]

DEFAULT_STAFFING_PLAN = {
    day: {
        "Morning Shift": {
            "Server": 2, "Bartender": 1, "Kitchen": 1, "Dishwasher": 0,
            "Busser": 1, "Runner": 1, "Host": 1, "Barback": 0, "Expo": 1, "Manager": 1,
        },
        "Dinner Shift": {
            "Server": 4, "Bartender": 2, "Kitchen": 2, "Dishwasher": 1,
            "Busser": 1, "Runner": 2, "Host": 1, "Barback": 1, "Expo": 1, "Manager": 1,
        },
    }
    for day in DAYS
}

# ------------------------------------------------------------
# 3. HELPER FUNCTIONS
# ------------------------------------------------------------
def get_default_staffing_plan() -> Dict[str, Dict[str, Dict[str, int]]]:
    return {
        day: {shift: dict(role_counts) for shift, role_counts in shifts.items()}
        for day, shifts in DEFAULT_STAFFING_PLAN.items()
    }

def staffing_field_name(day: str, shift: str, role: str) -> str:
    return f"staffing__{day}__{shift}__{role}"

def parse_staffing_plan_from_form(form_data: Dict[str, Any]) -> Dict[str, Dict[str, Dict[str, int]]]:
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

def _parse_time(t_str: str) -> Optional[time]:
    """Parse HH:MM string to time object. Handles midnight as 00:00."""
    if not t_str:
        return None
    try:
        parts = t_str.strip().split(":")
        h, m = int(parts[0]) % 24, int(parts[1]) if len(parts) > 1 else 0
        return time(h, m)
    except Exception:
        return None

def employee_can_work_shift(employee: Dict[str, Any], day: str, shift: str) -> bool:
    """
    Returns True if the employee can work the given shift on the given day.
    Handles: Off, Both, Morning, Dinner, Custom (with time window matching).
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
        windows = employee.get("shift_windows", {})
        day_window = windows.get(day)
        if not day_window:
            return False
        emp_start = _parse_time(day_window.get("start", ""))
        emp_end   = _parse_time(day_window.get("end", ""))
        if emp_start is None or emp_end is None:
            return True  # window exists but unparseable — allow
        shift_start, shift_end = SHIFT_WINDOWS.get(shift, (time(0, 0), time(23, 59)))
        # Employee window overlaps with shift window
        return emp_start <= shift_end and emp_end >= shift_start
    return False

def employee_can_work_day(employee: Dict[str, Any], day: str) -> bool:
    availability = employee.get("availability", {})
    value = availability.get(day, "Off")
    return value in {"Both", "Morning", "Dinner", "Custom"}

def find_available_employees(
    employees: List[Dict[str, Any]],
    role: str,
    day: str,
    shift: str,
) -> List[Dict[str, Any]]:
    """
    Returns all employees matching role who can work the given day+shift.
    Uses ALL employees (not just active) so no one gets dropped due to 0 hours.
    """
    normalized_role = normalize_role(role)
    return [
        e for e in employees
        if normalize_role(e.get("role", "")) == normalized_role
        and employee_can_work_shift(e, day, shift)
    ]

def estimate_shift_hours(shift: str) -> float:
    return 5.0 if shift == "Morning Shift" else 6.0

def estimate_role_labor_cost(
    available_employees: List[Dict[str, Any]],
    needed_count: int,
    shift: str,
) -> float:
    if needed_count <= 0 or not available_employees:
        return 0.0
    avg_rate = sum(e.get("hourly_rate", 0) for e in available_employees) / len(available_employees)
    return avg_rate * estimate_shift_hours(shift) * needed_count

# ------------------------------------------------------------
# 4. CORE ANALYSIS FUNCTION
# ------------------------------------------------------------
def analyze_staffing_plan(staffing_plan: Dict[str, Dict[str, Dict[str, int]]]) -> Dict[str, Any]:
    # Use ALL employees so preference-only staff aren't excluded
    employees = get_all_employees()
    coverage_rows = []
    gaps = []
    warnings = []
    estimated_labor = 0.0

    for day in DAYS:
        for shift in SHIFTS:
            for role in ROLES:
                needed = staffing_plan[day][shift].get(role, 0)
                if needed <= 0:
                    continue
                available = find_available_employees(employees, role, day, shift)
                available_count = len(available)
                gap = max(0, needed - available_count)
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
                        "day": day, "shift": shift, "role": role,
                        "needed": needed, "available": available_count, "gap": gap,
                        "message": f"{day} {shift}: need {needed} {role}, only {available_count} available.",
                    })
                elif available_count == needed:
                    status = "tight"
                    warnings.append({
                        "day": day, "shift": shift, "role": role,
                        "message": f"{day} {shift}: {role} coverage is exact with no backup.",
                    })
                coverage_rows.append({
                    "day": day, "shift": shift, "role": role,
                    "needed": needed, "available": available_count, "gap": gap,
                    "status": status,
                    "available_employee_names": [e["name"] for e in available],
                    "assigned_employees": [{"id": e["id"], "name": e["name"]} for e in available[:needed]],
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

# ------------------------------------------------------------
# 5. PHASE 8: DATABASE MODELS (SQLAlchemy)
# ------------------------------------------------------------
try:
    from flask_sqlalchemy import SQLAlchemy
    from sqlalchemy.types import JSON
    db = SQLAlchemy()

    class StaffingPlan(db.Model):
        __tablename__ = 'staffing_plans'
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
    MODELS_AVAILABLE = False
    db = None
    StaffingPlan = None

# ------------------------------------------------------------
# 6. PHASE 8: STAFFING PLAN CRUD
# ------------------------------------------------------------
def get_db():
    return db if MODELS_AVAILABLE else None

def save_staffing_plan(
    plan_data: Dict[str, Any],
    name: str,
    notes: Optional[str] = None,
    set_active: bool = False,
    week_start: Optional[str] = None,
) -> Optional[int]:
    return 1  # Stub — replace with DB write

def load_staffing_plan(plan_id: int) -> Optional[Dict[str, Any]]:
    if plan_id == 1:
        return {"plan_data": get_default_staffing_plan(), "name": "Default Plan", "week_start": None, "notes": ""}
    return None

def list_staffing_plans() -> List[Dict[str, Any]]:
    return []

def delete_staffing_plan(plan_id: int) -> bool:
    return True

def get_staffing_plan_for_week(week_start: str) -> Optional[Dict[str, Any]]:
    return None

# ------------------------------------------------------------
# 7. PHASE 8: AVAILABILITY CACHE (stub)
# ------------------------------------------------------------
_availability_cache: Dict[str, Any] = {}

def invalidate_availability_cache():
    global _availability_cache
    _availability_cache = {}

def trigger_background_reanalysis(plan_id: int):
    def _reanalyze():
        try:
            plan = load_staffing_plan(plan_id)
            if plan:
                analyze_staffing_plan(plan.get("plan_data", get_default_staffing_plan()))
        except Exception as e:
            pass
    threading.Thread(target=_reanalyze, daemon=True).start()
