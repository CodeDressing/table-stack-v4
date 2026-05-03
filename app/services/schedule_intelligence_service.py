"""
TABLE STACK v4 – SCHEDULE INTELLIGENCE SERVICE
================================================================================
PHASE 11 PART 2 OF 8
Master schedule persistence + editable schedule foundation.

Purpose:
- Manager-first schedule intelligence
- Remove non-Mike staffing positions from active planner
- Persist staffing plans to disk
- Persist current master schedules to disk
- Support save-by-week, save-by-day, save-by-shift, save-by-role
- Keep one current master schedule per week
- Keep routes thin and reusable

SECTION MAP
01. Imports
02. Configuration / storage paths
03. Core constants
04. Shift windows / time logic
05. Default staffing plan
06. Staffing form parsing
07. Employee availability / matching
08. Labor cost estimation
09. Staffing analysis engine
10. Schedule generation engine
11. Persistent staffing plan storage
12. Persistent master schedule storage
13. Master schedule edit helpers
14. Availability cache / background reanalysis
15. Future expansion blocks
================================================================================
"""

# ==============================================================================
# SECTION 01 — IMPORTS
# ==============================================================================

import copy
import json
import os
import threading
from datetime import datetime, time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.services.employee_service import (
    DAYS,
    get_all_employees,
    normalize_role,
)


# ==============================================================================
# SECTION 02 — CONFIGURATION / STORAGE PATHS
# ==============================================================================

USE_DATABASE = os.getenv("USE_DATABASE", "False").lower() == "true"

INSTANCE_DIR = Path.cwd() / "instance"
STAFFING_PLAN_FILE = INSTANCE_DIR / "staffing_plans.json"
MASTER_SCHEDULE_FILE = INSTANCE_DIR / "master_schedules.json"


def ensure_storage_files() -> None:
    """
    Ensure local JSON persistence files exist.

    This keeps TableStack usable without a database while still allowing
    schedules/plans to survive app restarts.
    """
    INSTANCE_DIR.mkdir(parents=True, exist_ok=True)

    if not STAFFING_PLAN_FILE.exists():
        STAFFING_PLAN_FILE.write_text(
            json.dumps(
                {
                    "plans": [],
                    "next_id": 1,
                    "last_updated": None,
                },
                indent=2,
            ),
            encoding="utf-8",
        )

    if not MASTER_SCHEDULE_FILE.exists():
        MASTER_SCHEDULE_FILE.write_text(
            json.dumps(
                {
                    "master_schedules": [],
                    "next_id": 1,
                    "last_updated": None,
                },
                indent=2,
            ),
            encoding="utf-8",
        )


def load_json_file(path: Path, default_data: Dict[str, Any]) -> Dict[str, Any]:
    ensure_storage_files()

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            return copy.deepcopy(default_data)

        return data

    except (json.JSONDecodeError, OSError):
        return copy.deepcopy(default_data)


def save_json_file(path: Path, data: Dict[str, Any]) -> bool:
    ensure_storage_files()

    data["last_updated"] = datetime.utcnow().isoformat()

    try:
        with path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)

        return True

    except OSError:
        return False


# ==============================================================================
# SECTION 03 — CORE CONSTANTS
# ==============================================================================

SHIFTS = [
    "Morning Shift",
    "Dinner Shift",
]

# Mike-facing staffing positions only.
# Kitchen and Dishwasher are intentionally removed from active scheduling.
ROLES = [
    "Server",
    "Bartender",
    "Busser",
    "Runner",
    "Host",
    "Barback",
    "Expo",
    "Manager",
]

REMOVED_POSITIONS = [
    "Kitchen",
    "Dishwasher",
]

MASTER_STATUS_DRAFT = "draft"
MASTER_STATUS_POSTED = "posted"
MASTER_STATUS_ARCHIVED = "archived"


# ==============================================================================
# SECTION 04 — SHIFT WINDOWS / TIME LOGIC
# ==============================================================================

