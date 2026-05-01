"""
TABLE STACK v4 – ENHANCED DASHBOARD SERVICE LAYER
--------------------------------------------------------------------------------
Purpose: All business logic, calculations, and data preparation for the dashboard.
Rules: Routes stay thin – this file does the heavy lifting.

Structure:
1. Mock data (enhanced with weather, events, efficiency)
2. Helper functions (currency, percentage, calculations)
3. Weekly snapshot builder (display‑ready)
4. Summary totals & metrics (with target labor support)
5. Forecasting engine (linear regression + seasonality)
6. Labor optimizer (schedule recommendations)
7. AI recommendations generator
8. Insight cards (best day, risk day, etc.)
9. Main context builder (combines everything)

Ready for 10k+ lines: add new sections below without breaking existing ones.
--------------------------------------------------------------------------------
"""

import math
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

# ------------------------------------------------------------
# 1. MOCK DATA – BASE WEEKLY DATA (enhanced)
# ------------------------------------------------------------
# This will eventually come from database / OCR / imported files.
BASE_WEEKLY_DATA = [
    {
        "day": "Monday",
        "sales": 1250.00,
        "labor_cost": 410.00,
        "staff_hours": 22,
        "weather": "Sunny",
        "event": "None",
        "efficiency": 0.92,          # sales per labor hour relative to ideal
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

# Historical sales data for forecasting (last 8 weeks)
# Used to detect trend and seasonality
HISTORICAL_WEEKLY_SALES = [
    11200, 11800, 12100, 12450, 13000, 12850, 13200, 13450
]  # weekly totals

# ------------------------------------------------------------
# 2. HELPER FUNCTIONS
# ------------------------------------------------------------
def calculate_labor_percentage(sales: float, labor_cost: float) -> float:
    """Return labor % = (labor_cost / sales) * 100. Returns 0 if sales <= 0."""
    if sales <= 0:
        return 0.0
    return (labor_cost / sales) * 100.0

def format_currency(amount: float) -> str:
    """Convert float to USD string with no decimals."""
    return f"${amount:,.0f}"

def format_percentage(value: float) -> str:
    """Format as percentage with 1 decimal."""
    return f"{value:.1f}%"

def parse_currency_string(value: str) -> float:
    """Convert '$1,234' to 1234.0."""
    return float(value.replace('$', '').replace(',', ''))

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    return numerator / denominator if denominator != 0 else default

# ------------------------------------------------------------
# 3. WEEKLY SNAPSHOT (display‑ready)
# ------------------------------------------------------------
def build_weekly_snapshot(weekly_data: List[Dict]) -> List[Dict[str, Any]]:
    """
    Transforms raw weekly data into display‑ready rows.
    Adds labor_percent, efficiency percent, formatted sales/labor.
    """
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
            # Keep raw values for calculations if needed later
            "_raw_sales": row["sales"],
            "_raw_labor": row["labor_cost"]
        })
    return snapshot

# ------------------------------------------------------------
# 4. SUMMARY TOTALS & METRIC CARDS
# ------------------------------------------------------------
def calculate_summary_totals(weekly_data: List[Dict]) -> Dict[str, float]:
    """Aggregate totals for the week."""
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
    """Return status, change text, description based on target."""
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
    """Metric cards for the top of dashboard."""
    labor_status = get_labor_status(totals["labor_percentage"], target_labor)
    return [
        {
            "label": "Total Sales",
            "value": format_currency(totals["total_sales"]),
            "change": "This week",
            "status": "neutral",
            "description": "Gross revenue"
        },
        {
            "label": "Labor Cost",
            "value": format_currency(totals["total_labor_cost"]),
            "change": "Total spend",
            "status": "neutral",
            "description": "Wages + taxes"
        },
        {
            "label": "Labor %",
            "value": format_percentage(totals["labor_percentage"]),
            "change": labor_status["change"],
            "status": labor_status["status"],
            "description": labor_status["description"]
        },
        {
            "label": "Staff Hours",
            "value": str(int(totals["total_staff_hours"])),
            "change": "Scheduled",
            "status": "neutral",
            "description": "Total hours worked"
        },
        {
            "label": "Sales / Labor Hour",
            "value": format_currency(totals["sales_per_labor_hour"]),
            "change": "Productivity",
            "status": "neutral",
            "description": "Revenue per labor hour"
        }
    ]

