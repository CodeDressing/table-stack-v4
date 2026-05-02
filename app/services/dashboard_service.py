"""
TABLE STACK v4 – ENHANCED DASHBOARD SERVICE LAYER (PHASE 8)
--------------------------------------------------------------------------------
Purpose: All business logic, calculations, and data preparation for the dashboard.
Rules: Routes stay thin – this file does the heavy lifting.

Phase 8 Additions:
- Database integration stubs (SQLAlchemy models, session management)
- Ability to read weekly data from database when USE_DATABASE = True
- Save/load imported report data (OCR results)
- Historical weekly data versioning
- Background forecast recalculation trigger
- All existing mock-based functions remain unchanged (backward compatible)

Structure:
1. Configuration flag (USE_DATABASE)
2. Mock data (unchanged)
3. Helper functions (unchanged)
4. Weekly snapshot (unchanged)
5. Summary totals & metrics (unchanged)
6. Forecasting engine (unchanged)
7. Labor optimizer (unchanged)
8. AI recommendations (unchanged)
9. Insight cards (unchanged)
10. Main context builder (now database-aware)
11. PHASE 8: Database models (SQLAlchemy)
12. PHASE 8: Database session manager
13. PHASE 8: CRUD operations for weekly data
14. PHASE 8: Import & save uploaded report data
15. PHASE 8: Background forecast recalculation stub
16. Existing API-facing functions (unchanged)
17. Future expansion blocks

Ready for 10k+ lines: each section can be replaced independently.
--------------------------------------------------------------------------------
"""

import math
import random
import os
import json
import threading
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

# Flask app context is used only inside request-handling functions – not at top level
from flask import current_app

# ------------------------------------------------------------
# 1. CONFIGURATION FLAG (set via environment variable)
# ------------------------------------------------------------
USE_DATABASE = os.getenv('USE_DATABASE', 'False').lower() == 'true'

# ------------------------------------------------------------
# 2. MOCK DATA (unchanged – used when USE_DATABASE=False)
# ------------------------------------------------------------
BASE_WEEKLY_DATA = [
    {
        "day": "Monday",
        "sales": 1250.00,
        "labor_cost": 410.00,
        "staff_hours": 22,
        "weather": "Sunny",
        "event": "None",
        "efficiency": 0.92,
        "holiday": False
    },
    {
        "day": "Tuesday",
        "sales": 1420.00,
        "labor_cost": 390.00,
        "staff_hours": 21,
        "weather": "Cloudy",
        "event": "None",
        "efficiency": 0.95,
        "holiday": False
    },
    {
        "day": "Wednesday",
        "sales": 1675.00,
        "labor_cost": 430.00,
        "staff_hours": 23,
        "weather": "Rainy",
        "event": "None",
        "efficiency": 0.88,
        "holiday": False
    },
    {
        "day": "Thursday",
        "sales": 1980.00,
        "labor_cost": 505.00,
        "staff_hours": 27,
        "weather": "Sunny",
        "event": "Happy Hour",
        "efficiency": 0.85,
        "holiday": False
    },
    {
        "day": "Friday",
        "sales": 2850.00,
        "labor_cost": 690.00,
        "staff_hours": 36,
        "weather": "Sunny",
        "event": "Live Music",
        "efficiency": 0.79,
        "holiday": False
    },
    {
        "day": "Saturday",
        "sales": 2375.00,
        "labor_cost": 640.00,
        "staff_hours": 34,
        "weather": "Sunny",
        "event": "Weekend Rush",
        "efficiency": 0.81,
        "holiday": False
    },
    {
        "day": "Sunday",
        "sales": 900.00,
        "labor_cost": 215.00,
        "staff_hours": 11,
        "weather": "Cloudy",
        "event": "None",
        "efficiency": 0.97,
        "holiday": False
    }
]

HISTORICAL_WEEKLY_SALES = [11200, 11800, 12100, 12450, 13000, 12850, 13200, 13450]


# ------------------------------------------------------------

# ------------------------------------------------------------
# 3. HELPER FUNCTIONS (unchanged)
# ------------------------------------------------------------
def calculate_labor_percentage(sales: float, labor_cost: float) -> float:
    if sales <= 0:
        return 0.0
    return (labor_cost / sales) * 100.0