SHIFT_WINDOWS = {
    "Morning Shift": (time(9, 0), time(16, 0)),
    "Dinner Shift": (time(16, 0), time(23, 59)),
}


def parse_time_string(value: str) -> Optional[time]:
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
    return employee_start <= shift_end and employee_end >= shift_start


def custom_window_matches_shift(
    employee: Dict[str, Any],
    day: str,
    shift: str,
) -> bool:
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


def clean_staffing_plan_roles(
    staffing_plan: Dict[str, Dict[str, Dict[str, int]]],
) -> Dict[str, Dict[str, Dict[str, int]]]:
    """
    Remove positions that should not be in Mike's staffing planner.
    Also ensures every active role exists in every day/shift.
    """
    cleaned = {}

    for day in DAYS:
        cleaned[day] = {}

        for shift in SHIFTS:
            source_shift = staffing_plan.get(day, {}).get(shift, {})
            cleaned[day][shift] = {}

            for role in ROLES:
                try:
                    value = int(source_shift.get(role, 0))
                except (TypeError, ValueError):
                    value = 0

                cleaned[day][shift][role] = max(0, value)

    return cleaned


def get_default_staffing_plan() -> Dict[str, Dict[str, Dict[str, int]]]:
    return copy.deepcopy(DEFAULT_STAFFING_PLAN)


# ==============================================================================
# SECTION 06 — STAFFING FORM PARSING
# ==============================================================================

def staffing_field_name(day: str, shift: str, role: str) -> str:
    return f"staffing__{day}__{shift}__{role}"


def parse_staffing_plan_from_form(
    form_data: Dict[str, Any],
) -> Dict[str, Dict[str, Dict[str, int]]]:
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

    return clean_staffing_plan_roles(plan)


# ==============================================================================
# SECTION 07 — EMPLOYEE AVAILABILITY / MATCHING
# ==============================================================================

def employee_can_work_day(
    employee: Dict[str, Any],
    day: str,
) -> bool:
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


def employee_public_schedule_shape(
    employee: Dict[str, Any],
    role: str,
) -> Dict[str, Any]:
    return {
        "id": employee.get("id"),
        "name": employee.get("name", "Unnamed Employee"),
        "role": employee.get("role", role),
        "hourly_rate": employee.get("hourly_rate", 0),
        "preference": employee.get("preference", "Any"),
    }


def assign_employees_for_role(
    employees: List[Dict[str, Any]],
    role: str,
    day: str,
    shift: str,
    needed_count: int,
) -> List[Dict[str, Any]]:
    if needed_count <= 0:
        return []

    available = find_available_employees(
        employees=employees,
        role=role,
        day=day,
        shift=shift,
    )

    return [
        employee_public_schedule_shape(employee, role)
        for employee in available[:needed_count]
    ]


# ==============================================================================
# SECTION 08 — LABOR COST ESTIMATION
# ==============================================================================

def estimate_shift_hours(shift: str) -> float:
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
    employees = get_all_employees()
    staffing_plan = clean_staffing_plan_roles(staffing_plan)

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
            "active_roles": ROLES,
            "removed_positions": REMOVED_POSITIONS,
        },
    }


# ==============================================================================
# SECTION 10 — SCHEDULE GENERATION ENGINE
# ==============================================================================

def empty_schedule() -> Dict[str, Dict[str, Dict[str, List[Dict[str, Any]]]]]:
    return {
        day: {
            shift: {
                role: []
                for role in ROLES
            }
            for shift in SHIFTS
        }
        for day in DAYS
    }


def clean_schedule_roles(
    schedule: Dict[str, Any],
) -> Dict[str, Dict[str, Dict[str, List[Dict[str, Any]]]]]:
    cleaned = empty_schedule()

    for day in DAYS:
        for shift in SHIFTS:
            for role in ROLES:
                employees = schedule.get(day, {}).get(shift, {}).get(role, [])

                if isinstance(employees, list):
                    cleaned[day][shift][role] = employees

    return cleaned