# ------------------------------------------------------------
# 5. FORECASTING ENGINE (linear trend + weekly seasonality)
# ------------------------------------------------------------
def get_forecast_data(weeks_ahead: int = 2) -> List[Dict[str, str]]:
    """
    Predict future sales and labor using linear regression on historical weekly totals.
    Then distribute to daily using average weekday weights.
    """
    # 1. Linear trend on historical weekly sales totals
    n = len(HISTORICAL_WEEKLY_SALES)
    if n < 2:
        # fallback simple growth
        forecast_weeks = [HISTORICAL_WEEKLY_SALES[-1] * (1 + 0.02 * i) for i in range(1, weeks_ahead+1)]
    else:
        # Linear regression (least squares)
        x = list(range(n))
        y = HISTORICAL_WEEKLY_SALES
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        numerator = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n))
        denominator = sum((x[i] - mean_x) ** 2 for i in range(n))
        slope = numerator / denominator if denominator != 0 else 0
        intercept = mean_y - slope * mean_x
        forecast_weeks = [intercept + slope * (n + i) for i in range(1, weeks_ahead+1)]

    # 2. Get average daily sales weights from current week
    weekly_sales_current = sum(row["sales"] for row in BASE_WEEKLY_DATA)
    daily_weights = [row["sales"] / weekly_sales_current for row in BASE_WEEKLY_DATA]
    days_order = [row["day"] for row in BASE_WEEKLY_DATA]

    # 3. Average labor % from current week (ignore zero)
    labor_percentages = [calculate_labor_percentage(row["sales"], row["labor_cost"]) for row in BASE_WEEKLY_DATA]
    avg_labor_percent = sum(labor_percentages) / len(labor_percentages)

    forecast = []
    for w, week_total in enumerate(forecast_weeks, start=1):
        week_sales = max(week_total, 0)
        # Daily distribution (simplified: same weights each week)
        for day_idx, day in enumerate(days_order):
            daily_sales = week_sales * daily_weights[day_idx]
            daily_labor = daily_sales * (avg_labor_percent / 100)
            forecast.append({
                "week": f"Week +{w} - {day}",
                "sales": format_currency(daily_sales),
                "labor": format_currency(daily_labor),
                "labor_percent": format_percentage(calculate_labor_percentage(daily_sales, daily_labor))
            })
        # Add a separator or just one line per week? Better to show weekly summary.
    # Instead of daily list, return weekly summary (cleaner)
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
# 6. LABOR OPTIMIZER (schedule suggestions)
# ------------------------------------------------------------
def optimize_labor(target_labor_percent: float, weekly_data: Optional[List[Dict]] = None) -> Dict[str, Any]:
    """
    For each day where labor % > target, suggest reducing hours.
    Assumes average wage $20/hour.
    """
    data = weekly_data if weekly_data is not None else BASE_WEEKLY_DATA
    suggestions = []
    for day in data:
        current_lp = calculate_labor_percentage(day["sales"], day["labor_cost"])
        if current_lp <= target_labor_percent:
            continue
        # Calculate ideal labor cost to hit target
        ideal_labor = day["sales"] * (target_labor_percent / 100)
        labor_reduction = day["labor_cost"] - ideal_labor
        # Assume $20 per hour wage (including taxes/benefits)
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
# 7. AI RECOMMENDATIONS (data‑driven insights)
# ------------------------------------------------------------
def generate_ai_recommendations(weekly_data: List[Dict], totals: Dict) -> List[Dict[str, str]]:
    """Generate actionable insights based on patterns."""
    recommendations = []

    # Worst labor day
    worst_day = max(weekly_data, key=lambda x: calculate_labor_percentage(x["sales"], x["labor_cost"]))
    worst_lp = calculate_labor_percentage(worst_day["sales"], worst_day["labor_cost"])
    if worst_lp > 27:
        recommendations.append({
            "title": "Reduce Overstaffing",
            "detail": f"{worst_day['day']} labor reached {format_percentage(worst_lp)}. Cut 2-3 hours.",
            "impact": f"Save ~${worst_day['labor_cost'] * 0.1:.0f} and lower labor % by ~3 points."
        })

    # Best sales day – promote similar events
    best_day = max(weekly_data, key=lambda x: x["sales"])
    recommendations.append({
        "title": "Capitalize on Peak Days",
        "detail": f"{best_day['day']} generated {format_currency(best_day['sales'])}. Run specials or events.",
        "impact": "Potential +10% sales lift with minimal labor increase."
    })

    # Weather impact
    rainy_days = [d for d in weekly_data if d["weather"].lower() == "rainy"]
    if rainy_days:
        rainy = rainy_days[0]
        rainy_lp = calculate_labor_percentage(rainy["sales"], rainy["labor_cost"])
        recommendations.append({
            "title": "Weather‑Based Staffing",
            "detail": f"Rainy days like {rainy['day']} hit {format_percentage(rainy_lp)} labor. Reduce FOH by 1-2.",
            "impact": "Save ~$80 on slow shifts."
        })

    # Efficiency insight (sales per labor hour)
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

    # Ensure at least 3 recommendations
    if len(recommendations) < 3:
        recommendations.append({
            "title": "Forecast Opportunity",
            "detail": "Next week's forecast shows +3% sales growth. Adjust labor by +2%.",
            "impact": "Capture additional revenue without overspending."
        })
    return recommendations[:4]  # Limit to 4 cards

