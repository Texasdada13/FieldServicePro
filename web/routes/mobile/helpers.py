"""Shared helpers for mobile routes."""
from functools import wraps
from flask import g, abort, request, redirect, url_for
from flask_login import login_required, current_user
from models.database import get_session
from models.technician import Technician


def get_current_technician():
    """Get the Technician record linked to the current logged-in user.

    Uses current_user from Flask-Login.
    Returns Technician or None.
    """
    if not current_user.is_authenticated:
        return None
    db = get_session()
    try:
        tech = db.query(Technician).filter_by(user_id=current_user.id).first()
        return tech
    finally:
        db.close()


def mobile_login_required(f):
    """Decorator: requires login AND a linked technician profile."""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        tech = get_current_technician()
        if tech is None:
            abort(403, description="No technician profile linked to your account.")

        g.technician = tech
        return f(*args, **kwargs)

    return decorated_function


def is_mobile_user_agent():
    """Detect if the request comes from a mobile device."""
    ua = request.headers.get('User-Agent', '').lower()
    mobile_keywords = [
        'iphone', 'ipod', 'android', 'webos', 'blackberry',
        'opera mini', 'opera mobi', 'windows phone', 'iemobile',
        'mobile safari', 'mobile'
    ]
    return any(kw in ua for kw in mobile_keywords)
