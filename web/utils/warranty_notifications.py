"""Warranty and callback notification utilities for CLI commands."""
import logging
from datetime import date
from models.warranty import Warranty
from models.callback import Callback
from models.user import User
from models.technician import Technician
from models.time_entry import TimeEntry
from sqlalchemy import func

log = logging.getLogger(__name__)


def notify_expiring_warranties(db):
    """Log/send notifications for warranties expiring within 30 days."""
    from web.utils.warranty_utils import refresh_all_warranty_statuses
    refresh_all_warranty_statuses(db)

    expiring = db.query(Warranty).filter(Warranty.status == 'expiring_soon').all()
    if not expiring:
        return {'sent': 0, 'warranties': 0}

    admins = db.query(User).filter(User.role.in_(['owner', 'admin'])).all()
    for admin in admins:
        if admin.email:
            log.info(
                "[WARRANTY EXPIRY] -> %s: %d warranty(s) expiring soon",
                admin.email, len(expiring)
            )
    return {'sent': len(admins), 'warranties': len(expiring)}


def notify_open_callbacks(db):
    """Log/send notifications for open callbacks."""
    open_cbs = db.query(Callback).filter(
        Callback.status.notin_(['resolved', 'closed'])
    ).all()
    if not open_cbs:
        return {'sent': 0, 'callbacks': 0}

    admins = db.query(User).filter(User.role.in_(['owner', 'admin'])).all()
    for admin in admins:
        if admin.email:
            log.info(
                "[CALLBACK ALERT] -> %s: %d open callback(s)",
                admin.email, len(open_cbs)
            )
    return {'sent': len(admins), 'callbacks': len(open_cbs)}


def check_callback_rate_thresholds(db, threshold=5.0):
    """Flag techs exceeding callback rate threshold."""
    flagged = []
    techs = db.query(Technician).filter_by(is_active=True).all()
    for tech in techs:
        total_callbacks = db.query(func.count(Callback.id)).filter(
            Callback.responsible_technician_id == tech.id
        ).scalar() or 0
        total_jobs = db.query(func.count(func.distinct(TimeEntry.job_id))).filter(
            TimeEntry.technician_id == tech.id
        ).scalar() or 0
        if total_jobs > 0:
            rate = (total_callbacks / total_jobs) * 100
            if rate > threshold:
                flagged.append({
                    'tech': tech, 'rate': round(rate, 1),
                    'callbacks': total_callbacks, 'jobs': total_jobs,
                })
    return {'flagged': len(flagged), 'threshold': threshold, 'details': flagged}
