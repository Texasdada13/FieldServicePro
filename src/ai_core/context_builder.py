"""Builds context strings from database for injection into Claude prompts."""

from datetime import datetime, timezone, timedelta
from sqlalchemy import func


def build_global_context(db, org_id):
    """Build a full business context summary for the AI."""
    from models import Client, Job, Quote, Invoice, Technician, Division

    lines = ["=== FieldServicePro FIELD SERVICE — BUSINESS DATA ===\n"]

    # Divisions
    divisions = db.query(Division).filter_by(organization_id=org_id, is_active=True).order_by(Division.sort_order).all()
    lines.append("DIVISIONS: " + ", ".join(f"{d.name} ({d.code})" for d in divisions))

    # Client summary
    total_clients = db.query(func.count(Client.id)).filter_by(organization_id=org_id, is_active=True).scalar()
    commercial = db.query(func.count(Client.id)).filter_by(organization_id=org_id, is_active=True, client_type='commercial').scalar()
    residential = total_clients - commercial
    lines.append(f"\nCLIENTS: {total_clients} total ({commercial} commercial, {residential} residential)")

    # Job summary
    total_jobs = db.query(func.count(Job.id)).filter_by(organization_id=org_id).scalar()
    active_jobs = db.query(func.count(Job.id)).filter(Job.organization_id == org_id, Job.status.in_(['scheduled', 'in_progress'])).scalar()
    draft_jobs = db.query(func.count(Job.id)).filter_by(organization_id=org_id, status='draft').scalar()
    on_hold = db.query(func.count(Job.id)).filter_by(organization_id=org_id, status='on_hold').scalar()
    completed = db.query(func.count(Job.id)).filter_by(organization_id=org_id, status='completed').scalar()
    cancelled = db.query(func.count(Job.id)).filter_by(organization_id=org_id, status='cancelled').scalar()
    lines.append(f"\nJOBS: {total_jobs} total | {active_jobs} active | {draft_jobs} draft | {on_hold} on hold | {completed} completed | {cancelled} cancelled")

    # Jobs by division
    for div in divisions:
        div_count = db.query(func.count(Job.id)).filter_by(organization_id=org_id, division_id=div.id).scalar()
        div_active = db.query(func.count(Job.id)).filter(Job.organization_id == org_id, Job.division_id == div.id, Job.status.in_(['scheduled', 'in_progress'])).scalar()
        lines.append(f"  {div.name}: {div_count} total, {div_active} active")

    # Invoice / revenue summary
    total_invoiced = db.query(func.coalesce(func.sum(Invoice.total), 0)).filter_by(organization_id=org_id).scalar()
    total_outstanding = db.query(func.coalesce(func.sum(Invoice.balance_due), 0)).filter(
        Invoice.organization_id == org_id, Invoice.status.in_(['sent', 'viewed', 'partial', 'overdue'])
    ).scalar()
    total_overdue = db.query(func.coalesce(func.sum(Invoice.balance_due), 0)).filter(
        Invoice.organization_id == org_id, Invoice.status == 'overdue'
    ).scalar()
    total_paid = db.query(func.coalesce(func.sum(Invoice.total), 0)).filter_by(organization_id=org_id, status='paid').scalar()
    lines.append(f"\nREVENUE: ${total_invoiced:,.2f} invoiced | ${total_paid:,.2f} paid | ${total_outstanding:,.2f} outstanding | ${total_overdue:,.2f} overdue")

    # Overdue invoices detail
    overdue_invoices = db.query(Invoice).filter(Invoice.organization_id == org_id, Invoice.status == 'overdue').all()
    if overdue_invoices:
        lines.append(f"\nOVERDUE INVOICES ({len(overdue_invoices)}):")
        for inv in overdue_invoices:
            client_name = inv.client.display_name if inv.client else 'Unknown'
            lines.append(f"  {inv.invoice_number}: ${inv.balance_due:,.2f} due — {client_name} (due {inv.due_date.strftime('%Y-%m-%d') if inv.due_date else 'N/A'})")

    # Quote summary
    total_quotes = db.query(func.count(Quote.id)).filter_by(organization_id=org_id).scalar()
    pending_quotes = db.query(func.count(Quote.id)).filter(Quote.organization_id == org_id, Quote.status.in_(['draft', 'sent'])).scalar()
    approved_quotes = db.query(func.count(Quote.id)).filter_by(organization_id=org_id, status='approved').scalar()
    declined_quotes = db.query(func.count(Quote.id)).filter_by(organization_id=org_id, status='declined').scalar()
    quote_value = db.query(func.coalesce(func.sum(Quote.total), 0)).filter(Quote.organization_id == org_id, Quote.status.in_(['draft', 'sent'])).scalar()
    lines.append(f"\nQUOTES: {total_quotes} total | {pending_quotes} pending (${quote_value:,.2f}) | {approved_quotes} approved | {declined_quotes} declined")

    # Technicians
    techs = db.query(Technician).filter_by(organization_id=org_id, is_active=True).all()
    lines.append(f"\nTECHNICIANS ({len(techs)}):")
    for tech in techs:
        assigned = db.query(func.count(Job.id)).filter(
            Job.assigned_technician_id == tech.id, Job.status.in_(['scheduled', 'in_progress'])
        ).scalar()
        completed_count = db.query(func.count(Job.id)).filter_by(assigned_technician_id=tech.id, status='completed').scalar()
        lines.append(f"  {tech.full_name} ({tech.division.name if tech.division else '?'}): {assigned} active, {completed_count} completed")

    # Recent jobs (last 20)
    recent = db.query(Job).filter_by(organization_id=org_id).order_by(Job.created_at.desc()).limit(20).all()
    if recent:
        lines.append("\nRECENT JOBS (last 20):")
        for j in recent:
            client_name = j.client.display_name if j.client else 'Unknown'
            div_name = j.division.name if j.division else '?'
            tech_name = j.technician.full_name if j.technician else 'Unassigned'
            sched = j.scheduled_date.strftime('%Y-%m-%d') if j.scheduled_date else 'Not scheduled'
            prop = j.property.display_address if j.property else 'N/A'
            lines.append(f"  {j.job_number}: {j.title} | {div_name} | {j.status} | {client_name} | {prop} | {tech_name} | Sched: {sched} | Est: ${j.estimated_amount or 0:,.2f}")

    # Top clients by revenue
    top_clients = db.query(
        Client.id, Client.company_name, Client.first_name, Client.last_name, Client.client_type,
        func.count(Job.id).label('job_count'),
        func.coalesce(func.sum(Invoice.total), 0).label('revenue')
    ).outerjoin(Job, Job.client_id == Client.id).outerjoin(Invoice, Invoice.client_id == Client.id).filter(
        Client.organization_id == org_id
    ).group_by(Client.id).order_by(func.coalesce(func.sum(Invoice.total), 0).desc()).limit(10).all()

    if top_clients:
        lines.append("\nTOP CLIENTS BY REVENUE:")
        for c in top_clients:
            name = c.company_name or f"{c.first_name or ''} {c.last_name or ''}".strip() or f"Client #{c.id}"
            lines.append(f"  {name} ({c.client_type}): {c.job_count} jobs, ${c.revenue:,.2f} revenue")

    return '\n'.join(lines)