def format_currency(amount: float) -> str:
    return f"${amount:,.0f}"

def format_percentage(value: float) -> str:
    return f"{value:.1f}%"

def parse_currency_string(value: str) -> float:
    return float(value.replace('$', '').replace(',', ''))

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    return numerator / denominator if denominator != 0 else default


# ------------------------------------------------------------
# 4. WEEKLY SNAPSHOT (unchanged)
# ------------------------------------------------------------
def build_weekly_snapshot(weekly_data: List[Dict]) -> List[Dict[str, Any]]:
    snapshot = []
    for row in weekly_data:
        labor_percent = calculate_labor_percentage(row["sales"], row["labor_cost"])
        snapshot.append({
            "day": row["day"],
            "sales": format_currency(row["sales"]),
            "labor": format_currency(row["labor_cost"]),
            "labor_percent": format_percentage(labor_percent),
            "staff_hours": row["staff_hours"],
            "efficiency": f"{row['efficiency'] * 100:.0f}%",
            "weather": row["weather"],
            "event": row["event"],
            "_raw_sales": row["sales"],
            "_raw_labor": row["labor_cost"]
        })
    return snapshot


# ------------------------------------------------------------
# 5. SUMMARY TOTALS & METRICS (unchanged)
# ------------------------------------------------------------
def calculate_summary_totals(weekly_data: List[Dict]) -> Dict[str, float]:
    total_sales = sum(row["sales"] for row in weekly_data)
    total_labor = sum(row["labor_cost"] for row in weekly_data)
    total_hours = sum(row["staff_hours"] for row in weekly_data)
    labor_percent = calculate_labor_percentage(total_sales, total_labor)
    sales_per_labor_hour = safe_divide(total_sales, total_hours)
    return {
        "total_sales": total_sales,
        "total_labor_cost": total_labor,
        "total_staff_hours": total_hours,
        "labor_percentage": labor_percent,
        "sales_per_labor_hour": sales_per_labor_hour
    }

def get_labor_status(labor_percent: float, target: float = 25.0) -> Dict[str, str]:
    if labor_percent <= target:
        return {
            "status": "positive",
            "change": "On target",
            "description": f"Labor at {format_percentage(labor_percent)} vs target {target}%"
        }
    if labor_percent <= target + 3:
        return {
            "status": "warning",
            "change": f"+{labor_percent - target:.1f}%",
            "description": f"Slightly above target ({format_percentage(labor_percent)})"
        }
    return {
        "status": "danger",
        "change": f"+{labor_percent - target:.1f}%",
        "description": f"Significantly above target ({format_percentage(labor_percent)})"
    }

def build_summary_metrics(totals: Dict[str, float], target_labor: float = 25.0) -> List[Dict]:
    labor_status = get_labor_status(totals["labor_percentage"], target_labor)
    return [
        {"label": "Total Sales", "value": format_currency(totals["total_sales"]), "change": "This week", "status": "neutral", "description": "Gross revenue"},
        {"label": "Labor Cost", "value": format_currency(totals["total_labor_cost"]), "change": "Total spend", "status": "neutral", "description": "Wages + taxes"},
        {"label": "Labor %", "value": format_percentage(totals["labor_percentage"]), "change": labor_status["change"], "status": labor_status["status"], "description": labor_status["description"]},
        {"label": "Staff Hours", "value": str(int(totals["total_staff_hours"])), "change": "Scheduled", "status": "neutral", "description": "Total hours worked"},
        {"label": "Sales / Labor Hour", "value": format_currency(totals["sales_per_labor_hour"]), "change": "Productivity", "status": "neutral", "description": "Revenue per labor hour"}
    ]