def generate_schedule_from_plan(
    staffing_plan: Dict[str, Dict[str, Dict[str, int]]],
    employees: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    if employees is None:
        employees = get_all_employees()

    staffing_plan = clean_staffing_plan_roles(staffing_plan)

    schedule = empty_schedule()

    for day in DAYS:
        for shift in SHIFTS:
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
# ==============================================================================
# SECTION 11 — PERSISTENT STAFFING PLAN STORAGE (complete)
# ==============================================================================

def load_staffing_plan_store() -> Dict[str, Any]:
    return load_json_file(
        STAFFING_PLAN_FILE,
        {
            "plans": [],
            "next_id": 1,
            "last_updated": None,
        },
    )


def save_staffing_plan_store(data: Dict[str, Any]) -> bool:
    return save_json_file(STAFFING_PLAN_FILE, data)


def save_staffing_plan(
    plan_data: Dict[str, Any],
    name: str,
    notes: str = "",
    set_active: bool = False,
    week_start: Optional[str] = None,
    is_master: bool = False,
) -> Optional[int]:
    """
    Save a staffing plan. Returns plan_id.
    If is_master=True, the plan will be marked as a master schedule.
    """
    store = load_staffing_plan_store()
    plans = store.get("plans", [])
    next_id = store.get("next_id", 1)

    # Check if we are updating an existing plan with the same week_start and is_master? Not needed.
    # Simple: always create new plan (append). Allow duplicates for different versions.
    new_plan = {
        "id": next_id,
        "name": name,
        "plan_data": clean_staffing_plan_roles(plan_data),
        "notes": notes,
        "is_active": set_active,
        "week_start": week_start,
        "is_master": is_master,
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
    }
    plans.append(new_plan)
    store["plans"] = plans
    store["next_id"] = next_id + 1

    if save_staffing_plan_store(store):
        return next_id
    return None


def load_staffing_plan(plan_id: int) -> Optional[Dict[str, Any]]:
    store = load_staffing_plan_store()
    for plan in store.get("plans", []):
        if int(plan.get("id", -1)) == int(plan_id):
            # Ensure plan_data has correct roles
            plan["plan_data"] = clean_staffing_plan_roles(
                plan.get("plan_data", get_default_staffing_plan())
            )
            return plan
    # Fallback for default plan (id=1) if not found in store
    if int(plan_id) == 1:
        return {
            "id": 1,
            "name": "Default Staffing Plan",
            "plan_data": get_default_staffing_plan(),
            "week_start": None,
            "is_master": False,
            "created_at": None,
            "updated_at": None,
            "is_active": False,
            "notes": "",
        }
    return None


def list_staffing_plans() -> List[Dict[str, Any]]:
    store = load_staffing_plan_store()
    plans = store.get("plans", [])
    # Return sorted by updated_at descending
    return sorted(
        plans,
        key=lambda p: p.get("updated_at") or "",
        reverse=True,
    )


def delete_staffing_plan(plan_id: int) -> bool:
    store = load_staffing_plan_store()
    plans = store.get("plans", [])
    new_plans = [p for p in plans if int(p.get("id", -1)) != int(plan_id)]
    if len(new_plans) == len(plans):
        return False
    store["plans"] = new_plans
    return save_staffing_plan_store(store)


def get_staffing_plan_for_week(week_start: str) -> Optional[Dict[str, Any]]:
    """Return the most recent non‑master plan for the given week."""
    store = load_staffing_plan_store()
    matching = [
        p for p in store.get("plans", [])
        if p.get("week_start") == week_start and not p.get("is_master", False)
    ]
    if not matching:
        return None
    # Return the latest (by updated_at)
    latest = sorted(matching, key=lambda p: p.get("updated_at") or "", reverse=True)[0]
    return clean_staffing_plan_roles(latest.get("plan_data", get_default_staffing_plan()))
# ==============================================================================
# SECTION 12 — PERSISTENT MASTER SCHEDULE STORAGE
# ==============================================================================

def load_master_schedule_store() -> Dict[str, Any]:
    return load_json_file(
        MASTER_SCHEDULE_FILE,
        {
            "master_schedules": [],
            "next_id": 1,
            "last_updated": None,
        },
    )


def save_master_schedule_store(data: Dict[str, Any]) -> bool:
    return save_json_file(MASTER_SCHEDULE_FILE, data)


def build_master_schedule_record(
    week_start: str,
    staffing_plan: Dict[str, Any],
    schedule: Dict[str, Any],
    source_plan_id: Optional[int] = None,
    status: str = MASTER_STATUS_DRAFT,
) -> Dict[str, Any]:
    now = datetime.utcnow().isoformat()

    return {
        "id": None,
        "week_start": week_start,
        "status": status,
        "source_plan_id": source_plan_id,
        "staffing_plan": clean_staffing_plan_roles(staffing_plan),
        "schedule": clean_schedule_roles(schedule),
        "created_at": now,
        "updated_at": now,
        "published_at": None,
        "edit_history": [],
    }


def get_master_schedule_for_week(
    week_start: str,
) -> Optional[Dict[str, Any]]:
    store = load_master_schedule_store()

    matching = [
        master for master in store.get("master_schedules", [])
        if master.get("week_start") == week_start
        and master.get("status") != MASTER_STATUS_ARCHIVED
    ]

    if not matching:
        return None

    return sorted(
        matching,
        key=lambda master: master.get("updated_at") or "",
        reverse=True,
    )[0]


def save_master_schedule(
    week_start: str,
    staffing_plan: Dict[str, Any],
    schedule: Dict[str, Any],
    source_plan_id: Optional[int] = None,
    status: str = MASTER_STATUS_DRAFT,
) -> Optional[int]:
    store = load_master_schedule_store()
    masters = store.get("master_schedules", [])

    existing = get_master_schedule_for_week(week_start)
    now = datetime.utcnow().isoformat()

    if existing:
        master_id = int(existing.get("id"))
        updated_masters = []

        for master in masters:
            if int(master.get("id", -1)) == master_id:
                master["staffing_plan"] = clean_staffing_plan_roles(staffing_plan)
                master["schedule"] = clean_schedule_roles(schedule)
                master["source_plan_id"] = source_plan_id
                master["status"] = status
                master["updated_at"] = now
                master.setdefault("edit_history", []).append({
                    "type": "full_save",
                    "timestamp": now,
                    "message": "Full master schedule saved.",
                })

            updated_masters.append(master)

        store["master_schedules"] = updated_masters
        save_master_schedule_store(store)
        return master_id

    master_id = int(store.get("next_id", 1))

    record = build_master_schedule_record(
        week_start=week_start,
        staffing_plan=staffing_plan,
        schedule=schedule,
        source_plan_id=source_plan_id,
        status=status,
    )

    record["id"] = master_id

    masters.append(record)

    store["master_schedules"] = masters
    store["next_id"] = master_id + 1

    if save_master_schedule_store(store):
        return master_id

    return None


def generate_and_save_master_schedule(
    week_start: str,
    staffing_plan: Dict[str, Any],
    source_plan_id: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    schedule = generate_schedule_from_plan(staffing_plan)

    master_id = save_master_schedule(
        week_start=week_start,
        staffing_plan=staffing_plan,
        schedule=schedule,
        source_plan_id=source_plan_id,
        status=MASTER_STATUS_DRAFT,
    )

    if not master_id:
        return None

    return get_master_schedule_for_week(week_start)


# ==============================================================================
# SECTION 13 — MASTER SCHEDULE EDIT HELPERS
# ==============================================================================

def normalize_assignment_list(assignments: Any) -> List[Dict[str, Any]]:
    """
    Normalize employee assignment payloads.

    Accepts:
    - list of full employee dicts
    - list of {id, name, role}
    - empty list
    """
    if not isinstance(assignments, list):
        return []

    normalized = []

    for assignment in assignments:
        if not isinstance(assignment, dict):
            continue

        normalized.append({
            "id": assignment.get("id"),
            "name": assignment.get("name", "Unnamed Employee"),
            "role": assignment.get("role", ""),
            "hourly_rate": assignment.get("hourly_rate", 0),
            "preference": assignment.get("preference", "Any"),
        })

    return normalized


def update_master_schedule_role(
    week_start: str,
    day: str,
    shift: str,
    role: str,
    assignments: List[Dict[str, Any]],
    edited_by: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    master = get_master_schedule_for_week(week_start)

    if not master:
        return None

    if day not in DAYS or shift not in SHIFTS or role not in ROLES:
        return None

    schedule = clean_schedule_roles(master.get("schedule", empty_schedule()))
    schedule[day][shift][role] = normalize_assignment_list(assignments)

    master["schedule"] = schedule
    master["updated_at"] = datetime.utcnow().isoformat()
    master.setdefault("edit_history", []).append({
        "type": "role_update",
        "day": day,
        "shift": shift,
        "role": role,
        "edited_by": edited_by,
        "timestamp": master["updated_at"],
    })

    return replace_master_schedule_record(master)


def update_master_schedule_shift(
    week_start: str,
    day: str,
    shift: str,
    shift_payload: Dict[str, Any],
    edited_by: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    master = get_master_schedule_for_week(week_start)

    if not master:
        return None

    if day not in DAYS or shift not in SHIFTS:
        return None

    schedule = clean_schedule_roles(master.get("schedule", empty_schedule()))

    for role in ROLES:
        schedule[day][shift][role] = normalize_assignment_list(
            shift_payload.get(role, [])
        )

    master["schedule"] = schedule
    master["updated_at"] = datetime.utcnow().isoformat()
    master.setdefault("edit_history", []).append({
        "type": "shift_update",
        "day": day,
        "shift": shift,
        "edited_by": edited_by,
        "timestamp": master["updated_at"],
    })

    return replace_master_schedule_record(master)


def update_master_schedule_day(
    week_start: str,
    day: str,
    day_payload: Dict[str, Any],
    edited_by: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    master = get_master_schedule_for_week(week_start)

    if not master:
        return None

    if day not in DAYS:
        return None

    schedule = clean_schedule_roles(master.get("schedule", empty_schedule()))

    for shift in SHIFTS:
        shift_payload = day_payload.get(shift, {})

        for role in ROLES:
            schedule[day][shift][role] = normalize_assignment_list(
                shift_payload.get(role, [])
            )

    master["schedule"] = schedule
    master["updated_at"] = datetime.utcnow().isoformat()
    master.setdefault("edit_history", []).append({
        "type": "day_update",
        "day": day,
        "edited_by": edited_by,
        "timestamp": master["updated_at"],
    })

    return replace_master_schedule_record(master)


def replace_master_schedule_record(
    updated_master: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    store = load_master_schedule_store()
    masters = store.get("master_schedules", [])

    updated = False
    output = []

    for master in masters:
        if int(master.get("id", -1)) == int(updated_master.get("id", -2)):
            output.append(updated_master)
            updated = True
        else:
            output.append(master)

    if not updated:
        return None

    store["master_schedules"] = output

    if not save_master_schedule_store(store):
        return None

    return updated_master


# ==============================================================================
# SECTION 14 — AVAILABILITY CACHE / BACKGROUND REANALYSIS
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
# SECTION 15 — FUTURE SHIFT SWAP / DROP / APPROVAL STRUCTURES
# ==============================================================================

def build_shift_change_request_stub(
    request_type: str,
    employee_id: int,
    day: str,
    shift: str,
    role: str,
    target_employee_id: Optional[int] = None,
) -> Dict[str, Any]:
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
# SECTION 16 — FUTURE EXPANSION BLOCKS
# ==============================================================================
# SECTION 16A — Real database-backed StaffingPlan CRUD
# SECTION 16B — Fair schedule rotation / hour balancing
# SECTION 16C — Manager approval queue logic
# SECTION 16D — Employee shift acceptance workflow
# SECTION 16E — Schedule publishing history
# SECTION 16F — Auto-save persisted schedules
# ==============================================================================