def build_client_context(db, client_id):
    """Build context for a specific client."""
    from models import Client, Job, Quote, Invoice, ClientNote, ClientCommunication, Property

    client = db.query(Client).filter_by(id=client_id).first()
    if not client:
        return "Client not found."

    lines = [f"=== CLIENT DETAIL: {client.display_name} ===\n"]
    lines.append(f"Type: {client.client_type}")
    lines.append(f"Email: {client.email or 'N/A'} | Phone: {client.phone or 'N/A'}")
    lines.append(f"City: {client.billing_city or 'N/A'}")

    # Properties
    props = [p for p in client.properties if p.is_active]
    if props:
        lines.append(f"\nPROPERTIES ({len(props)}):")
        for p in props:
            lines.append(f"  {p.display_address}")

    # Contacts
    if client.contacts:
        lines.append(f"\nCONTACTS ({len(client.contacts)}):")
        for c in client.contacts:
            lines.append(f"  {c.first_name} {c.last_name or ''} — {c.title or 'N/A'} | {c.phone or ''} | {c.email or ''}")

    # All jobs
    jobs = db.query(Job).filter_by(client_id=client_id).order_by(Job.created_at.desc()).all()
    lines.append(f"\nJOBS ({len(jobs)}):")
    status_counts = {}
    for j in jobs:
        status_counts[j.status] = status_counts.get(j.status, 0) + 1
        div_name = j.division.name if j.division else '?'
        tech_name = j.technician.full_name if j.technician else 'Unassigned'
        sched = j.scheduled_date.strftime('%Y-%m-%d') if j.scheduled_date else 'Not scheduled'
        prop = j.property.display_address if j.property else 'N/A'
        lines.append(f"  {j.job_number}: {j.title} | {div_name} | {j.status} | {tech_name} | {prop} | Sched: {sched} | Est: ${j.estimated_amount or 0:,.2f}")
    lines.append(f"  Status breakdown: {status_counts}")

    # Visit frequency
    visit_count = len([j for j in jobs if j.status in ('completed', 'invoiced')])
    lines.append(f"  Total completed visits: {visit_count}")

    # Cancelled/on-hold (red flags)
    cancelled = [j for j in jobs if j.status == 'cancelled']
    on_hold = [j for j in jobs if j.status == 'on_hold']
    if cancelled:
        lines.append(f"\n  RED FLAG — {len(cancelled)} CANCELLED JOBS:")
        for j in cancelled:
            lines.append(f"    {j.job_number}: {j.title}")
    if on_hold:
        lines.append(f"\n  WARNING — {len(on_hold)} ON HOLD JOBS:")
        for j in on_hold:
            lines.append(f"    {j.job_number}: {j.title}")

    # Quotes
    quotes = db.query(Quote).filter_by(client_id=client_id).order_by(Quote.created_at.desc()).all()
    if quotes:
        lines.append(f"\nQUOTES ({len(quotes)}):")
        for q in quotes:
            div_name = q.division.name if q.division else '?'
            lines.append(f"  {q.quote_number}: {q.title} | {div_name} | {q.status} | ${q.total or 0:,.2f}")

    # Invoices
    invoices = db.query(Invoice).filter_by(client_id=client_id).order_by(Invoice.created_at.desc()).all()
    total_invoiced = sum(inv.total or 0 for inv in invoices)
    total_paid = sum(inv.amount_paid or 0 for inv in invoices)
    total_outstanding = sum(inv.balance_due or 0 for inv in invoices if inv.status in ('sent', 'viewed', 'partial', 'overdue'))
    if invoices:
        lines.append(f"\nINVOICES ({len(invoices)}): ${total_invoiced:,.2f} invoiced | ${total_paid:,.2f} paid | ${total_outstanding:,.2f} outstanding")
        for inv in invoices:
            lines.append(f"  {inv.invoice_number}: {inv.status} | Total: ${inv.total or 0:,.2f} | Due: ${inv.balance_due or 0:,.2f} | Issued: {inv.issued_date.strftime('%Y-%m-%d') if inv.issued_date else 'N/A'}")

    # Notes
    notes = db.query(ClientNote).filter_by(client_id=client_id).order_by(ClientNote.is_starred.desc(), ClientNote.created_at.desc()).all()
    if notes:
        lines.append(f"\nCLIENT NOTES ({len(notes)}):")
        for n in notes:
            star = " [STARRED]" if n.is_starred else ""
            lines.append(f"  {n.created_at.strftime('%Y-%m-%d') if n.created_at else '?'}{star}: {n.content[:200]}")

    return '\n'.join(lines)


def get_context_summary(db, org_id, client_id=None):
    """Quick summary dict for suggested prompts."""
    from models import Job, Invoice, Client

    summary = {}
    summary['active_jobs'] = db.query(func.count(Job.id)).filter(
        Job.organization_id == org_id, Job.status.in_(['scheduled', 'in_progress'])
    ).scalar()
    summary['overdue_invoices'] = db.query(func.count(Invoice.id)).filter(
        Invoice.organization_id == org_id, Invoice.status == 'overdue'
    ).scalar()

    if client_id:
        client = db.query(Client).filter_by(id=client_id).first()
        if client:
            summary['client_name'] = client.display_name

    return summary
