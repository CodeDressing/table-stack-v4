"""
TABLE STACK v4 – APPLICATION FACTORY (PHASE 8 UPGRADE)
--------------------------------------------------------------------------------
Purpose: Central app creation, blueprint registration, extension setup, CLI commands.
Phase 8 Additions:
- SQLAlchemy database integration (flask_sqlalchemy)
- Background scheduler (APScheduler) for forecast refresh & housekeeping
- Import service initialization for OCR/task queue
- Environment-aware config with database URI from .env
- Better error handling for missing templates

Structure:
1. Imports & configuration
2. create_app() – main factory with DB init
3. setup_logging()
4. register_blueprints() (existing + sales, schedule already included)
5. register_extensions() – DB, scheduler, CORS
6. register_cli() – custom commands (seed, routes, db init)
7. register_error_handlers() – global error pages
8. Background job configuration (forecast refresh)

Ready for 10k+ lines: add new blueprints, extensions, or CLI commands below.
--------------------------------------------------------------------------------
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

from config import Config, get_config

# ------------------------------------------------------------------
# 1. GLOBALS FOR EXTENSIONS (will be initialized in register_extensions)
# ------------------------------------------------------------------
db = None  # SQLAlchemy instance (set later if available)
migrate = None
scheduler = None


def create_app(config_class=None):
    """Application factory – now with database and scheduler support."""
    # Load config from environment if not provided
    if config_class is None:
        config_class = get_config()

    app = Flask(__name__)
    app.config.from_object(config_class)

    # ------------------------------------------------------------------
    # 1.1 Ensure required directories exist
    # ------------------------------------------------------------------
    Path(app.config.get('UPLOAD_FOLDER', 'uploads')).mkdir(parents=True, exist_ok=True)
    Path(app.config.get('LOG_DIR', 'logs')).mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # 1.2 CORS (optional)
    # ------------------------------------------------------------------
    if app.config.get('CORS_ENABLED', False):
        CORS(app)

    # ------------------------------------------------------------------
    # 1.3 Logging
    # ------------------------------------------------------------------
    setup_logging(app)

    # ------------------------------------------------------------------
    # 1.4 Extensions (DB, scheduler, etc.)
    # ------------------------------------------------------------------
    register_extensions(app)
    register_blueprints(app)
    register_cli(app)
    register_error_handlers(app)
    register_background_jobs(app)

    return app


def setup_logging(app):
    """Configure file and console logging – unchanged but ensures log dir exists."""
    if not app.debug and not app.testing:
        log_dir = Path(app.config.get('LOG_DIR', 'logs'))
        log_file = log_dir / 'tablestack.log'

        file_handler = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5
        )
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.WARNING)
        app.logger.addHandler(console_handler)

        app.logger.setLevel(logging.INFO)
        app.logger.info('Table Stack v4 Phase 8 startup')


def register_extensions(app):
    """
    Phase 8: Initialize SQLAlchemy, Flask-Migrate, APScheduler, and caching stubs.
    Gracefully handle missing packages.
    """
    global db, migrate, scheduler

    # ------------------------------------------------------------------
    # 2.1 Database (SQLAlchemy)
    # ------------------------------------------------------------------
    try:
        from flask_sqlalchemy import SQLAlchemy
        from flask_migrate import Migrate

        db = SQLAlchemy()
        db.init_app(app)
        migrate = Migrate(app, db)
        app.logger.info("SQLAlchemy and Migrate initialized")
    except ImportError as e:
        app.logger.warning(f"Database extensions not installed: {e}")
        db = None
        migrate = None

    # ------------------------------------------------------------------
    # 2.2 Background Scheduler (APScheduler) for forecast refresh
    # ------------------------------------------------------------------
    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler()

        def scheduled_forecast_refresh():
            """Job that calls forecast service to pre‑compute forecasts."""
            with app.app_context():
                try:
                    from app.services.dashboard_service import get_forecast_data
                    get_forecast_data(weeks_ahead=4)  # warm cache
                    app.logger.info("Scheduled forecast refresh completed")
                except Exception as e:
                    app.logger.error(f"Forecast refresh job failed: {e}")

        # Run every 6 hours
        scheduler.add_job(
            func=scheduled_forecast_refresh,
            trigger="interval",
            hours=app.config.get('SCHEDULER_FORECAST_INTERVAL_HOURS', 6),
            id="forecast_refresh",
            replace_existing=True
        )
        scheduler.start()
        app.logger.info("APScheduler started with forecast refresh job")
    except ImportError:
        app.logger.info("APScheduler not installed – background jobs disabled")
        scheduler = None

    # ------------------------------------------------------------------
    # 2.3 Cache (Redis stub – Phase 9)
    # ------------------------------------------------------------------
    try:
        from flask_caching import Cache
        cache = Cache(app, config={'CACHE_TYPE': 'SimpleCache'})
        app.extensions['cache'] = cache
        app.logger.info("Flask-Caching initialized")
    except ImportError:
        app.logger.info("Flask-Caching not installed – caching disabled")

    # ------------------------------------------------------------------
    # 2.4 Store extensions on app for easy access
    # ------------------------------------------------------------------
    app.db = db
    app.scheduler = scheduler


def register_blueprints(app):
    """
    Register all route blueprints. Missing modules are gracefully skipped.
    Phase 8: ensure sales and schedule are loaded, add API versioning prefix optionally.
    """
    # Core dashboard
    try:
        from app.routes.dashboard_routes import dashboard_bp
        app.register_blueprint(dashboard_bp)
        app.logger.info("Registered dashboard blueprint")
    except ImportError as e:
        app.logger.error(f"Dashboard blueprint failed to load: {e}")

    # Schedule (staffing)
    try:
        from app.routes.schedule_routes import schedule_bp
        app.register_blueprint(schedule_bp)
        app.logger.info("Registered schedule blueprint")
    except ImportError as e:
        app.logger.error(f"Schedule blueprint not loaded: {e}")

    # Sales module (Phase 8)
    try:
        from app.routes.sales_routes import sales_bp
        app.register_blueprint(sales_bp)
        app.logger.info("Registered sales blueprint")
    except ImportError as e:
        app.logger.info(f"Sales module not loaded: {e}")

    # Future optional modules (safe import)
    future_modules = [
        ('labor', 'labor_routes', 'labor_bp'),
        ('staffing', 'staffing_routes', 'staffing_bp'),
        ('reports', 'reports_routes', 'reports_bp'),
        ('forecasting', 'forecasting_routes', 'forecasting_bp'),
    ]
    for module_name, module_file, bp_var in future_modules:
        try:
            module = __import__(
                f'app.routes.{module_file}',
                fromlist=[bp_var]
            )
            blueprint = getattr(module, bp_var)
            app.register_blueprint(blueprint)
            app.logger.info(f"Registered {module_name} blueprint")
        except (ImportError, AttributeError) as e:
            app.logger.info(f"{module_name.capitalize()} module not loaded: {e}")


def register_cli(app):
    """Custom Flask CLI commands for data management and DB operations."""
    @app.cli.command("seed-mock-data")
    def seed_mock_data():
        """Seed database with mock weekly data and employees."""
        print("Seeding mock data...")
        if app.db is None:
            print("Database not available. Install flask_sqlalchemy and set USE_DATABASE=True")
            return
        try:
            from app.services.dashboard_service import BASE_WEEKLY_DATA
            from app.services.employee_service import get_all_employees
            # Import model (assumes model exists)
            from app.services.dashboard_service import WeeklyData
            from datetime import datetime, timedelta

            week_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            # Clear old data for this week
            app.db.session.query(WeeklyData).filter(WeeklyData.week_start == week_start).delete()
            for row in BASE_WEEKLY_DATA:
                entry = WeeklyData(
                    week_start=week_start,
                    day=row["day"],
                    sales=row["sales"],
                    labor_cost=row["labor_cost"],
                    staff_hours=row["staff_hours"],
                    weather=row["weather"],
                    event=row["event"],
                    efficiency=row["efficiency"],
                    holiday=row.get("holiday", False)
                )
                app.db.session.add(entry)
            app.db.session.commit()
            print(f"Seeded {len(BASE_WEEKLY_DATA)} days of mock data.")
        except Exception as e:
            print(f"Seeding failed: {e}")

    @app.cli.command("run-forecast")
    def run_forecast():
        """Generate and store forecast data."""
        print("Running forecast generation...")
        try:
            from app.services.dashboard_service import get_forecast_data
            forecast = get_forecast_data(weeks_ahead=4)
            print(f"Forecast generated for {len(forecast)} weeks.")
        except Exception as e:
            print(f"Forecast error: {e}")

    @app.cli.command("list-routes")
    def list_routes():
        """Print all registered routes (for debugging)."""
        import urllib
        output = []
        for rule in app.url_map.iter_rules():
            methods = ','.join(rule.methods)
            line = urllib.parse.unquote(f"{rule.endpoint:40s} {methods:20s} {rule}")
            output.append(line)
        for line in sorted(output):
            print(line)

    @app.cli.command("db-init")
    def db_init():
        """Create database tables (if using SQLAlchemy)."""
        if app.db is None:
            print("SQLAlchemy not installed.")
            return
        app.db.create_all()
        print("Database tables created.")


def register_error_handlers(app):
    """Global error pages for HTTP errors – enhanced with JSON fallback for APIs."""
    @app.errorhandler(404)
    def not_found_error(error):
        if request.path.startswith('/api/'):
            return jsonify({"error": "API endpoint not found"}), 404
        # Try to render custom 404 template, fallback to simple string
        try:
            return render_template('404.html'), 404
        except Exception:
            return "<h1>404 Not Found</h1><p>The page you requested does not exist.</p>", 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Server Error: {error}")
        if request.path.startswith('/api/'):
            return jsonify({"error": "Internal server error"}), 500
        try:
            return render_template('500.html'), 500
        except Exception:
            return "<h1>500 Internal Server Error</h1><p>Something went wrong.</p>", 500


def register_background_jobs(app):
    """Additional background jobs (e.g., daily cleanup, report generation)."""
    if scheduler is None:
        return

    def daily_cleanup():
        """Remove old uploaded files and stale tasks."""
        with app.app_context():
            try:
                # Clean files older than 7 days in uploads folder
                upload_dir = Path(app.config.get('UPLOAD_FOLDER', 'uploads'))
                if upload_dir.exists():
                    cutoff = datetime.now().timestamp() - 7 * 86400
                    for f in upload_dir.iterdir():
                        if f.is_file() and f.stat().st_mtime < cutoff:
                            f.unlink()
                            app.logger.debug(f"Removed old uploaded file: {f.name}")
                # Also clear in‑memory task dict if needed
                app.logger.info("Daily cleanup completed")
            except Exception as e:
                app.logger.error(f"Cleanup job failed: {e}")

    scheduler.add_job(
        func=daily_cleanup,
        trigger="cron",
        hour=app.config.get('SCHEDULER_CLEANUP_HOUR', 3),
        minute=0,
        id="daily_cleanup",
        replace_existing=True
    )
    app.logger.info("Registered daily cleanup job")