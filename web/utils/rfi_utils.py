"""RFI utility functions — stats and helpers."""
from datetime import date
from models.rfi import RFI


def get_rfi_stats(db, project_id=None):
    """Return dict of RFI counts for dashboard or project view."""
    q = db.query(RFI)
    if project_id:
        q = q.filter_by(project_id=project_id)

    total = q.count()
    open_count = q.filter(RFI.status.in_(['open', 'pending_response'])).count()

    overdue_rfis = q.filter(
        RFI.status.notin_(['answered', 'closed', 'void']),
        RFI.date_required != None,
        RFI.date_required < date.today(),
    ).all()

    all_answered = q.filter(RFI.response_date != None).all()
    avg_days = 0
    if all_answered:
        days_list = []
        for r in all_answered:
            if r.response_date and r.date_submitted:
                rd = r.response_date.date() if hasattr(r.response_date, 'date') else r.response_date
                days_list.append((rd - r.date_submitted).days)
        avg_days = round(sum(days_list) / len(days_list), 1) if days_list else 0

    return {
        'open': open_count,
        'overdue': len(overdue_rfis),
        'overdue_rfis': overdue_rfis,
        'avg_response_days': avg_days,
        'total': total,
    }
