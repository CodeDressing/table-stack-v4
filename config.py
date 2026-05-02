"""
TABLE STACK v4 – CONFIGURATION (PHASE 8 UPGRADE)
--------------------------------------------------------------------------------
Central config: development, testing, production.
Values can be overridden by environment variables.

Phase 8 Additions:
- USE_DATABASE flag (to switch between mock and real DB)
- Absolute UPLOAD_FOLDER path
- SCHEDULER_ENABLED flag for background jobs
- OCR_API_KEY for future OCR service
- Improved type conversion for boolean env vars
- Section headers for easy 10k+ line expansion

Structure:
1. Imports & env loading
2. Base Config class
3. Environment-specific subclasses (Development, Testing, Production)
4. Config map and getter function
5. Future expansion blocks
--------------------------------------------------------------------------------
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file (safe if missing)
load_dotenv()

# Helper to parse boolean environment variables
def _bool_env(var_name: str, default: bool = False) -> bool:
    val = os.getenv(var_name, str(default)).lower()
    return val in ('true', '1', 'yes', 'on')


# ============================================================
# 1. BASE CONFIGURATION
# ============================================================
class Config:
    """Base configuration – all environments inherit from this."""

    # --------------------------------------------------------
    # 1.1 Flask Core
    # --------------------------------------------------------
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    DEBUG = False
    TESTING = False

    # --------------------------------------------------------
    # 1.2 Server
    # --------------------------------------------------------
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))

    # --------------------------------------------------------
    # 1.3 Paths
    # --------------------------------------------------------
    BASE_DIR = Path(__file__).resolve().parent
    STATIC_DIR = BASE_DIR / 'app' / 'static'
    TEMPLATES_DIR = BASE_DIR / 'app' / 'templates'

    # Upload folder – absolute path (creates within project root)
    UPLOAD_FOLDER = Path(os.getenv('UPLOAD_FOLDER', BASE_DIR / 'uploads')).resolve()

    # Maximum upload file size (16MB default)
    MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 16 * 1024 * 1024))

    # --------------------------------------------------------
    # 1.4 Logging
    # --------------------------------------------------------
    LOG_DIR = Path(os.getenv('LOG_DIR', BASE_DIR / 'logs')).resolve()

    # --------------------------------------------------------
    # 1.5 CORS (optional)
    # --------------------------------------------------------
    CORS_ENABLED = _bool_env('CORS_ENABLED', False)

    # --------------------------------------------------------
    # 1.6 Database (Phase 8)
    # --------------------------------------------------------
    USE_DATABASE = _bool_env('USE_DATABASE', False)
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///' + str(BASE_DIR / 'tablestack.db'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # --------------------------------------------------------
    # 1.7 Background Scheduler (Phase 8)
    # --------------------------------------------------------
    SCHEDULER_ENABLED = _bool_env('SCHEDULER_ENABLED', True)
    SCHEDULER_FORECAST_INTERVAL_HOURS = int(os.getenv('SCHEDULER_FORECAST_INTERVAL_HOURS', 6))
    SCHEDULER_CLEANUP_HOUR = int(os.getenv('SCHEDULER_CLEANUP_HOUR', 3))

    # --------------------------------------------------------
    # 1.8 Cache / Redis (Phase 9)
    # --------------------------------------------------------
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    CACHE_TYPE = os.getenv('CACHE_TYPE', 'SimpleCache')  # 'RedisCache' for Phase 9

    # --------------------------------------------------------
    # 1.9 External APIs (Phase 9+)
    # --------------------------------------------------------
    WEATHER_API_KEY = os.getenv('WEATHER_API_KEY', '')
    WEATHER_API_URL = 'https://api.openweathermap.org/data/2.5'

    # OCR Service (Phase 8/9)
    OCR_API_KEY = os.getenv('OCR_API_KEY', '')
    OCR_API_URL = os.getenv('OCR_API_URL', '')

    # --------------------------------------------------------
    # 1.10 Misc
    # --------------------------------------------------------
    # Timezone for scheduled jobs (default UTC)
    TIMEZONE = os.getenv('TIMEZONE', 'UTC')


# ============================================================
# 2. ENVIRONMENT-SPECIFIC CONFIGURATIONS
# ============================================================
class DevelopmentConfig(Config):
    """Development environment – debug on, use SQLite, mock data by default."""
    DEBUG = True
    TESTING = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')

    # In development, force USE_DATABASE=False unless explicitly set
    USE_DATABASE = _bool_env('USE_DATABASE', False)

    # Log to console and file
    LOG_LEVEL = 'DEBUG'

    # CORS enabled by default in dev for frontend testing
    CORS_ENABLED = _bool_env('CORS_ENABLED', True)


class TestingConfig(Config):
    """Testing environment – in-memory DB, no background jobs."""
    TESTING = True
    DEBUG = False
    SECRET_KEY = 'test-secret-key'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    USE_DATABASE = True  # Use in-memory DB for tests
    SCHEDULER_ENABLED = False
    CORS_ENABLED = False


class ProductionConfig(Config):
    """Production environment – secure, use real DB, background jobs on."""
    DEBUG = False
    TESTING = False

    # SECRET_KEY must be set in environment
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable not set in production")

    # In production, we typically want to use the database
    USE_DATABASE = _bool_env('USE_DATABASE', True)

    # Background jobs enabled by default
    SCHEDULER_ENABLED = _bool_env('SCHEDULER_ENABLED', True)

    # CORS disabled in production unless required
    CORS_ENABLED = _bool_env('CORS_ENABLED', False)

    # Log to file only, not console
    LOG_LEVEL = 'WARNING'


# ============================================================
# 3. CONFIGURATION MAP & GETTER
# ============================================================
config_map = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}

def get_config():
    """Return the appropriate configuration class based on FLASK_ENV."""
    env = os.getenv('FLASK_ENV', 'development').lower()
    return config_map.get(env, DevelopmentConfig)


# ============================================================
# 4. FUTURE EXPANSION BLOCKS (add below without breaking)
# ============================================================
# Example: Phase 9 – AI Model API keys
# Example: Phase 10 – Webhook URLs for real‑time POS integration
# Example: Phase 11 – Email/SMTP settings for reports