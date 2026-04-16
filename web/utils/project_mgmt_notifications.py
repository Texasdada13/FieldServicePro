"""Notification triggers for RFI, Submittal, Punch List, Daily Log events.
Called from CLI scheduled checks."""
from datetime import date, timedelta
from models.database import get_session
from models.rfi import RFI
from models.submittal import Submittal


def notify_rfi_overdue():
    """Send overdue notifications for RFIs past due date."""
    db = get_session()
    try:
        from web.utils.notification_service import NotificationService

        overdue = db.query(RFI).filter(
            RFI.status.notin_(['answered', 'closed', 'void']),
            RFI.date_required != None,
            RFI.date_required < date.today(),
        ).all()

        for rfi in overdue:
            try:
                NotificationService.notify('system', rfi,
                    title=f'RFI Overdue: {rfi.rfi_number}',
                    message=f'RFI "{rfi.subject}" was due {rfi.date_required.strftime("%B %d")} and has not been answered.',
                    override_recipients=[r for r in [rfi.submitted_by, rfi.assigned_to] if r])
            except Exception:
                pass

        return len(overdue)
    finally:
        db.close()


def notify_submittal_overdue():
    """Check for overdue submittals still under review."""
    db = get_session()
    try:
        from web.utils.notification_service import NotificationService

        overdue = db.query(Submittal).filter(
            Submittal.status.in_(['submitted', 'under_review']),
            Submittal.date_required != None,
            Submittal.date_required < date.today(),
        ).all()

        for sub in overdue:
            try:
                NotificationService.notify('system', sub,
                    title=f'Submittal Overdue: {sub.submittal_number}',
                    message=f'Submittal "{sub.title}" is past its required date.',
                    override_recipients=[sub.submitted_by] if sub.submitted_by else None)
            except Exception:
                pass

        return len(overdue)
    finally:
        db.close()


def notify_delivery_approaching():
    """Alert when approved submittal delivery is within 3 days."""
    db = get_session()
    try:
        from web.utils.notification_service import NotificationService

        threshold = date.today() + timedelta(days=3)
        approaching = db.query(Submittal).filter(
            Submittal.status.in_(['approved', 'approved_as_noted']),
            Submittal.delivery_date != None,
            Submittal.delivery_date <= threshold,
            Submittal.delivery_date >= date.today(),
        ).all()

        for sub in approaching:
            try:
                NotificationService.notify('system', sub,
                    title=f'Delivery Approaching: {sub.submittal_number}',
                    message=f'"{sub.title}" expected by {sub.delivery_date.strftime("%B %d")}.',
                    override_recipients=[sub.submitted_by] if sub.submitted_by else None)
            except Exception:
                pass

        return len(approaching)
    finally:
        db.close()