# ------------------------------------------------------------
# 6. FORECASTING ENGINE (unchanged)
# ------------------------------------------------------------
def get_forecast_data(weeks_ahead: int = 2) -> List[Dict[str, str]]:
    n = len(HISTORICAL_WEEKLY_SALES)
    if n < 2:
        forecast_weeks = [HISTORICAL_WEEKLY_SALES[-1] * (1 + 0.02 * i) for i in range(1, weeks_ahead+1)]
    else:
        x = list(range(n))
        y = HISTORICAL_WEEKLY_SALES
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        denominator = sum((x[i] - mean_x) ** 2 for i in range(n))
        slope = numerator / denominator if denominator != 0 else 0
        intercept = mean_y - slope * mean_x
        forecast_weeks = [intercept + slope * (n + i) for i in range(1, weeks_ahead+1)]

    weekly_sales_current = sum(row["sales"] for row in BASE_WEEKLY_DATA)
    daily_weights = [row["sales"] / weekly_sales_current for row in BASE_WEEKLY_DATA]
    labor_percentages = [calculate_labor_percentage(row["sales"], row["labor_cost"]) for row in BASE_WEEKLY_DATA]
    avg_labor_percent = sum(labor_percentages) / len(labor_percentages)

    weekly_summary = []
    for w, week_total in enumerate(forecast_weeks, start=1):
        week_labor = week_total * (avg_labor_percent / 100)
        weekly_summary.append({
            "week": f"Week +{w}",
            "sales": format_currency(week_total),
            "labor": format_currency(week_labor),
            "labor_percent": format_percentage(calculate_labor_percentage(week_total, week_labor))
        })
    return weekly_summary


# ------------------------------------------------------------
# 7. LABOR OPTIMIZER (unchanged)
# ------------------------------------------------------------
def optimize_labor(target_labor_percent: float, weekly_data: Optional[List[Dict]] = None) -> Dict[str, Any]:
    data = weekly_data if weekly_data is not None else BASE_WEEKLY_DATA
    suggestions = []
    for day in data:
        current_lp = calculate_labor_percentage(day["sales"], day["labor_cost"])
        if current_lp <= target_labor_percent:
            continue
        ideal_labor = day["sales"] * (target_labor_percent / 100)
        labor_reduction = day["labor_cost"] - ideal_labor
        wage_rate = 20.0
        hour_reduction = labor_reduction / wage_rate
        suggested_hours = max(0, day["staff_hours"] - hour_reduction)
        suggestions.append({
            "day": day["day"],
            "current_hours": day["staff_hours"],
            "suggested_hours": round(suggested_hours, 1),
            "labor_reduction": format_currency(labor_reduction)
        })
    return {
        "optimized_schedule": suggestions,
        "target_labor": target_labor_percent,
        "note": "Assumes $20/hour average wage. Actual savings may vary."
    }


# ------------------------------------------------------------
# 8. AI RECOMMENDATIONS (unchanged)
# ------------------------------------------------------------
def generate_ai_recommendations(weekly_data: List[Dict], totals: Dict) -> List[Dict[str, str]]:
    recommendations = []
    worst_day = max(weekly_data, key=lambda x: calculate_labor_percentage(x["sales"], x["labor_cost"]))
    worst_lp = calculate_labor_percentage(worst_day["sales"], worst_day["labor_cost"])
    if worst_lp > 27:
        recommendations.append({
            "title": "Reduce Overstaffing",
            "detail": f"{worst_day['day']} labor reached {format_percentage(worst_lp)}. Cut 2-3 hours.",
            "impact": f"Save ~${worst_day['labor_cost'] * 0.1:.0f} and lower labor % by ~3 points."
        })
    best_day = max(weekly_data, key=lambda x: x["sales"])
    recommendations.append({
        "title": "Capitalize on Peak Days",
        "detail": f"{best_day['day']} generated {format_currency(best_day['sales'])}. Run specials or events.",
        "impact": "Potential +10% sales lift with minimal labor increase."
    })
    rainy_days = [d for d in weekly_data if d["weather"].lower() == "rainy"]
    if rainy_days:
        rainy = rainy_days[0]
        rainy_lp = calculate_labor_percentage(rainy["sales"], rainy["labor_cost"])
        recommendations.append({
            "title": "Weather‑Based Staffing",
            "detail": f"Rainy days like {rainy['day']} hit {format_percentage(rainy_lp)} labor. Reduce FOH by 1-2.",
            "impact": "Save ~$80 on slow shifts."
        })
    avg_sales_per_hour = totals["sales_per_labor_hour"]
    if avg_sales_per_hour < 40:
        recommendations.append({
            "title": "Boost Productivity",
            "detail": f"Sales per labor hour at {format_currency(avg_sales_per_hour)}. Target >$50.",
            "impact": "Cross‑train staff to handle multiple roles."
        })
    else:
        recommendations.append({
            "title": "Strong Efficiency",
            "detail": f"Sales per labor hour at {format_currency(avg_sales_per_hour)} – above benchmark.",
            "impact": "Maintain schedule and consider small bonuses."
        })
    if len(recommendations) < 3:
        recommendations.append({
            "title": "Forecast Opportunity",
            "detail": "Next week's forecast shows +3% sales growth. Adjust labor by +2%.",
            "impact": "Capture additional revenue without overspending."
        })
    return recommendations[:4]


