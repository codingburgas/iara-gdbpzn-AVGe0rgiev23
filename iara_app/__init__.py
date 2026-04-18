# iara_app/__init__.py
# ---------------------------------------------------------
# Application factory — creates and configures the Flask app.
# ---------------------------------------------------------

from datetime import date

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_apscheduler import APScheduler
from flask_wtf.csrf import CSRFProtect

from .config import Config

# Create extension objects (not yet attached to any app)
db           = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"   # redirect here when @login_required fails
migrate      = Migrate()
scheduler    = APScheduler()
csrf         = CSRFProtect()


def expire_old_permits():
    """
    Scheduler job — runs once a day.
    Automatically marks permits as Expired when their expiry date has passed.
    """
    from .models import Permit  # imported inside function to avoid circular imports

    today   = date.today()
    permits = Permit.query.all()
    changed = False

    for permit in permits:
        if permit.expiry_date < today and permit.status != "Expired":
            permit.status = "Expired"
            changed = True

    if changed:
        db.session.commit()
        print("[Scheduler] Expired permits updated.")


def create_app():
    """Create, configure, and return the Flask application."""
    app = Flask(__name__)
    app.config.from_object(Config)

    # ── Attach extensions ──────────────────────────────────────────────────
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    # CSRFProtect automatically adds csrf_token() to every template
    # and blocks any POST request that doesn't include the token.
    csrf.init_app(app)

    # ── User loader for Flask-Login ────────────────────────────────────────
    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        """
        Flask-Login calls this to get the User object from the session.
        Returns None if the user doesn't exist or has been deactivated,
        which forces a logout automatically.
        """
        user = db.session.get(User, int(user_id))   # SQLAlchemy 2.x style
        if user is None:
            return None
        # If admin deactivated the account, treat them as logged out
        if not user.is_active:
            return None
        return user

    # ── Register blueprints ────────────────────────────────────────────────
    from .routes import register_blueprints
    register_blueprints(app)

    # ── Daily scheduler — auto-expire permits ──────────────────────────────
    scheduler.init_app(app)
    scheduler.start()
    scheduler.add_job(
        id="expire_permits_daily",
        func=expire_old_permits,
        trigger="interval",
        days=1
    )

    return app
