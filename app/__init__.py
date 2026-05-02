"""
TABLE STACK v4 – APPLICATION FACTORY
------------------------------------------------------------
Central Flask app setup.

Includes:
- Config loading
- Logging
- Flask-Login setup
- Optional database / scheduler / cache setup
- Blueprint registration
- Secure headers
- CLI helpers
- Global error handlers
------------------------------------------------------------
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from datetime import datetime

from flask import Flask, render_template, jsonify, request, redirect, url_for
from flask_cors import CORS

from config import get_config


db = None
migrate = None
scheduler = None


def create_app(config_class=None):
    """Create and configure the Flask app."""

    if config_class is None:
        config_class = get_config()

    app = Flask(__name__)
    app.config.from_object(config_class)

    ensure_directories(app)
    setup_logging(app)
    register_extensions(app)
    register_auth(app)
    register_blueprints(app)
    register_cli(app)
    register_error_handlers(app)
    register_security_headers(app)
    register_background_jobs(app)

    return app


# ============================================================
# 1. DIRECTORIES
# ============================================================

def ensure_directories(app):
    """Create required app directories if they do not exist."""

    dirs = [
        app.config.get("UPLOAD_FOLDER", "uploads"),
        app.config.get("LOG_DIR", "logs"),
        app.config.get("INSTANCE_DIR", "instance"),
    ]

    for directory in dirs:
        Path(directory).mkdir(parents=True, exist_ok=True)


# ============================================================
# 2. LOGGING
# ============================================================

def setup_logging(app):
    """Set up console and file logging."""

    log_dir = Path(app.config.get("LOG_DIR", "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)

    log_level_name = app.config.get("LOG_LEVEL", "INFO")
    log_level = getattr(logging, log_level_name.upper(), logging.INFO)

    app.logger.setLevel(log_level)

    if not app.debug and not app.testing:
        log_file = log_dir / "tablestack.log"

        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
        )
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]"
        ))
        file_handler.setLevel(log_level)

        if not any(isinstance(handler, RotatingFileHandler) for handler in app.logger.handlers):
            app.logger.addHandler(file_handler)

    app.logger.info("TableStack v4 startup")


# ============================================================
# 3. EXTENSIONS
# ============================================================

def register_extensions(app):
    """
    Register optional extensions.

    The app stays usable even if optional packages are not installed.
    """

    global db, migrate, scheduler

    if app.config.get("CORS_ENABLED", False):
        CORS(app)

    try:
        from flask_sqlalchemy import SQLAlchemy
        from flask_migrate import Migrate

        db = SQLAlchemy()
        db.init_app(app)

        migrate = Migrate(app, db)

        app.db = db
        app.migrate = migrate

        app.logger.info("SQLAlchemy and Flask-Migrate initialized")

    except ImportError as error:
        db = None
        migrate = None
        app.db = None
        app.migrate = None
        app.logger.warning(f"Database extensions not installed: {error}")

    try:
        from flask_caching import Cache

        cache = Cache(app, config={
            "CACHE_TYPE": app.config.get("CACHE_TYPE", "SimpleCache")
        })
        app.extensions["cache"] = cache
        app.logger.info("Flask-Caching initialized")

    except ImportError:
        app.logger.info("Flask-Caching not installed – caching disabled")

    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        if app.config.get("SCHEDULER_ENABLED", False):
            scheduler = BackgroundScheduler()
            app.scheduler = scheduler
            scheduler.start()
            app.logger.info("APScheduler started")
        else:
            scheduler = None
            app.scheduler = None
            app.logger.info("Scheduler disabled by config")

    except ImportError:
        scheduler = None
        app.scheduler = None
        app.logger.info("APScheduler not installed – background jobs disabled")


# ============================================================
# 4. AUTH / LOGIN
# ============================================================

def register_auth(app):
    """Initialize Flask-Login and register auth blueprint."""

    try:
        from app.routes.auth_routes import auth_bp, login_manager

        login_manager.init_app(app)
        app.register_blueprint(auth_bp)

        app.logger.info("Registered auth blueprint and login manager")

    except ImportError as error:
        app.logger.warning(f"Auth system not loaded: {error}")


# ============================================================
# 5. BLUEPRINTS
# ============================================================

def register_blueprints(app):
    """Register all route blueprints safely."""

    blueprints = [
        ("dashboard", "app.routes.dashboard_routes", "dashboard_bp"),
        ("schedule", "app.routes.schedule_routes", "schedule_bp"),
        ("sales", "app.routes.sales_routes", "sales_bp"),
        ("labor", "app.routes.labor_routes", "labor_bp"),
        ("staffing", "app.routes.staffing_routes", "staffing_bp"),
        ("reports", "app.routes.reports_routes", "reports_bp"),
        ("forecasting", "app.routes.forecasting_routes", "forecasting_bp"),
    ]

    for name, module_path, blueprint_name in blueprints:
        try:
            module = __import__(module_path, fromlist=[blueprint_name])
            blueprint = getattr(module, blueprint_name)
            app.register_blueprint(blueprint)
            app.logger.info(f"Registered {name} blueprint")

        except (ImportError, AttributeError) as error:
            app.logger.info(f"{name.capitalize()} blueprint not loaded: {error}")


# ============================================================
# 6. SECURITY HEADERS
# ============================================================

def register_security_headers(app):
    """Add basic security headers to every response."""

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")

        if app.config.get("FORCE_HTTPS", False):
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains"
            )

        return response


# ============================================================
# 7. CLI COMMANDS
# ============================================================

def register_cli(app):
    """Register helpful Flask CLI commands."""

    @app.cli.command("list-routes")
    def list_routes():
        """Print all registered routes."""
        import urllib.parse

        output = []

        for rule in app.url_map.iter_rules():
            methods = ",".join(sorted(rule.methods))
            line = urllib.parse.unquote(
                f"{rule.endpoint:40s} {methods:30s} {rule}"
            )
            output.append(line)

        for line in sorted(output):
            print(line)

    @app.cli.command("db-init")
    def db_init():
        """Create database tables if DB is enabled."""
        if app.db is None:
            print("Database not available.")
            return

        app.db.create_all()
        print("Database tables created.")

    @app.cli.command("seed-auth")
    def seed_auth():
        """Create default auth users."""
        try:
            from app.services.auth_service import seed_default_managers

            seed_default_managers()
            print("Default manager users seeded.")

        except Exception as error:
            print(f"Auth seed failed: {error}")

    @app.cli.command("run-forecast")
    def run_forecast():
        """Generate forecast data."""
        try:
            from app.services.dashboard_service import get_forecast_data

            forecast = get_forecast_data(weeks_ahead=4)
            print(f"Generated forecast rows: {len(forecast)}")

        except Exception as error:
            print(f"Forecast failed: {error}")


# ============================================================
# 8. ERROR HANDLERS
# ============================================================

def register_error_handlers(app):
    """Global error pages and API error responses."""

    @app.errorhandler(401)
    def unauthorized_error(error):
        if request.path.startswith("/api/") or request.path.startswith("/schedule/api/"):
            return jsonify({"error": "Authentication required"}), 401

        return redirect(url_for("auth.login"))

    @app.errorhandler(403)
    def forbidden_error(error):
        if request.path.startswith("/api/") or request.path.startswith("/schedule/api/"):
            return jsonify({"error": "Forbidden"}), 403

        return "<h1>403 Forbidden</h1><p>You do not have permission to access this page.</p>", 403

    @app.errorhandler(404)
    def not_found_error(error):
        if request.path.startswith("/api/") or request.path.startswith("/schedule/api/"):
            return jsonify({"error": "API endpoint not found"}), 404

        try:
            return render_template("404.html"), 404
        except Exception:
            return "<h1>404 Not Found</h1><p>The page you requested does not exist.</p>", 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Server error: {error}")

        if request.path.startswith("/api/") or request.path.startswith("/schedule/api/"):
            return jsonify({"error": "Internal server error"}), 500

        try:
            return render_template("500.html"), 500
        except Exception:
            return "<h1>500 Internal Server Error</h1><p>Something went wrong.</p>", 500


# ============================================================
# 9. BACKGROUND JOBS
# ============================================================

def register_background_jobs(app):
    """Register background jobs if scheduler is available."""

    if scheduler is None:
        return

    def scheduled_forecast_refresh():
        with app.app_context():
            try:
                from app.services.dashboard_service import get_forecast_data

                get_forecast_data(weeks_ahead=4)
                app.logger.info("Scheduled forecast refresh completed")

            except Exception as error:
                app.logger.error(f"Scheduled forecast refresh failed: {error}")

    def daily_cleanup():
        with app.app_context():
            try:
                upload_dir = Path(app.config.get("UPLOAD_FOLDER", "uploads"))

                if upload_dir.exists():
                    cutoff = datetime.now().timestamp() - 7 * 86400

                    for file_path in upload_dir.iterdir():
                        if file_path.is_file() and file_path.stat().st_mtime < cutoff:
                            file_path.unlink()
                            app.logger.debug(f"Removed old upload: {file_path.name}")

                app.logger.info("Daily cleanup completed")

            except Exception as error:
                app.logger.error(f"Daily cleanup failed: {error}")

    scheduler.add_job(
        func=scheduled_forecast_refresh,
        trigger="interval",
        hours=app.config.get("SCHEDULER_FORECAST_INTERVAL_HOURS", 6),
        id="forecast_refresh",
        replace_existing=True,
    )

    scheduler.add_job(
        func=daily_cleanup,
        trigger="cron",
        hour=app.config.get("SCHEDULER_CLEANUP_HOUR", 3),
        minute=0,
        id="daily_cleanup",
        replace_existing=True,
    )

    app.logger.info("Background jobs registered")