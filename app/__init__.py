"""
TABLE STACK v4 – APPLICATION FACTORY
--------------------------------------------------------------------------------
Purpose: Central app creation, blueprint registration, extension setup, CLI commands.
Structure:
1. create_app() – main factory
2. register_blueprints() – loads all routes (dashboard + future modules)
3. register_extensions() – placeholder for DB, auth, caching
4. register_cli() – custom Flask CLI commands
5. register_error_handlers() – global error pages

Ready for 10k+ lines: add new blueprints, extensions, or CLI commands below.
--------------------------------------------------------------------------------
"""

import os
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, render_template, jsonify
from flask_cors import CORS  # optional, for future API access

from config import Config


def create_app(config_class=Config):
    """Application factory."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Enable CORS if needed (for separate frontend in future)
    if app.config.get('CORS_ENABLED', False):
        CORS(app)

    # Setup logging
    setup_logging(app)

    # Register core components
    register_blueprints(app)
    register_extensions(app)
    register_cli(app)
    register_error_handlers(app)

    return app


def setup_logging(app):
    """Configure file and console logging."""
    if not app.debug and not app.testing:
        log_dir = Path(app.config.get('LOG_DIR', 'logs'))
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / 'tablestack.log'

        file_handler = RotatingFileHandler(
            log_file, maxBytes=10*1024*1024, backupCount=5
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
        app.logger.info('Table Stack v4 startup')


def register_blueprints(app):
    """Register all route blueprints. Missing modules are gracefully skipped."""
    # Dashboard (core)
    from app.routes.dashboard_routes import dashboard_bp
    app.register_blueprint(dashboard_bp)
    app.logger.info("Registered dashboard blueprint")

    # Future modules (optional, safe import)
    future_modules = [
        ('sales', 'sales_routes', 'sales_bp'),
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


def register_extensions(app):
    """
    Placeholder for Flask extensions:
    - SQLAlchemy (database)
    - Flask-Login
    - Flask-Migrate
    - Flask-Caching (Redis)
    - Flask-Mail
    """
    # Example: from app.extensions import db, migrate
    # db.init_app(app)
    # migrate.init_app(app, db)
    pass


def register_cli(app):
    """Custom CLI commands for data management."""
    @app.cli.command("seed-mock-data")
    def seed_mock_data():
        """Seed database with mock data (Phase 8+)."""
        print("Seeding mock data... (implementation in Phase 8)")
        # Future: call service layer to populate DB

    @app.cli.command("run-forecast")
    def run_forecast():
        """Generate and store forecast data."""
        print("Forecast generation CLI ready in Phase 9")

    @app.cli.command("list-routes")
    def list_routes():
        """Print all registered routes."""
        import urllib
        output = []
        for rule in app.url_map.iter_rules():
            methods = ','.join(rule.methods)
            line = urllib.parse.unquote(f"{rule.endpoint:30s} {methods:20s} {rule}")
            output.append(line)
        for line in sorted(output):
            print(line)


def register_error_handlers(app):
    """Global error pages for HTTP errors."""
    @app.errorhandler(404)
    def not_found_error(error):
        if request.path.startswith('/api/'):
            return jsonify({"error": "API endpoint not found"}), 404
        return render_template('404.html'), 404

    @app.errorhandler(500)
    def internal_error(error):
        app.logger.error(f"Server Error: {error}")
        if request.path.startswith('/api/'):
            return jsonify({"error": "Internal server error"}), 500
        return render_template('500.html'), 500