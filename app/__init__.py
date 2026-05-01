from flask import Flask


def create_app():
    """
    Application factory for Table Stack v4.

    This is the central place where:
    - Flask app is created
    - Config is loaded
    - Blueprints are registered
    - Extensions (DB, etc.) will be initialized later
    """

    app = Flask(__name__)

    # -------------------------
    # CONFIGURATION
    # -------------------------
    # Future: load from config.py or environment variables
    app.config["SECRET_KEY"] = "dev"  # replace later for production

    # -------------------------
    # BLUEPRINT REGISTRATION
    # -------------------------
    from app.routes.dashboard_routes import dashboard_bp
    app.register_blueprint(dashboard_bp)

    # Future blueprint registrations:
    # from app.routes.sales_routes import sales_bp
    # from app.routes.labor_routes import labor_bp
    # from app.routes.staffing_routes import staffing_bp

    # app.register_blueprint(sales_bp)
    # app.register_blueprint(labor_bp)
    # app.register_blueprint(staffing_bp)

    # -------------------------
    # EXTENSIONS (FUTURE)
    # -------------------------
    # Example:
    # from app.extensions import db
    # db.init_app(app)

    # -------------------------
    # CLI / STARTUP HOOKS (FUTURE)
    # -------------------------
    # Example:
    # from app.commands import register_commands
    # register_commands(app)

    return app