# config.py
# ---------------------------------------------------------
# Stores configuration settings for the Flask application.
# Keeping configuration separate makes the project cleaner.
# ---------------------------------------------------------

import os

class Config:
    # Secret key is required for:
    # - session cookies
    # - CSRF protection
    SECRET_KEY = os.environ.get("SECRET_KEY") or "dev_secret_key_change_me"

    # SQLite database (simple file-based DB for development)
    SQLALCHEMY_DATABASE_URI = "sqlite:///iara.db"

    # Disable modification tracking to improve performance
    SQLALCHEMY_TRACK_MODIFICATIONS = False
