#!/usr/bin/env python3
"""
TABLE STACK v4 – APPLICATION ENTRY POINT
--------------------------------------------------------------------------------
Usage:
    python run.py               # runs Flask development server
    gunicorn run:app            # production (Gunicorn)

Environment variables (from .env) override defaults.
--------------------------------------------------------------------------------
"""

import os
from dotenv import load_dotenv

from app.services.auth_service import create_user

create_user("ryanschuren@gmail.com", "WeBeTheBest", role="admin")
create_user("michaelstevendepalma@gmail.com", "WeBeTheBest", role="manager")

# Load environment variables from .env file
load_dotenv()

from app import create_app

# Create the Flask application instance
app = create_app()

if __name__ == "__main__":
    # Development server
    host = os.getenv('HOST', '127.0.0.1')
    port = int(os.getenv('PORT', 5000))
    debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

    app.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True
    )