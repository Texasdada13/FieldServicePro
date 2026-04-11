"""Project utility functions."""
from datetime import datetime
from models.project import Project
from models.job import Job
from models.invoice import Invoice, Payment
from models.change_order import ChangeOrder


def generate_project_number(db):
    """Generate next project number: PRJ-YYYY-XXXX."""
    return Project.generate_project_number(db)


def get_project_stats(db, org_id):
    """Get summary stats for the project list page."""
    total = db.query(Project).filter_by(organization_id=org_id).count()
    active = db.query(Project).filter_by(organization_id=org_id, status='active').count()
    planning = db.query(Project).filter_by(organization_id=org_id, status='planning').count()
    completed = db.query(Project).filter_by(organization_id=org_id, status='completed').count()
    on_hold = db.query(Project).filter_by(organization_id=org_id, status='on_hold').count()

    # Total active budget
    active_projects = db.query(Project).filter_by(organization_id=org_id, status='active').all()
    total_budget = sum(float(p.approved_budget or p.estimated_budget or 0) for p in active_projects)

    # At-risk count (behind schedule)
    at_risk = sum(1 for p in active_projects if p.is_behind_schedule)

    return {
        'total': total,
        'active': active,
        'planning': planning,
        'completed': completed,
        'on_hold': on_hold,
        'total_budget': total_budget,
        'at_risk': at_risk,
    }


def compute_project_financials(db, project):
    """Compute financial summary for a project from its related entities."""
    from sqlalchemy import or_

    jobs = db.query(Job).filter_by(project_id=project.id).all()
    job_ids = [j.id for j in jobs]

    # Estimated from jobs
    total_estimated = sum(float(j.estimated_amount or 0) for j in jobs)

    # Invoices linked to project or project's jobs
    inv_filter = [Invoice.project_id == project.id]
    if job_ids:
        inv_filter.append(Invoice.job_id.in_(job_ids))
    invoices = db.query(Invoice).filter(or_(*inv_filter)).all()

    total_invoiced = sum(float(i.total or 0) for i in invoices)
    total_paid = sum(float(i.amount_paid or 0) for i in invoices)
    total_outstanding = sum(float(i.balance_due or 0) for i in invoices)

    budget = float(project.approved_budget or project.estimated_budget or 0)
    budget_variance = budget - total_estimated

    # Change order impact
    co_impact = 0.0
    if job_ids:
        cos = db.query(ChangeOrder).filter(
            ChangeOrder.job_id.in_(job_ids),
            ChangeOrder.status == 'approved'
        ).all()
        co_impact = sum(float(co.revised_amount or 0) - float(co.original_amount or 0) for co in cos)

    return {
        'total_estimated': total_estimated,
        'total_invoiced': total_invoiced,
        'total_paid': total_paid,
        'total_outstanding': total_outstanding,
        'budget': budget,
        'budget_variance': budget_variance,
        'co_impact': co_impact,
        'job_count': len(jobs),
        'invoice_count': len(invoices),
    }
