"""
TABLE STACK v4 – CONFIGURATION
--------------------------------------------------------------------------------
Central config: development, testing, production.
Values can be overridden by environment variables.
--------------------------------------------------------------------------------
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file in development
load_dotenv()
class Config:
    """Base configuration."""
    # Flask
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-production')
    DEBUG = False
    TESTING = False

    # Server
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))

    # Paths
    BASE_DIR = Path(__file__).resolve().parent
    STATIC_DIR = BASE_DIR / 'app' / 'static'
    TEMPLATES_DIR = BASE_DIR / 'app' / 'templates'

    # Logging
    LOG_DIR = os.getenv('LOG_DIR', 'logs')

    # CORS (for future API separation)
    CORS_ENABLED = os.getenv('CORS_ENABLED', 'False').lower() == 'true'

    # Database (Phase 8)
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///tablestack.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Redis / Cache (Phase 9)
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

    # External APIs (Phase 9+)
    WEATHER_API_KEY = os.getenv('WEATHER_API_KEY', '')
    WEATHER_API_URL = 'https://api.openweathermap.org/data/2.5'

    # OCR / Import (Phase 8)
    UPLOAD_FOLDER = BASE_DIR / 'uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')


class TestingConfig(Config):
    TESTING = True
    DEBUG = False
    SECRET_KEY = 'test-secret-key'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False
    # In production, SECRET_KEY must be set in environment
    SECRET_KEY = os.getenv('SECRET_KEY')
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable not set in production")


# Map environment name to config class
config_map = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config():
    env = os.getenv('FLASK_ENV', 'development')
    return config_map.get(env, DevelopmentConfig)