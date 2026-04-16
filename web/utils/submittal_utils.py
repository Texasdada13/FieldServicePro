"""Submittal utility functions — stats."""
from datetime import date
from models.submittal import Submittal


def get_submittal_stats(db, project_id=None):
    q = db.query(Submittal)
    if project_id:
        q = q.filter_by(project_id=project_id)

    total = q.count()
    pending = q.filter(Submittal.status.in_(['submitted', 'under_review'])).count()
    approved = q.filter(Submittal.status.in_(['approved', 'approved_as_noted'])).count()
    revise = q.filter_by(status='revise_and_resubmit').count()

    all_subs = q.all()
    overdue = sum(1 for s in all_subs if s.is_overdue)

    return {
        'pending': pending,
        'approved': approved,
        'overdue': overdue,
        'revise': revise,
        'total': total,
    }
