# decorators.py
# ---------------------------------------------------------
# Custom decorators that protect routes based on user role.
# Import these in any blueprint file to guard your routes.
# ---------------------------------------------------------

from functools import wraps
from flask import redirect, url_for, abort, flash
from flask_login import current_user, logout_user


def admin_required(f):
    """Only administrators can access this route."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.is_active:
            logout_user()
            flash("Your account has been deactivated. Contact an administrator.", "danger")
            return redirect(url_for("auth.login"))
        if current_user.role != "administrator":
            abort(403)
        return f(*args, **kwargs)
    return decorated


def inspector_required(f):
    """Inspectors AND administrators can access this route."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.is_active:
            logout_user()
            flash("Your account has been deactivated. Contact an administrator.", "danger")
            return redirect(url_for("auth.login"))
        if current_user.role not in ["inspector", "administrator"]:
            abort(403)
        return f(*args, **kwargs)
    return decorated


def fisherman_required(f):
    """Fishermen, amateurs, AND administrators can access this route."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not current_user.is_active:
            logout_user()
            flash("Your account has been deactivated. Contact an administrator.", "danger")
            return redirect(url_for("auth.login"))
        if current_user.role not in ["fisherman", "amateur", "administrator"]:
            abort(403)
        return f(*args, **kwargs)
    return decorated