# ------------------------------------------------------------
# 8. OPERATIONAL INSIGHT CARDS (simple stats)
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
        {
            "title": "Best Sales Day",
            "value": best["day"],
            "details": f"{best['day']} generated {format_currency(best['sales'])}."
        },
        {
            "title": "Highest Labor Risk",
            "value": risk["day"],
            "details": f"{risk['day']} reached {format_percentage(risk_percent)} labor."
        },
        {
            "title": "Efficiency Leader",
            "value": most_efficient["day"],
            "details": f"{most_efficient['day']} achieved {most_efficient['efficiency']*100:.0f}% sales per hour efficiency."
        },
        {
            "title": "Staffing Intelligence",
            "value": "AI Ready",
            "details": "Future: compare sales, weather, events & schedule coverage."
        }
    ]

# ------------------------------------------------------------
# 9. MAIN CONTEXT BUILDER (entry point for routes)
# ------------------------------------------------------------
def get_dashboard_context(target_labor_percent: float = 25.0) -> Dict[str, Any]:
    """
    Build the full dashboard context consumed by dashboard.html.
    Accepts target_labor_percent to adjust metrics status (but not the data itself).
    """
    weekly_data = BASE_WEEKLY_DATA.copy()
    totals = calculate_summary_totals(weekly_data)
    # For status calculations, we use the provided target
    metrics = build_summary_metrics(totals, target_labor_percent)
    # Override the labor % status with the target-sensitive version (already done inside build_summary_metrics)

    # Generate recommendations using original data (target not needed for AI)
    recommendations = generate_ai_recommendations(weekly_data, totals)

    # Forecast preview (2 weeks)
    forecast_preview = get_forecast_data(2)

    # Weekly snapshot (display)
    weekly_snapshot = build_weekly_snapshot(weekly_data)

    # Insight cards
    insight_cards = build_operational_insights(weekly_data)

    # Future modules list
    future_modules = [
        "OCR Sales Import (Phase 8)",
        "Weather API Integration (Phase 9)",
        "Real Staff Scheduling (Phase 10)",
        "Profitability Engine (Phase 11)",
        "Mobile App Companion (Phase 12)",
        "Live POS Integration (Phase 13)"
    ]

    return {
        "page": {
            "title": "Table Stack v4 Intelligence Suite",
            "subtitle": "Real‑time sales, labor, forecast & AI recommendations."
        },
        "summary_metrics": metrics,
        "weekly_snapshot": weekly_snapshot,
        "insight_cards": insight_cards,
        "recommendations": recommendations,
        "forecast_preview": forecast_preview,
        "future_modules": future_modules
    }

# ------------------------------------------------------------
# 10. ADDITIONAL API‑FACING FUNCTIONS (for routes)
# ------------------------------------------------------------
def get_raw_weekly_data() -> List[Dict]:
    """Return raw weekly data for potential export or further processing."""
    return BASE_WEEKLY_DATA.copy()

def refresh_mock_data_with_random_variation() -> None:
    """
    Future: simulate daily data changes. For now, placeholder.
    In production, this would query database.
    """
    pass

# ------------------------------------------------------------
# FUTURE EXPANSION BLOCKS (add below without breaking)
# ------------------------------------------------------------
# Example: Database connector to replace mock data
# Example: ML model loader for more accurate forecasts
# Example: OCR result parser