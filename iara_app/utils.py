# utils.py
# ---------------------------------------------------------
# Shared helper functions used across blueprints.
# ---------------------------------------------------------

from flask import request
from flask_login import current_user


def log_action(action, target_type=None, target_id=None, detail=None):
    """
    Write one line to the AuditLog table.

    Call this from any route like:
        log_action("login", "User", user.id, "Logged in from mobile")
    """
    from .models import AuditLog
    from . import db
    try:
        entry = AuditLog(
            user_id=current_user.id if current_user.is_authenticated else None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail,
            ip_address=request.remote_addr
        )
        db.session.add(entry)
        db.session.commit()
    except Exception:
        # Never crash the main request just because logging failed
        pass