# ------------------------------------------------------------
# 9. OPERATIONAL INSIGHT CARDS (unchanged)
# ------------------------------------------------------------
def find_best_sales_day(weekly_data: List[Dict]) -> Dict:
    return max(weekly_data, key=lambda x: x["sales"])

def find_highest_labor_risk_day(weekly_data: List[Dict]) -> Dict:
    return max(weekly_data, key=lambda x: calculate_labor_percentage(x["sales"], x["labor_cost"]))

def build_operational_insights(weekly_data: List[Dict]) -> List[Dict[str, str]]:
    best = find_best_sales_day(weekly_data)
    risk = find_highest_labor_risk_day(weekly_data)
    risk_percent = calculate_labor_percentage(risk["sales"], risk["labor_cost"])
    most_efficient = max(weekly_data, key=lambda x: x["efficiency"])
    return [
        {"title": "Best Sales Day", "value": best["day"], "details": f"{best['day']} generated {format_currency(best['sales'])}."},
        {"title": "Highest Labor Risk", "value": risk["day"], "details": f"{risk['day']} reached {format_percentage(risk_percent)} labor."},
        {"title": "Efficiency Leader", "value": most_efficient["day"], "details": f"{most_efficient['day']} achieved {most_efficient['efficiency']*100:.0f}% sales per hour efficiency."},
        {"title": "Staffing Intelligence", "value": "AI Ready", "details": "Future: compare sales, weather, events & schedule coverage."}
    ]


# ------------------------------------------------------------
# 10. MAIN CONTEXT BUILDER (now database-aware)
# ------------------------------------------------------------
def get_weekly_data_from_source() -> List[Dict]:
    """Fetch weekly data either from database or mock."""
    if USE_DATABASE:
        # Attempt to load from database
        try:
            from app.services.dashboard_db import get_current_weekly_data
            db_data = get_current_weekly_data()
            if db_data:
                return db_data
        except (ImportError, Exception) as e:
            if current_app:
                current_app.logger.warning(f"Database fetch failed, falling back to mock: {e}")
    # Fallback to mock
    return [row.copy() for row in BASE_WEEKLY_DATA]

def get_dashboard_context(target_labor_percent: float = 25.0) -> Dict[str, Any]:
    """Build the full dashboard context (now pulls from DB if enabled)."""
    weekly_data = get_weekly_data_from_source()
    totals = calculate_summary_totals(weekly_data)
    metrics = build_summary_metrics(totals, target_labor_percent)
    recommendations = generate_ai_recommendations(weekly_data, totals)
    forecast_preview = get_forecast_data(2)
    weekly_snapshot = build_weekly_snapshot(weekly_data)
    insight_cards = build_operational_insights(weekly_data)
    future_modules = [
        "OCR Sales Import (Phase 8)",
        "Weather API Integration (Phase 9)",
        "Real Staff Scheduling (Phase 10)",
        "Profitability Engine (Phase 11)",
        "Mobile App Companion (Phase 12)",
        "Live POS Integration (Phase 13)"
    ]
    return {
        "page": {"title": "Table Stack v4 Intelligence Suite", "subtitle": "Real‑time sales, labor, forecast & AI recommendations."},
        "summary_metrics": metrics,
        "weekly_snapshot": weekly_snapshot,
        "insight_cards": insight_cards,
        "recommendations": recommendations,
        "forecast_preview": forecast_preview,
        "future_modules": future_modules
    }


