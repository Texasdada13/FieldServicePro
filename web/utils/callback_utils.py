"""Utility functions for callback tracking."""
from datetime import date, timedelta
from sqlalchemy import func
from models.callback import Callback
from models.job import Job


def generate_callback_number(db):
    year = date.today().year
    prefix = f"CB-{year}-"
    last = db.query(Callback).filter(Callback.callback_number.like(f"{prefix}%")).order_by(Callback.id.desc()).first()
    seq = int(last.callback_number.split('-')[-1]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


def get_callback_stats(db, org_id):
    today = date.today()
    month_start = today.replace(day=1)
    ninety_days_ago = today - timedelta(days=90)

    open_count = db.query(func.count(Callback.id)).filter(
        Callback.status.notin_(['resolved', 'closed'])
    ).scalar() or 0

    resolved_month = db.query(func.count(Callback.id)).filter(
        Callback.resolved_date >= month_start,
        Callback.status.in_(['resolved', 'closed'])
    ).scalar() or 0

    recent_callbacks = db.query(func.count(Callback.id)).filter(
        Callback.reported_date >= ninety_days_ago
    ).scalar() or 0

    completed_jobs = db.query(func.count(Job.id)).filter(
        Job.organization_id == org_id,
        Job.status == 'completed',
        Job.completed_at >= ninety_days_ago,
    ).scalar() or 1

    callback_rate = round((recent_callbacks / completed_jobs) * 100, 1)

    return {
        'open_callbacks': open_count,
        'resolved_this_month': resolved_month,
        'callback_rate': callback_rate,
        'recent_callbacks': recent_callbacks,
    }
