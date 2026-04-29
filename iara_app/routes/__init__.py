# routes/__init__.py
# ---------------------------------------------------------
# This file turns the `routes` folder into a Python package.
# It provides a single function to register all blueprints
# onto the Flask app at startup.
# ---------------------------------------------------------

from .auth import bp as auth_bp
from .admin import bp as admin_bp
from .inspector import bp as inspector_bp
from .fisherman import bp as fisherman_bp
from .public import bp as public_bp
from .lookup import bp as lookup_bp
from .trips import bp as trips_bp


def register_blueprints(app):
    """Register all route blueprints with the Flask application."""
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(inspector_bp)
    app.register_blueprint(fisherman_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(lookup_bp)
    app.register_blueprint(trips_bp)
