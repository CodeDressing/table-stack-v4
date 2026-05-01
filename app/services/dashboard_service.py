def get_dashboard_context():
    """
    Builds all dashboard data for the main Restaurant Intelligence Dashboard.

    This file is intentionally designed as a service layer so the route does not
    become bloated as the project grows.

    Future upgrades can add:
    - real database queries
    - labor calculations
    - sales trend analysis
    - staffing efficiency scoring
    - forecasting
    - OCR-imported report summaries
    - AI recommendations
    """

    return {
        "page": {
            "title": "Table Stack v4 Dashboard",
            "subtitle": "Restaurant intelligence system for sales, labor, and staffing insights.",
        },

        "summary_metrics": [
            {
                "label": "Total Sales",
                "value": "$12,450",
                "change": "+8.4%",
                "status": "positive",
                "description": "Compared to last week",
            },
            {
                "label": "Labor Cost",
                "value": "$3,280",
                "change": "-2.1%",
                "status": "positive",
                "description": "Lower labor spend",
            },
            {
                "label": "Labor %",
                "value": "26.3%",
                "change": "Target: 25%",
                "status": "warning",
                "description": "Slightly above target",
            },
            {
                "label": "Staff Hours",
                "value": "164",
                "change": "+12 hrs",
                "status": "neutral",
                "description": "Scheduled this week",
            },
        ],

        "insight_cards": [
            {
                "title": "Best Performing Shift",
                "value": "Friday Dinner",
                "details": "Highest sales volume and strongest labor efficiency.",
            },
            {
                "title": "Labor Risk",
                "value": "Saturday Dinner",
                "details": "Projected labor percentage may exceed target.",
            },
            {
                "title": "Staffing Opportunity",
                "value": "Sunday Brunch",
                "details": "Sales are strong, but staffing may be slightly light.",
            },
        ],

        "weekly_snapshot": [
            {"day": "Monday", "sales": "$1,250", "labor": "$410", "labor_percent": "32.8%"},
            {"day": "Tuesday", "sales": "$1,420", "labor": "$390", "labor_percent": "27.5%"},
            {"day": "Wednesday", "sales": "$1,675", "labor": "$430", "labor_percent": "25.7%"},
            {"day": "Thursday", "sales": "$1,980", "labor": "$505", "labor_percent": "25.5%"},
            {"day": "Friday", "sales": "$2,850", "labor": "$690", "labor_percent": "24.2%"},
            {"day": "Saturday", "sales": "$2,375", "labor": "$640", "labor_percent": "26.9%"},
            {"day": "Sunday", "sales": "$900", "labor": "$215", "labor_percent": "23.9%"},
        ],

        "future_modules": [
            "Sales Forecasting Engine",
            "Labor Optimization Engine",
            "OCR Sales Report Importer",
            "Staff Performance Analyzer",
            "Schedule Recommendation System",
        ],
    }