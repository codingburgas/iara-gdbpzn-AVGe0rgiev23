from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_apscheduler import APScheduler
from flask_wtf.csrf import CSRFProtect
from datetime import date

from .config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "main.login"
migrate = Migrate()
scheduler = APScheduler()
csrf = CSRFProtect()


def expire_old_permits():
    """Daily job: automatically expire permits past their expiry date."""
    from .models import Permit  # imported here to avoid circular imports

    today = date.today()
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
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    csrf.init_app(app)  # enables csrf_token() in ALL templates + protects all POST routes

    # Register user loader
    from .models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register blueprint
    from .routes import bp
    app.register_blueprint(bp)

    # -------------------------
    # APScheduler Setup
    # -------------------------
    scheduler.init_app(app)
    scheduler.start()

    # Register daily expiration job
    scheduler.add_job(
        id="expire_permits_daily",
        func=expire_old_permits,
        trigger="interval",
        days=1
    )

    return app