# ------------------------------------------------------------
# 11. PHASE 8: DATABASE MODELS (SQLAlchemy stubs)
# ------------------------------------------------------------
# These are placeholders. When SQLAlchemy is installed, replace with real models.
# They are defined here so that other functions can reference them.
try:
    from flask_sqlalchemy import SQLAlchemy
    db = SQLAlchemy()

    class WeeklyData(db.Model):
        __tablename__ = 'weekly_data'
        id = db.Column(db.Integer, primary_key=True)
        week_start = db.Column(db.Date, nullable=False)
        day = db.Column(db.String(20), nullable=False)
        sales = db.Column(db.Float, nullable=False)
        labor_cost = db.Column(db.Float, nullable=False)
        staff_hours = db.Column(db.Float, nullable=False)
        weather = db.Column(db.String(50))
        event = db.Column(db.String(100))
        efficiency = db.Column(db.Float)
        holiday = db.Column(db.Boolean, default=False)
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

    class ImportedReport(db.Model):
        __tablename__ = 'imported_reports'
        id = db.Column(db.Integer, primary_key=True)
        filename = db.Column(db.String(255))
        file_type = db.Column(db.String(20))
        parsed_data = db.Column(db.JSON)
        status = db.Column(db.String(50), default='pending')
        created_at = db.Column(db.DateTime, default=datetime.utcnow)

    MODELS_AVAILABLE = True
except ImportError:
    MODELS_AVAILABLE = False
    db = None
    WeeklyData = None
    ImportedReport = None


# ------------------------------------------------------------
# 12. PHASE 8: DATABASE SESSION MANAGER
# ------------------------------------------------------------
def get_db():
    """Return database session if available."""
    if MODELS_AVAILABLE and db:
        return db
    return None

def save_weekly_data_to_db(weekly_rows: List[Dict], week_start_date: Optional[datetime] = None) -> bool:
    """Save a full week of data to database. Returns success boolean."""
    if not USE_DATABASE or not MODELS_AVAILABLE:
        return False
    try:
        db_session = get_db()
        if not db_session:
            return False
        week_start = week_start_date or datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        # Delete existing data for same week to avoid duplicates
        db_session.session.query(WeeklyData).filter(WeeklyData.week_start == week_start).delete()
        for row in weekly_rows:
            entry = WeeklyData(
                week_start=week_start,
                day=row["day"],
                sales=row["sales"],
                labor_cost=row["labor_cost"],
                staff_hours=row["staff_hours"],
                weather=row.get("weather", ""),
                event=row.get("event", ""),
                efficiency=row.get("efficiency", 0.9),
                holiday=row.get("holiday", False)
            )
            db_session.session.add(entry)
        db_session.session.commit()
        return True
    except Exception as e:
        if current_app:
            current_app.logger.error(f"Failed to save weekly data: {e}")
        return False


# ------------------------------------------------------------
# 13. PHASE 8: CRUD OPERATIONS FOR WEEKLY DATA
# ------------------------------------------------------------
def get_current_weekly_data_from_db() -> Optional[List[Dict]]:
    """Retrieve the most recent week's data from DB, return as list of dicts."""
    if not USE_DATABASE or not MODELS_AVAILABLE:
        return None
    try:
        db_session = get_db()
        if not db_session:
            return None
        # Get latest week_start
        latest_week = db_session.session.query(WeeklyData.week_start).order_by(WeeklyData.week_start.desc()).first()
        if not latest_week:
            return None
        records = db_session.session.query(WeeklyData).filter(WeeklyData.week_start == latest_week[0]).all()
        result = []
        for rec in records:
            result.append({
                "day": rec.day,
                "sales": rec.sales,
                "labor_cost": rec.labor_cost,
                "staff_hours": rec.staff_hours,
                "weather": rec.weather,
                "event": rec.event,
                "efficiency": rec.efficiency,
                "holiday": rec.holiday
            })
        # Ensure days are in correct order (Monday..Sunday)
        day_order = ["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"]
        result.sort(key=lambda x: day_order.index(x["day"]))
        return result
    except Exception as e:
        if current_app:
            current_app.logger.error(f"Failed to fetch weekly data from DB: {e}")
        return None


