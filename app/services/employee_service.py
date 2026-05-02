"""
TABLE STACK v4 – EMPLOYEE SERVICE
------------------------------------------------------------
Purpose:
Employee data engine for Schedule Intelligence.

Features:
- Loads employees.json from project root
- Normalizes v2 employee data
- Supports role aliases
- Supports custom shift windows
- Supports employee availability
- Supports optional database mode if Flask-SQLAlchemy is installed
- Keeps JSON fallback working when database packages are missing
- Provides employee CRUD helper functions
- Provides roster summaries for dashboard/schedule tools
------------------------------------------------------------
"""

import csv
import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from flask import current_app


# ============================================================
# 1. CONFIGURATION
# ============================================================

USE_DATABASE = os.getenv("USE_DATABASE", "False").lower() == "true"

DEFAULT_EMPLOYEE_DATA = {
    "employees": [],
    "next_id": 1,
    "last_updated": None,
}


# ============================================================
# 2. CONSTANTS
# ============================================================

DAYS = [
    "Monday",
    "Tuesday",
    "Wednesday",
    "Thursday",
    "Friday",
    "Saturday",
    "Sunday",
]

SHIFT_NAMES = [
    "Morning Shift",
    "Dinner Shift",
]

ROLE_ALIASES = {
    "Server": "Server",
    "Bartender": "Bartender",
    "Barback": "Barback",
    "Host": "Host",
    "Runner": "Runner",
    "Busser": "Busser",
    "Backwaiter": "Backwaiter",
    "Kitchen": "Kitchen",
    "Dishwasher": "Dishwasher",
    "Expo": "Expo",
    "Expeditor": "Expo",
    "Food Expeditor": "Expo",
    "Manager": "Manager",
    "Owner": "Manager",
    "Parkside": "Server",
}


# ============================================================
# 3. SAFE LOGGING
# ============================================================

def log_warning(message: str) -> None:
    try:
        current_app.logger.warning(message)
    except RuntimeError:
        pass


def log_error(message: str) -> None:
    try:
        current_app.logger.error(message)
    except RuntimeError:
        pass


# ============================================================
# 4. FILE LOADING / SAVING
# ============================================================

def get_employee_file_path() -> Path:
    """
    Expected project structure:

    table-stack-v4/
        run.py
        employees.json
        app/
    """
    return Path.cwd() / "employees.json"


