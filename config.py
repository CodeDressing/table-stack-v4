"""
TABLE STACK v4 – CONFIGURATION
------------------------------------------------------------
Central configuration for development, testing, and production.

Includes:
- Secure Flask settings
- Render-ready production config
- Session security
- Upload/log paths
- Optional database flags
- Optional scheduler/cache flags
- Future API keys
------------------------------------------------------------
"""

import os
from pathlib import Path
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()


def bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name, str(default)).strip().lower()
    return value in {"true", "1", "yes", "on"}


def int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


class Config:
    """Base configuration."""

    BASE_DIR = Path(__file__).resolve().parent

    # Flask core
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-before-production")
    DEBUG = False
    TESTING = False

    # Server
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int_env("PORT", 5000)

    # Paths
    STATIC_DIR = BASE_DIR / "app" / "static"
    TEMPLATES_DIR = BASE_DIR / "app" / "templates"
    UPLOAD_FOLDER = Path(os.getenv("UPLOAD_FOLDER", BASE_DIR / "uploads")).resolve()
    LOG_DIR = Path(os.getenv("LOG_DIR", BASE_DIR / "logs")).resolve()
    INSTANCE_DIR = Path(os.getenv("INSTANCE_DIR", BASE_DIR / "instance")).resolve()

    # Uploads
    MAX_CONTENT_LENGTH = int_env("MAX_CONTENT_LENGTH", 16 * 1024 * 1024)

    # CORS
    CORS_ENABLED = bool_env("CORS_ENABLED", False)

    # Database
    USE_DATABASE = bool_env("USE_DATABASE", False)
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "DATABASE_URL",
        "sqlite:///" + str(BASE_DIR / "tablestack.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Sessions / cookies
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = bool_env("SESSION_COOKIE_SECURE", False)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = bool_env("REMEMBER_COOKIE_SECURE", False)
    REMEMBER_COOKIE_DURATION = timedelta(days=7)
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=int_env("SESSION_IDLE_MINUTES", 15))

    # Security headers / HTTPS
    FORCE_HTTPS = bool_env("FORCE_HTTPS", False)

    # Scheduler
    SCHEDULER_ENABLED = bool_env("SCHEDULER_ENABLED", False)
    SCHEDULER_FORECAST_INTERVAL_HOURS = int_env("SCHEDULER_FORECAST_INTERVAL_HOURS", 6)
    SCHEDULER_CLEANUP_HOUR = int_env("SCHEDULER_CLEANUP_HOUR", 3)

    # Cache / Redis
    REDIS_URL = os.getenv("REDIS_URL", "")
    CACHE_TYPE = os.getenv("CACHE_TYPE", "SimpleCache")

    # Rate limiting
    RATELIMIT_STORAGE_URI = os.getenv("RATELIMIT_STORAGE_URI", "memory://")
    LOGIN_RATE_LIMIT = os.getenv("LOGIN_RATE_LIMIT", "5 per 5 minutes")

    # External APIs
    WEATHER_API_KEY = os.getenv("WEATHER_API_KEY", "")
    WEATHER_API_URL = os.getenv("WEATHER_API_URL", "https://api.openweathermap.org/data/2.5")
    OCR_API_KEY = os.getenv("OCR_API_KEY", "")
    OCR_API_URL = os.getenv("OCR_API_URL", "")

    # App metadata
    APP_NAME = "TableStack v4"
    TIMEZONE = os.getenv("TIMEZONE", "America/New_York")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    CORS_ENABLED = bool_env("CORS_ENABLED", True)
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    FORCE_HTTPS = False
    USE_DATABASE = bool_env("USE_DATABASE", False)
    SCHEDULER_ENABLED = bool_env("SCHEDULER_ENABLED", False)
    LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")


class TestingConfig(Config):
    DEBUG = False
    TESTING = True
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    USE_DATABASE = True
    SCHEDULER_ENABLED = False
    CORS_ENABLED = False
    SESSION_COOKIE_SECURE = False
    REMEMBER_COOKIE_SECURE = False
    FORCE_HTTPS = False
    LOG_LEVEL = "ERROR"


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False

    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable not set in production")

    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    FORCE_HTTPS = bool_env("FORCE_HTTPS", True)
    CORS_ENABLED = bool_env("CORS_ENABLED", False)

    # Keep database optional so Render deploy does not break without SQLAlchemy/Postgres.
    USE_DATABASE = bool_env("USE_DATABASE", False)

    SCHEDULER_ENABLED = bool_env("SCHEDULER_ENABLED", False)
    LOG_LEVEL = os.getenv("LOG_LEVEL", "WARNING")


config_map = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def get_config():
    env = os.getenv("FLASK_ENV", "development").strip().lower()
    return config_map.get(env, DevelopmentConfig)