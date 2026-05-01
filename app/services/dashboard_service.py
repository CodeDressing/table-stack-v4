"""
Dashboard Service Layer
-----------------------

This module prepares all data needed by the main dashboard.

Important rule:
Routes should stay small.
Business logic, calculations, and dashboard data preparation belong here.

Future upgrades can safely expand this file or split it into smaller service files
without damaging the Flask route structure.
"""


def get_mock_weekly_shift_data():
    """
    Temporary structured mock data.

    Later, this data will come from:
    - database tables
    - uploaded reports
    - OCR extraction
    - sales imports
    - scheduling records

    For now, this gives us realistic structured data to calculate from.
    """

    return [
        {
            "day": "Monday",
            "sales": 1250.00,
            "labor_cost": 410.00,
            "staff_hours": 22,
        },
        {
            "day": "Tuesday",
            "sales": 1420.00,
            "labor_cost": 390.00,
            "staff_hours": 21,
        },
        {
            "day": "Wednesday",
            "sales": 1675.00,
            "labor_cost": 430.00,
            "staff_hours": 23,
        },
        {
            "day": "Thursday",
            "sales": 1980.00,
            "labor_cost": 505.00,
            "staff_hours": 27,
        },
        {
            "day": "Friday",
            "sales": 2850.00,
            "labor_cost": 690.00,
            "staff_hours": 36,
        },
        {
            "day": "Saturday",
            "sales": 2375.00,
            "labor_cost": 640.00,
            "staff_hours": 34,
        },
        {
            "day": "Sunday",
            "sales": 900.00,
            "labor_cost": 215.00,
            "staff_hours": 11,
        },
    ]


def calculate_labor_percentage(sales, labor_cost):
    """
    Calculate labor percentage.

    Formula:
    labor percentage = labor cost / sales * 100

    If sales are zero, return 0 to prevent division errors.
    """

    if sales <= 0:
        return 0

    return (labor_cost / sales) * 100


def format_currency(amount):
    """
    Convert a number into a clean dollar format.
    Example:
    12450.0 -> $12,450
    """

    return f"${amount:,.0f}"


def format_percentage(value):
    """
    Convert a number into a percentage string.
    Example:
    26.345 -> 26.3%
    """

    return f"{value:.1f}%"


def build_weekly_snapshot(weekly_data):
    """
    Build table-ready weekly snapshot rows.

    This transforms raw numeric data into display-ready values while still
    keeping calculations centralized in Python.
    """

    snapshot_rows = []

    for row in weekly_data:
        sales = row["sales"]
        labor_cost = row["labor_cost"]
        labor_percentage = calculate_labor_percentage(sales, labor_cost)

        snapshot_rows.append(
            {
                "day": row["day"],
                "sales": format_currency(sales),
                "labor": format_currency(labor_cost),
                "labor_percent": format_percentage(labor_percentage),
                "staff_hours": row["staff_hours"],
            }
        )

    return snapshot_rows


def calculate_summary_totals(weekly_data):
    """
    Calculate high-level dashboard totals from weekly data.
    """

    total_sales = sum(row["sales"] for row in weekly_data)
    total_labor_cost = sum(row["labor_cost"] for row in weekly_data)
    total_staff_hours = sum(row["staff_hours"] for row in weekly_data)
    labor_percentage = calculate_labor_percentage(total_sales, total_labor_cost)

    return {
        "total_sales": total_sales,
        "total_labor_cost": total_labor_cost,
        "total_staff_hours": total_staff_hours,
        "labor_percentage": labor_percentage,
    }


def get_labor_status(labor_percentage, target_percentage=25):
    """
    Determine dashboard warning state based on labor percentage.
    """

    if labor_percentage <= target_percentage:
        return {
            "status": "positive",
            "change": "On target",
            "description": "Labor is at or below target",
        }

    if labor_percentage <= target_percentage + 3:
        return {
            "status": "warning",
            "change": f"Target: {target_percentage}%",
            "description": "Slightly above target",
        }

    return {
        "status": "danger",
        "change": f"+{labor_percentage - target_percentage:.1f}%",
        "description": "Labor is significantly above target",
    }


def build_summary_metrics(totals):
    """
    Build the main metric cards shown at the top of the dashboard.
    """

    labor_status = get_labor_status(totals["labor_percentage"])

    return [
        {
            "label": "Total Sales",
            "value": format_currency(totals["total_sales"]),
            "change": "Calculated",
            "status": "neutral",
            "description": "Total sales from weekly data",
        },
        {
            "label": "Labor Cost",
            "value": format_currency(totals["total_labor_cost"]),
            "change": "Calculated",
            "status": "neutral",
            "description": "Total labor spend",
        },
        {
            "label": "Labor %",
            "value": format_percentage(totals["labor_percentage"]),
            "change": labor_status["change"],
            "status": labor_status["status"],
            "description": labor_status["description"],
        },
        {
            "label": "Staff Hours",
            "value": str(totals["total_staff_hours"]),
            "change": "Calculated",
            "status": "neutral",
            "description": "Total scheduled hours",
        },
    ]


def find_best_sales_day(weekly_data):
    """
    Find the day with the highest sales.
    """

    return max(weekly_data, key=lambda row: row["sales"])


def find_highest_labor_risk_day(weekly_data):
    """
    Find the day with the highest labor percentage.
    """

    return max(
        weekly_data,
        key=lambda row: calculate_labor_percentage(row["sales"], row["labor_cost"])
    )


def build_operational_insights(weekly_data):
    """
    Build simple operational insights from weekly data.

    These are early intelligence cards.
    Later, this can evolve into a real recommendation engine.
    """

    best_sales_day = find_best_sales_day(weekly_data)
    labor_risk_day = find_highest_labor_risk_day(weekly_data)

    labor_risk_percent = calculate_labor_percentage(
        labor_risk_day["sales"],
        labor_risk_day["labor_cost"]
    )

    return [
        {
            "title": "Best Sales Day",
            "value": best_sales_day["day"],
            "details": (
                f"{best_sales_day['day']} generated "
                f"{format_currency(best_sales_day['sales'])} in sales."
            ),
        },
        {
            "title": "Highest Labor Risk",
            "value": labor_risk_day["day"],
            "details": (
                f"{labor_risk_day['day']} reached "
                f"{format_percentage(labor_risk_percent)} labor."
            ),
        },
        {
            "title": "Staffing Intelligence",
            "value": "Coming Soon",
            "details": (
                "Future versions will compare staff hours, sales volume, "
                "weather, events, and schedule coverage."
            ),
        },
    ]


def get_dashboard_context():
    """
    Build the full dashboard context consumed by dashboard.html.
    """

    weekly_data = get_mock_weekly_shift_data()
    totals = calculate_summary_totals(weekly_data)

    return {
        "page": {
            "title": "Table Stack v4 Dashboard",
            "subtitle": "Restaurant intelligence system for sales, labor, and staffing insights.",
        },
        "summary_metrics": build_summary_metrics(totals),
        "weekly_snapshot": build_weekly_snapshot(weekly_data),
        "insight_cards": build_operational_insights(weekly_data),
        "future_modules": [
            "Sales Forecasting Engine",
            "Labor Optimization Engine",
            "OCR Sales Report Importer",
            "Staff Performance Analyzer",
            "Schedule Recommendation System",
        ],
    }