def load_employee_file(path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load employees.json safely.
    """
    file_path = path or get_employee_file_path()

    if not file_path.exists():
        log_warning(f"employees.json not found at {file_path}")
        return DEFAULT_EMPLOYEE_DATA.copy()

    try:
        with file_path.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, dict):
            log_warning("employees.json did not contain a dictionary.")
            return DEFAULT_EMPLOYEE_DATA.copy()

        if "employees" not in data or not isinstance(data["employees"], list):
            data["employees"] = []

        if "next_id" not in data:
            existing_ids = [
                emp.get("id", 0)
                for emp in data["employees"]
                if isinstance(emp, dict) and isinstance(emp.get("id"), int)
            ]
            data["next_id"] = max(existing_ids, default=0) + 1

        if "last_updated" not in data:
            data["last_updated"] = None

        return data

    except json.JSONDecodeError as error:
        log_error(f"Invalid employees.json: {error}")
        return DEFAULT_EMPLOYEE_DATA.copy()
    except OSError as error:
        log_error(f"Could not read employees.json: {error}")
        return DEFAULT_EMPLOYEE_DATA.copy()


def save_employee_file(data: Dict[str, Any]) -> bool:
    """
    Save employees.json safely.
    """
    file_path = get_employee_file_path()

    try:
        data["last_updated"] = datetime.now().isoformat()

        if "employees" not in data:
            data["employees"] = []

        existing_ids = [
            emp.get("id", 0)
            for emp in data["employees"]
            if isinstance(emp, dict) and isinstance(emp.get("id"), int)
        ]
        data["next_id"] = max(existing_ids, default=0) + 1

        with file_path.open("w", encoding="utf-8") as file:
            json.dump(data, file, indent=2)

        return True

    except OSError as error:
        log_error(f"Could not save employees.json: {error}")
        return False


# ============================================================
# 5. NORMALIZATION HELPERS
# ============================================================

def normalize_role(role: str) -> str:
    clean_role = (role or "").strip()
    return ROLE_ALIASES.get(clean_role, clean_role or "Unassigned")


def normalize_employment_type(value: str) -> str:
    value = (value or "Part Time").strip()

    if value.lower() in {"full time", "full-time", "ft"}:
        return "Full Time"

    if value.lower() in {"part time", "part-time", "pt"}:
        return "Part Time"

    return value


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def normalize_shift_windows(employee: Dict[str, Any]) -> Dict[str, Dict[str, str]]:
    """
    Converts v2 custom_times into:

    {
        "Monday": {"start": "17:00", "end": "22:00"}
    }
    """
    custom_times = employee.get("custom_times") or employee.get("shift_windows") or {}
    normalized = {}

    for day in DAYS:
        day_times = custom_times.get(day)

        if not isinstance(day_times, dict):
            continue

        start = day_times.get("start")
        end = day_times.get("end")

        if start and end:
            normalized[day] = {
                "start": str(start),
                "end": str(end),
            }

    return normalized


def normalize_availability(employee: Dict[str, Any]) -> Dict[str, str]:
    """
    Availability priority:
    1. Existing availability dict
    2. custom_times/shift_windows means Custom
    3. Otherwise Off
    """
    raw_availability = employee.get("availability") or {}
    shift_windows = normalize_shift_windows(employee)

    normalized = {}

    for day in DAYS:
        value = raw_availability.get(day)

        if value in {"Both", "Morning", "Dinner", "Custom", "Off"}:
            normalized[day] = value
        elif day in shift_windows:
            normalized[day] = "Custom"
        else:
            normalized[day] = "Off"

    return normalized


def normalize_employee(employee: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize one raw employee record.

    Supports both old v2 names:
    - type
    - hours
    - rate
    - pref
    - custom_times

    And v4 names:
    - employment_type
    - weekly_hours_target
    - hourly_rate
    - preference
    - shift_windows
    """
    weekly_hours = safe_float(
        employee.get("weekly_hours_target", employee.get("hours", 0.0)),
        0.0,
    )
    hourly_rate = safe_float(
        employee.get("hourly_rate", employee.get("rate", 0.0)),
        0.0,
    )

    shift_windows = normalize_shift_windows(employee)
    availability = normalize_availability(employee)

    has_hours = weekly_hours > 0
    has_windows = bool(shift_windows)
    has_availability = any(value != "Off" for value in availability.values())

    return {
        "id": employee.get("id"),
        "name": employee.get("name", "Unnamed Employee"),
        "role": normalize_role(employee.get("role", "")),
        "original_role": employee.get("original_role", employee.get("role", "")),
        "employment_type": normalize_employment_type(
            employee.get("employment_type", employee.get("type", "Part Time"))
        ),
        "weekly_hours_target": weekly_hours,
        "hourly_rate": hourly_rate,
        "estimated_weekly_labor": round(weekly_hours * hourly_rate, 2),
        "preference": employee.get("preference", employee.get("pref", "Any")),
        "availability": availability,
        "shift_windows": shift_windows,
        "certifications": employee.get("certifications", []),
        "unavailable_dates": employee.get("unavailable_dates", []),
        "notes": employee.get("notes", ""),
        "active": bool(employee.get("active", has_hours or has_windows or has_availability)),
    }


def employee_to_legacy_json(employee: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert normalized employee back into employees.json-friendly structure.
    Keeps the v2 format mostly intact.
    """
    return {
        "id": employee.get("id"),
        "name": employee.get("name", "Unnamed Employee"),
        "role": employee.get("original_role") or employee.get("role", "Unassigned"),
        "type": employee.get("employment_type", "Part Time"),
        "hours": employee.get("weekly_hours_target", 0.0),
        "rate": employee.get("hourly_rate", 0.0),
        "pref": employee.get("preference", "Any"),
        "custom_times": employee.get("shift_windows", {}),
        "availability": employee.get("availability", {}),
        "certifications": employee.get("certifications", []),
        "unavailable_dates": employee.get("unavailable_dates", []),
        "notes": employee.get("notes", ""),
    }


# ============================================================
# 6. OPTIONAL DATABASE MODELS
# ============================================================

try:
    from flask_sqlalchemy import SQLAlchemy
    from sqlalchemy.types import JSON

    db = SQLAlchemy()

    class Employee(db.Model):
        __tablename__ = "employees"

        id = db.Column(db.Integer, primary_key=True)
        name = db.Column(db.String(100), nullable=False)
        role = db.Column(db.String(50), nullable=False)
        original_role = db.Column(db.String(50))
        employment_type = db.Column(db.String(20), default="Part Time")
        weekly_hours_target = db.Column(db.Float, default=0.0)
        hourly_rate = db.Column(db.Float, default=0.0)
        estimated_weekly_labor = db.Column(db.Float, default=0.0)
        preference = db.Column(db.String(80), default="Any")
        availability = db.Column(JSON, default={})
        shift_windows = db.Column(JSON, default={})
        certifications = db.Column(JSON, default=[])
        unavailable_dates = db.Column(JSON, default=[])
        notes = db.Column(db.Text, default="")
        active = db.Column(db.Boolean, default=True)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)
        updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    MODELS_AVAILABLE = True

except ImportError:
    db = None
    Employee = None
    MODELS_AVAILABLE = False


def get_db():
    return db if MODELS_AVAILABLE else None


def employee_model_to_dict(employee_model) -> Dict[str, Any]:
    return {
        "id": employee_model.id,
        "name": employee_model.name,
        "role": employee_model.role,
        "original_role": employee_model.original_role,
        "employment_type": employee_model.employment_type,
        "weekly_hours_target": employee_model.weekly_hours_target,
        "hourly_rate": employee_model.hourly_rate,
        "estimated_weekly_labor": employee_model.estimated_weekly_labor,
        "preference": employee_model.preference,
        "availability": employee_model.availability or {},
        "shift_windows": employee_model.shift_windows or {},
        "certifications": employee_model.certifications or [],
        "unavailable_dates": employee_model.unavailable_dates or [],
        "notes": employee_model.notes or "",
        "active": employee_model.active,
    }


def get_all_employees_from_db() -> List[Dict[str, Any]]:
    if not USE_DATABASE or not MODELS_AVAILABLE:
        return []

    try:
        employees = db.session.query(Employee).order_by(Employee.name).all()
        return [employee_model_to_dict(employee) for employee in employees]
    except Exception as error:
        log_error(f"Failed to fetch employees from DB: {error}")
        return []


def save_employee_to_db(employee_data: Dict[str, Any]) -> Optional[int]:
    if not USE_DATABASE or not MODELS_AVAILABLE:
        return None

    try:
        normalized = normalize_employee(employee_data)
        employee_id = normalized.get("id")

        if employee_id:
            employee_model = db.session.query(Employee).filter(Employee.id == employee_id).first()
            if not employee_model:
                return None
        else:
            employee_model = Employee()
            db.session.add(employee_model)

        for key, value in normalized.items():
            if key != "id" and hasattr(employee_model, key):
                setattr(employee_model, key, value)

        employee_model.updated_at = datetime.utcnow()
        db.session.commit()

        return employee_model.id

    except Exception as error:
        log_error(f"Failed to save employee to DB: {error}")
        try:
            db.session.rollback()
        except Exception:
            pass
        return None


def delete_employee_from_db(employee_id: int) -> bool:
    if not USE_DATABASE or not MODELS_AVAILABLE:
        return False

    try:
        employee_model = db.session.query(Employee).filter(Employee.id == employee_id).first()

        if not employee_model:
            return False

        db.session.delete(employee_model)
        db.session.commit()
        return True

    except Exception as error:
        log_error(f"Failed to delete employee from DB: {error}")
        try:
            db.session.rollback()
        except Exception:
            pass
        return False


# ============================================================
# 7. PUBLIC EMPLOYEE GETTERS
# ============================================================

def get_all_employees() -> List[Dict[str, Any]]:
    """
    Return all employees, normalized.
    """
    if USE_DATABASE and MODELS_AVAILABLE:
        db_employees = get_all_employees_from_db()
        if db_employees:
            return db_employees

    raw_data = load_employee_file()
    raw_employees = raw_data.get("employees", [])

    employees = [
        normalize_employee(employee)
        for employee in raw_employees
        if isinstance(employee, dict)
    ]

    if not employees:
        log_warning(
            "No employees loaded. Check employees.json location or USE_DATABASE setting."
        )

    return employees


def get_active_employees() -> List[Dict[str, Any]]:
    return [
        employee for employee in get_all_employees()
        if employee.get("active")
    ]


def get_employee_by_id(employee_id: int) -> Optional[Dict[str, Any]]:
    employee_id = safe_int(employee_id, -1)

    for employee in get_all_employees():
        if employee.get("id") == employee_id:
            return employee

    return None


def get_employees_by_role(role: str) -> List[Dict[str, Any]]:
    normalized_role = normalize_role(role)

    return [
        employee for employee in get_all_employees()
        if employee.get("role") == normalized_role
    ]


# ============================================================
# 8. AVAILABILITY LOGIC
# ============================================================

def employee_can_work_day(employee: Dict[str, Any], day: str) -> bool:
    availability = employee.get("availability", {})
    value = availability.get(day, "Off")
    return value in {"Both", "Morning", "Dinner", "Custom"}


def employee_can_work_shift(employee: Dict[str, Any], day: str, shift: str) -> bool:
    availability = employee.get("availability", {})
    value = availability.get(day, "Off")

    if value == "Off":
        return False

    if value == "Both":
        return True

    if value == "Custom":
        return day in employee.get("shift_windows", {})

    if value == "Morning" and shift == "Morning Shift":
        return True

    if value == "Dinner" and shift == "Dinner Shift":
        return True

    return False


def get_available_employees_for_shift(
    day: str,
    shift: str,
    role: Optional[str] = None,
) -> List[Dict[str, Any]]:
    employees = get_all_employees()

    if role:
        normalized_role = normalize_role(role)
        employees = [
            employee for employee in employees
            if employee.get("role") == normalized_role
        ]

    return [
        employee for employee in employees
        if employee_can_work_shift(employee, day, shift)
    ]


# ============================================================
# 9. SUMMARY / DASHBOARD DATA
# ============================================================

def get_employee_summary() -> Dict[str, Any]:
    employees = get_all_employees()
    active_employees = get_active_employees()

    role_counts = {}
    total_target_hours = 0.0
    estimated_weekly_labor = 0.0

    for employee in active_employees:
        role = employee.get("role", "Unassigned")
        role_counts[role] = role_counts.get(role, 0) + 1

        total_target_hours += safe_float(employee.get("weekly_hours_target"), 0.0)
        estimated_weekly_labor += safe_float(employee.get("estimated_weekly_labor"), 0.0)

    return {
        "total_employees": len(employees),
        "active_employees": len(active_employees),
        "inactive_employees": len(employees) - len(active_employees),
        "role_counts": role_counts,
        "total_target_hours": round(total_target_hours, 1),
        "estimated_weekly_labor": round(estimated_weekly_labor, 2),
    }


def get_role_summary() -> List[Dict[str, Any]]:
    employees = get_active_employees()
    roles = sorted(set(employee.get("role", "Unassigned") for employee in employees))

    summary = []

    for role in roles:
        role_employees = [
            employee for employee in employees
            if employee.get("role") == role
        ]

        total_hours = sum(
            safe_float(employee.get("weekly_hours_target"), 0.0)
            for employee in role_employees
        )

        average_rate = 0.0
        if role_employees:
            average_rate = sum(
                safe_float(employee.get("hourly_rate"), 0.0)
                for employee in role_employees
            ) / len(role_employees)

        summary.append({
            "role": role,
            "employee_count": len(role_employees),
            "total_target_hours": round(total_hours, 1),
            "average_rate": round(average_rate, 2),
            "employees": [employee.get("name") for employee in role_employees],
        })

    return summary


def get_employee_debug_report() -> Dict[str, Any]:
    return {
        "file_path": str(get_employee_file_path()),
        "file_exists": get_employee_file_path().exists(),
        "summary": get_employee_summary(),
        "roles": get_role_summary(),
    }


# ============================================================
# 10. CRUD API HELPERS
# ============================================================

def add_employee(employee_data: Dict[str, Any]) -> Optional[int]:
    """
    Add a new employee.

    If database mode is off, writes to employees.json.
    """
    if USE_DATABASE and MODELS_AVAILABLE:
        return save_employee_to_db(employee_data)

    data = load_employee_file()
    employees = data.get("employees", [])

    new_id = data.get("next_id")
    if not isinstance(new_id, int):
        existing_ids = [
            employee.get("id", 0)
            for employee in employees
            if isinstance(employee, dict) and isinstance(employee.get("id"), int)
        ]
        new_id = max(existing_ids, default=0) + 1

    employee_data["id"] = new_id
    normalized = normalize_employee(employee_data)
    employees.append(employee_to_legacy_json(normalized))

    data["employees"] = employees

    if save_employee_file(data):
        return new_id

    return None


def update_employee(employee_id: int, updates: Dict[str, Any]) -> bool:
    """
    Update an employee.

    Works in JSON fallback mode and DB mode.
    """
    employee_id = safe_int(employee_id, -1)

    if USE_DATABASE and MODELS_AVAILABLE:
        existing = get_employee_by_id(employee_id)
        if not existing:
            return False

        existing.update(updates)
        return save_employee_to_db(existing) is not None

    data = load_employee_file()
    employees = data.get("employees", [])

    for index, raw_employee in enumerate(employees):
        if raw_employee.get("id") == employee_id:
            normalized = normalize_employee(raw_employee)

            for key, value in updates.items():
                normalized[key] = value

            normalized["active"] = (
                safe_float(normalized.get("weekly_hours_target"), 0.0) > 0
                or bool(normalized.get("shift_windows"))
                or any(
                    value != "Off"
                    for value in normalized.get("availability", {}).values()
                )
            )

            employees[index] = employee_to_legacy_json(normalized)
            data["employees"] = employees
            return save_employee_file(data)

    return False


def delete_employee(employee_id: int) -> bool:
    employee_id = safe_int(employee_id, -1)

    if USE_DATABASE and MODELS_AVAILABLE:
        return delete_employee_from_db(employee_id)

    data = load_employee_file()
    employees = data.get("employees", [])

    new_employees = [
        employee for employee in employees
        if employee.get("id") != employee_id
    ]

    if len(new_employees) == len(employees):
        return False

    data["employees"] = new_employees
    return save_employee_file(data)


# ============================================================
# 11. FILE IMPORT / BACKGROUND PROCESSING
# ============================================================

ALLOWED_IMPORT_EXTENSIONS = {"json", "csv"}
UPLOAD_FOLDER = Path.cwd() / "uploads"
IMPORT_TASKS: Dict[str, Any] = {}


def process_employee_import_file(file_path: str, file_type: str) -> Dict[str, Any]:
    imported = 0
    errors = []

    try:
        if file_type == "json":
            with open(file_path, "r", encoding="utf-8") as file:
                data = json.load(file)

            employees = data if isinstance(data, list) else data.get("employees", [])

            for employee_data in employees:
                employee_id = add_employee(employee_data)
                if employee_id:
                    imported += 1
                else:
                    errors.append(f"Failed to import {employee_data.get('name', 'Unnamed')}")

        elif file_type == "csv":
            with open(file_path, "r", encoding="utf-8") as file:
                reader = csv.DictReader(file)

                for row in reader:
                    employee_data = {
                        "name": row.get("name", ""),
                        "role": row.get("role", ""),
                        "hours": safe_float(row.get("weekly_hours_target", 0)),
                        "rate": safe_float(row.get("hourly_rate", 0)),
                        "type": row.get("employment_type", "Part Time"),
                        "pref": row.get("preference", "Any"),
                    }

                    employee_id = add_employee(employee_data)

                    if employee_id:
                        imported += 1
                    else:
                        errors.append(f"Failed to import {employee_data.get('name', 'Unnamed')}")

        else:
            return {
                "status": "failed",
                "error": f"Unsupported file type: {file_type}",
                "imported": imported,
                "errors": errors,
            }

        return {
            "status": "complete",
            "imported": imported,
            "errors": errors,
        }

    except Exception as error:
        return {
            "status": "failed",
            "error": str(error),
            "imported": imported,
            "errors": errors,
        }


def start_employee_import_background(file_path: str, file_type: str) -> str:
    task_id = str(uuid.uuid4())

    def worker() -> None:
        result = process_employee_import_file(file_path, file_type)
        IMPORT_TASKS[task_id] = result

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    IMPORT_TASKS[task_id] = {"status": "processing"}
    return task_id


def get_employee_import_status(task_id: str) -> Dict[str, Any]:
    return IMPORT_TASKS.get(task_id, {"status": "not_found"})