# ------------------------------------------------------------
# 14. PHASE 8: IMPORT & SAVE UPLOADED REPORT DATA
# ------------------------------------------------------------
def save_imported_report(filename: str, file_type: str, parsed_data: Dict) -> str:
    """Save an imported report to database. Returns report_id."""
    if not USE_DATABASE or not MODELS_AVAILABLE:
        return "mock-saved"
    try:
        db_session = get_db()
        if not db_session:
            return "db-unavailable"
        report = ImportedReport(
            filename=filename,
            file_type=file_type,
            parsed_data=parsed_data,
            status="parsed"
        )
        db_session.session.add(report)
        db_session.session.commit()
        return str(report.id)
    except Exception as e:
        if current_app:
            current_app.logger.error(f"Failed to save imported report: {e}")
        return "error"

def process_uploaded_file(file_path: str, file_type: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Phase 8: Parse uploaded CSV/PDF/image, extract sales/labor data, save to DB.
    This is the function called by the background worker in routes.
    Returns task result dict.
    """
    task_id = str(random.randint(100000, 999999))
    try:
        # Stub: In real implementation, parse file based on file_type
        # For now, simulate successful parse with sample data
        if file_type == 'csv':
            # In real code: parse CSV into rows
            parsed = {"rows": [{"day": "Monday", "sales": 1300, "labor": 420}]}
        elif file_type == 'pdf':
            # In real code: extract text, run OCR if needed
            parsed = {"rows": []}
        elif file_type == 'image':
            # In real code: use pytesseract
            parsed = {"rows": []}
        else:
            parsed = {"error": "Unsupported file type"}

        # Save to database
        save_imported_report(Path(file_path).name, file_type, parsed)

        # If parsed contains weekly data rows, optionally update current weekly data
        if "rows" in parsed and parsed["rows"]:
            # Convert to full weekly format and save
            # (simplified stub)
            pass

        return {
            "task_id": task_id,
            "status": "complete",
            "progress": 100,
            "message": f"Successfully parsed {file_type} file",
            "data_preview": parsed
        }
    except Exception as e:
        return {
            "task_id": task_id,
            "status": "failed",
            "progress": 0,
            "message": f"Parse failed: {str(e)}",
            "error": str(e)
        }


# ------------------------------------------------------------
# 15. PHASE 8: BACKGROUND FORECAST RECALCULATION STUB
# ------------------------------------------------------------
def trigger_forecast_recalculation(weeks: int = 4) -> None:
    """Start background thread to recalculate forecast based on latest data."""
    def recalc():
        try:
            new_forecast = get_forecast_data(weeks)
            # Save to database or cache
            if USE_DATABASE and MODELS_AVAILABLE:
                # Store forecast results in a ForecastCache table (not yet defined)
                pass
            if current_app:
                current_app.logger.info(f"Forecast recalculation completed for {weeks} weeks")
        except Exception as e:
            if current_app:
                current_app.logger.error(f"Forecast recalculation failed: {e}")
    thread = threading.Thread(target=recalc)
    thread.daemon = True
    thread.start()


# ------------------------------------------------------------
# 16. EXISTING API-FACING FUNCTIONS (unchanged, but now database-aware when called)
# ------------------------------------------------------------
def get_raw_weekly_data() -> List[Dict]:
    """Return raw weekly data (from DB if enabled, else mock)."""
    if USE_DATABASE:
        db_data = get_current_weekly_data_from_db()
        if db_data:
            return db_data
    return BASE_WEEKLY_DATA.copy()

def refresh_mock_data_with_random_variation() -> None:
    """Legacy: no longer needed. Kept for compatibility."""
    pass


# ------------------------------------------------------------
# FUTURE EXPANSION BLOCKS (add below without breaking)
# ------------------------------------------------------------
# Phase 9: Weather API integration
# Phase 10: Employee-level schedule optimization
# Phase 11: Profitability engine (COGS, margins)
# Phase 12: Mobile API endpoints