"""FieldServicePro — Main Flask Application."""

import os
import sys
import logging
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, case, text
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, stream_with_context
from flask_login import login_required, current_user
from flask_cors import CORS
from flask_talisman import Talisman

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
# Try multiple paths to find .env (handles different working directories)
for _candidate in [
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'),
    os.path.join(os.getcwd(), '.env'),
]:
    if os.path.exists(_candidate):
        load_dotenv(_candidate)
        break

from models import (
    get_session, init_db,
    User, Organization, Division,
    Client, Property, ClientContact, ClientNote, ClientCommunication,
    Job, JobStatus, JobNote,
    Quote, QuoteItem, QuoteStatus,
    Invoice, InvoiceItem, InvoiceStatus, Payment,
    Technician,
)
from web.auth import auth_bp, login_manager

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger(__name__)

# ---------- App factory ----------
IS_PRODUCTION = os.environ.get('FLASK_ENV') == 'production'

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'fsp-dev-secret-key-change-in-prod')
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION

# Security headers via Talisman (HTTPS redirect, CSP, HSTS)
csp = {
    'default-src': "'self'",
    'script-src': ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net"],
    'style-src': ["'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net", "https://fonts.googleapis.com"],
    'font-src': ["'self'", "https://cdn.jsdelivr.net", "https://fonts.gstatic.com"],
    'img-src': ["'self'", "data:"],
    'connect-src': "'self'",
}
Talisman(
    app,
    force_https=IS_PRODUCTION,
    content_security_policy=csp,
    session_cookie_secure=IS_PRODUCTION,
)

CORS(app, resources={r"/api/*": {"origins": "*" if not IS_PRODUCTION else []}})
login_manager.init_app(app)
app.register_blueprint(auth_bp)

# Make datetime.now available in templates
app.jinja_env.globals['now'] = datetime.now

# Initialize database
with app.app_context():
    init_db()
    # Seed default divisions for new installs
    db = get_session()
    try:
        if db.query(Division).count() == 0:
            org = db.query(Organization).first()
            if org:
                defaults = [
                    Division(organization_id=org.id, name='Plumbing', code='PLB', color='#2563eb', icon='bi-droplet-fill', sort_order=1),
                    Division(organization_id=org.id, name='HVAC', code='HVAC', color='#059669', icon='bi-thermometer-half', sort_order=2),
                    Division(organization_id=org.id, name='Electrical', code='ELEC', color='#f59e0b', icon='bi-lightning-fill', sort_order=3),
                    Division(organization_id=org.id, name='General Contracting', code='GC', color='#8b5cf6', icon='bi-hammer', sort_order=4),
                ]
                db.add_all(defaults)
                db.commit()
    except Exception as e:
        logger.error("Error seeding default divisions: %s", e)
    finally:
        db.close()

logger.info("FieldServicePro app initialized (production=%s)", IS_PRODUCTION)


# ========== HEALTH CHECK (Render uses this) ==========

@app.route('/health')
def health_check():
    """Health check endpoint for Render deploy verification."""
    db = get_session()
    try:
        db.execute(text('SELECT 1'))
        db_status = 'connected'
    except Exception:
        db_status = 'unavailable'
    finally:
        db.close()
    status_code = 200 if db_status == 'connected' else 503
    return jsonify({
        'status': 'healthy' if db_status == 'connected' else 'degraded',
        'database': db_status,
    }), status_code


def get_divisions():
    """Get all active divisions for the current user's org."""
    db = get_session()
    try:
        divisions = db.query(Division).filter_by(
            organization_id=current_user.organization_id,
            is_active=True
        ).order_by(Division.sort_order).all()
        return [d.to_dict() for d in divisions]
    finally:
        db.close()


def get_active_division(request):
    """Get the currently selected division from query param or session."""
    division_id = request.args.get('division')
    return int(division_id) if division_id else None


# ========== DASHBOARD ==========

@app.route('/')
@login_required
def dashboard():
    db = get_session()
    try:
        org_id = current_user.organization_id
        active_div = get_active_division(request)

        # Base queries
        jobs_q = db.query(Job).filter_by(organization_id=org_id)
        quotes_q = db.query(Quote).filter_by(organization_id=org_id)
        invoices_q = db.query(Invoice).filter_by(organization_id=org_id)
        clients_q = db.query(Client).filter_by(organization_id=org_id)

        if active_div:
            jobs_q = jobs_q.filter_by(division_id=active_div)
            quotes_q = quotes_q.filter_by(division_id=active_div)



        # ── Workflow pipeline counts ──
        # Requests = draft jobs (new requests)
        requests_new = jobs_q.filter_by(status='draft').count()
        requests_overdue = jobs_q.filter(
            Job.status == 'draft',
            Job.scheduled_date != None,
            Job.scheduled_date < datetime.now(timezone.utc)
        ).count()

        # Quotes
        quotes_draft = quotes_q.filter_by(status='draft').count()
        quotes_approved = quotes_q.filter_by(status='approved').count()
        quotes_changes = quotes_q.filter_by(status='declined').count()
        quotes_total_value = db.query(func.coalesce(func.sum(Quote.total), 0)).filter(
            Quote.organization_id == org_id, Quote.status == 'draft'
        ).scalar()

        # Jobs
        total_jobs = jobs_q.count()
        active_jobs = jobs_q.filter(Job.status.in_(['scheduled', 'in_progress'])).count()
        completed_jobs = jobs_q.filter_by(status='completed').count()
        jobs_requires_invoicing = jobs_q.filter_by(status='completed').count()
        jobs_action_required = jobs_q.filter(Job.status.in_(['on_hold'])).count()
        jobs_active_value = db.query(func.coalesce(func.sum(Job.estimated_amount), 0)).filter(
            Job.organization_id == org_id,
            Job.status.in_(['scheduled', 'in_progress'])
        ).scalar()
        jobs_action_value = db.query(func.coalesce(func.sum(Job.estimated_amount), 0)).filter(
            Job.organization_id == org_id,
            Job.status == 'on_hold'
        ).scalar()

        # Invoices
        total_quotes = quotes_q.count()
        total_clients = clients_q.count()
        invoices_awaiting = invoices_q.filter(Invoice.status.in_(['sent', 'viewed', 'partial', 'overdue'])).count()
        invoices_draft = invoices_q.filter_by(status='draft').count()
        invoices_past_due = invoices_q.filter_by(status='overdue').count()

        # ── Revenue / Financial ──
        total_invoiced = db.query(func.coalesce(func.sum(Invoice.total), 0)).filter_by(organization_id=org_id).scalar()
        total_outstanding = db.query(func.coalesce(func.sum(Invoice.balance_due), 0)).filter(
            Invoice.organization_id == org_id,
            Invoice.status.in_(['sent', 'viewed', 'partial', 'overdue'])
        ).scalar()
        total_overdue = db.query(func.coalesce(func.sum(Invoice.balance_due), 0)).filter(
            Invoice.organization_id == org_id,
            Invoice.status == 'overdue'
        ).scalar()
        invoices_draft_value = db.query(func.coalesce(func.sum(Invoice.total), 0)).filter(
            Invoice.organization_id == org_id, Invoice.status == 'draft'
        ).scalar()
        invoices_past_due_value = db.query(func.coalesce(func.sum(Invoice.balance_due), 0)).filter(
            Invoice.organization_id == org_id, Invoice.status == 'overdue'
        ).scalar()
        total_paid = db.query(func.coalesce(func.sum(Invoice.amount_paid), 0)).filter_by(organization_id=org_id).scalar()

        # ── Receivables breakdown (top clients who owe) ──
        receivables_clients = db.query(
            Client.id,
            Client.company_name, Client.first_name, Client.last_name, Client.client_type,
            func.sum(Invoice.balance_due).label('balance'),
            func.sum(
                case(
                    (Invoice.status == 'overdue', Invoice.balance_due),
                    else_=0
                )
            ).label('late')
        ).join(Invoice, Invoice.client_id == Client.id).filter(
            Invoice.organization_id == org_id,
            Invoice.status.in_(['sent', 'viewed', 'partial', 'overdue']),
            Invoice.balance_due > 0
        ).group_by(Client.id).order_by(func.sum(Invoice.balance_due).desc()).limit(5).all()

        receivables_count = db.query(func.count(func.distinct(Client.id))).join(
            Invoice, Invoice.client_id == Client.id
        ).filter(
            Invoice.organization_id == org_id,
            Invoice.status.in_(['sent', 'viewed', 'partial', 'overdue']),
            Invoice.balance_due > 0
        ).scalar()

        # ── Today's appointments ──
        today = datetime.now(timezone.utc).date()
        todays_jobs_q = jobs_q.filter(
            Job.scheduled_date != None,
            func.date(Job.scheduled_date) == today
        ).order_by(Job.scheduled_date)
        todays_jobs = todays_jobs_q.all()
        todays_total = db.query(func.coalesce(func.sum(Job.estimated_amount), 0)).filter(
            Job.organization_id == org_id,
            Job.scheduled_date != None,
            func.date(Job.scheduled_date) == today
        ).scalar()
        todays_active_value = db.query(func.coalesce(func.sum(Job.estimated_amount), 0)).filter(
            Job.organization_id == org_id,
            Job.scheduled_date != None,
            func.date(Job.scheduled_date) == today,
            Job.status.in_(['scheduled', 'in_progress'])
        ).scalar()
        todays_completed_value = db.query(func.coalesce(func.sum(Job.estimated_amount), 0)).filter(
            Job.organization_id == org_id,
            Job.scheduled_date != None,
            func.date(Job.scheduled_date) == today,
            Job.status == 'completed'
        ).scalar()
        now_utc = datetime.utcnow()
        todays_overdue_jobs = [j for j in todays_jobs if j.status in ('draft', 'scheduled') and j.scheduled_date and j.scheduled_date < now_utc]

        # ── Upcoming jobs (this week) ──
        week_end = today + timedelta(days=7)
        upcoming_jobs_value = db.query(func.coalesce(func.sum(Job.estimated_amount), 0)).filter(
            Job.organization_id == org_id,
            Job.scheduled_date != None,
            func.date(Job.scheduled_date) >= today,
            func.date(Job.scheduled_date) <= week_end,
            Job.status.in_(['scheduled', 'in_progress', 'draft'])
        ).scalar()

        # Recent jobs
        recent_jobs = jobs_q.order_by(Job.created_at.desc()).limit(10).all()

        return render_template('dashboard.html',
            active_page='dashboard',
            user=current_user,
            divisions=get_divisions(),
            active_division=active_div,
            # Workflow pipeline
            requests_new=requests_new,
            requests_overdue=requests_overdue,
            quotes_draft=quotes_draft,
            quotes_approved=quotes_approved,
            quotes_changes=quotes_changes,
            quotes_total_value=quotes_total_value,
            total_jobs=total_jobs,
            active_jobs=active_jobs,
            completed_jobs=completed_jobs,
            jobs_requires_invoicing=jobs_requires_invoicing,
            jobs_action_required=jobs_action_required,
            jobs_active_value=jobs_active_value,
            jobs_action_value=jobs_action_value,
            invoices_awaiting=invoices_awaiting,
            invoices_draft=invoices_draft,
            invoices_past_due=invoices_past_due,
            invoices_draft_value=invoices_draft_value,
            invoices_past_due_value=invoices_past_due_value,
            # Financial
            total_quotes=total_quotes,
            total_clients=total_clients,
            total_invoiced=total_invoiced,
            total_outstanding=total_outstanding,
            total_overdue=total_overdue,
            total_paid=total_paid,
            # Receivables
            receivables_clients=receivables_clients,
            receivables_count=receivables_count,
            # Today
            todays_jobs=[j.to_dict() for j in todays_jobs],
            todays_total=todays_total,
            todays_active_value=todays_active_value,
            todays_completed_value=todays_completed_value,
            todays_overdue_value=sum(j.estimated_amount or 0 for j in todays_overdue_jobs),
            todays_remaining=todays_active_value - todays_completed_value,
            # Upcoming
            upcoming_jobs_value=upcoming_jobs_value,
            # Recent
            recent_jobs=[j.to_dict() for j in recent_jobs],
        )
    finally:
        db.close()


# ========== JOBS ==========

@app.route('/jobs')
@login_required
def jobs_page():
    db = get_session()
    try:
        org_id = current_user.organization_id
        active_div = get_active_division(request)
        status_filter = request.args.get('status', '')

        q = db.query(Job).filter_by(organization_id=org_id)
        if active_div:
            q = q.filter_by(division_id=active_div)
        if status_filter:
            q = q.filter_by(status=status_filter)

        jobs = q.order_by(Job.created_at.desc()).all()

        # Get related data
        job_list = []
        for job in jobs:
            jd = job.to_dict()
            jd['client_name'] = job.client.display_name if job.client else 'Unknown'
            jd['division_name'] = job.division.name if job.division else ''
            jd['division_color'] = job.division.color if job.division else '#666'
            jd['technician_name'] = job.technician.full_name if job.technician else 'Unassigned'
            jd['property_address'] = job.property.display_address if job.property else ''
            job_list.append(jd)

        # KPI calculations
        now = datetime.now(timezone.utc)
        thirty_days = timedelta(days=30)

        # Build base query for KPIs (same filters as main query)
        kpi_q = db.query(Job).filter_by(organization_id=org_id)
        if active_div:
            kpi_q = kpi_q.filter_by(division_id=active_div)

        jobs_late = kpi_q.filter(
            Job.scheduled_date < now,
            Job.status.notin_(['completed', 'cancelled', 'invoiced'])
        ).count()

        jobs_requires_invoicing = kpi_q.filter(
            Job.status == 'completed'
        ).count()

        jobs_action_required = kpi_q.filter(
            Job.status == 'on_hold'
        ).count()

        jobs_unscheduled = kpi_q.filter(
            Job.scheduled_date.is_(None),
            Job.status.notin_(['completed', 'cancelled', 'invoiced'])
        ).count()

        jobs_ending_soon = kpi_q.filter(
            Job.scheduled_date >= now,
            Job.scheduled_date <= now + thirty_days,
            Job.status.notin_(['completed', 'cancelled', 'invoiced'])
        ).count()

        recent_visits_count = kpi_q.filter(
            Job.status == 'completed',
            Job.updated_at >= now - thirty_days
        ).count()

        visits_scheduled_count = kpi_q.filter(
            Job.status.in_(['scheduled', 'in_progress']),
            Job.scheduled_date >= now
        ).count()

        total_jobs_value = sum(j.get('estimated_amount', 0) or 0 for j in job_list)

        return render_template('jobs.html',
            active_page='jobs',
            user=current_user,
            divisions=get_divisions(),
            active_division=active_div,
            jobs=job_list,
            status_filter=status_filter,
            statuses=[s.value for s in JobStatus],
            jobs_late=jobs_late,
            jobs_requires_invoicing=jobs_requires_invoicing,
            jobs_action_required=jobs_action_required,
            jobs_unscheduled=jobs_unscheduled,
            jobs_ending_soon=jobs_ending_soon,
            recent_visits_count=recent_visits_count,
            visits_scheduled_count=visits_scheduled_count,
            total_jobs_value=total_jobs_value,
        )
    finally:
        db.close()


@app.route('/api/jobs', methods=['POST'])
@login_required
def create_job():
    data = request.get_json()
    db = get_session()
    try:

        max_num = db.query(func.max(Job.id)).filter_by(organization_id=current_user.organization_id).scalar() or 0
        job_number = f"JOB-{max_num + 1:05d}"

        job = Job(
            organization_id=current_user.organization_id,
            division_id=data['division_id'],
            client_id=data['client_id'],
            property_id=data.get('property_id'),
            job_number=job_number,
            title=data['title'],
            description=data.get('description', ''),
            status=data.get('status', 'draft'),
            priority=data.get('priority', 'normal'),
            job_type=data.get('job_type', 'service_call'),
            scheduled_date=datetime.fromisoformat(data['scheduled_date']) if data.get('scheduled_date') else None,
            assigned_technician_id=data.get('technician_id'),
            estimated_amount=float(data.get('estimated_amount', 0)),
            created_by_id=current_user.id,
        )
        db.add(job)
        db.commit()
        return jsonify({'success': True, 'job': job.to_dict()})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        db.close()


@app.route('/jobs/<int:job_id>')
@login_required
def job_detail(job_id):
    db = get_session()
    try:
        org_id = current_user.organization_id
        job = db.query(Job).filter_by(id=job_id, organization_id=org_id).first()
        if not job:
            flash('Job not found', 'error')
            return redirect(url_for('jobs_page'))

        client = job.client
        prop = job.property
        tech = job.technician
        division = job.division
        job_notes = db.query(JobNote).filter_by(job_id=job.id).order_by(JobNote.created_at.desc()).all()
        job_invoices = db.query(Invoice).filter_by(job_id=job.id, organization_id=org_id).order_by(Invoice.created_at.desc()).all()

        total_invoiced = sum(inv.total or 0 for inv in job_invoices)
        total_paid = sum(inv.amount_paid or 0 for inv in job_invoices)
        total_balance = sum(inv.balance_due or 0 for inv in job_invoices)

        total_price = job.estimated_amount or 0
        profit = total_price
        profit_pct = 100 if total_price > 0 else 0

        return render_template('job_detail.html',
            active_page='jobs', user=current_user, divisions=get_divisions(),
            job=job.to_dict(), job_obj=job,
            client=client.to_dict() if client else {},
            client_name=client.display_name if client else 'Unknown',
            property=prop.to_dict() if prop else {},
            property_address=prop.display_address if prop else '',
            technician=tech.to_dict() if tech else {},
            technician_name=tech.full_name if tech else 'Unassigned',
            division=division,
            division_name=division.name if division else '',
            division_color=division.color if division else '#666',
            quote=job.quote.to_dict() if job.quote else None,
            job_notes=[n.to_dict() for n in job_notes],
            job_invoices=[inv.to_dict() for inv in job_invoices],
            total_invoiced=total_invoiced, total_paid=total_paid, total_balance=total_balance,
            total_price=total_price, line_item_cost=0, labour_cost=0, expenses=0,
            profit=profit, profit_pct=profit_pct,
        )
    finally:
        db.close()


@app.route('/api/jobs/<int:job_id>/notes', methods=['POST'])
@login_required
def add_job_note(job_id):
    data = request.get_json()
    db = get_session()
    try:
        note = JobNote(
            job_id=job_id,
            user_id=current_user.id,
            content=data['content'],
        )
        db.add(note)
        db.commit()
        return jsonify({'success': True, 'note': note.to_dict()})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/jobs/<int:job_id>/status', methods=['PUT'])
@login_required
def update_job_status(job_id):
    data = request.get_json()
    db = get_session()
    try:
        job = db.query(Job).filter_by(id=job_id, organization_id=current_user.organization_id).first()
        if not job:
            return jsonify({'success': False, 'error': 'Job not found'}), 404
        job.status = data['status']
        if data['status'] == 'completed':
            job.completed_at = datetime.now(timezone.utc)
        if data['status'] == 'in_progress' and not job.started_at:
            job.started_at = datetime.now(timezone.utc)
        db.commit()
        return jsonify({'success': True, 'job': job.to_dict()})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        db.close()


# ========== QUOTES ==========

@app.route('/quotes')
@login_required
def quotes_page():
    db = get_session()
    try:
        org_id = current_user.organization_id
        active_div = get_active_division(request)

        q = db.query(Quote).filter_by(organization_id=org_id)
        if active_div:
            q = q.filter_by(division_id=active_div)

        quotes = q.order_by(Quote.created_at.desc()).all()

        quote_list = []
        for quote in quotes:
            qd = quote.to_dict()
            qd['client_name'] = quote.client.display_name if quote.client else 'Unknown'
            qd['division_name'] = quote.division.name if quote.division else ''
            qd['division_color'] = quote.division.color if quote.division else '#666'
            quote_list.append(qd)

        return render_template('quotes.html',
            active_page='quotes',
            user=current_user,
            divisions=get_divisions(),
            active_division=active_div,
            quotes=quote_list,
            statuses=[s.value for s in QuoteStatus],
        )
    finally:
        db.close()


@app.route('/quotes/new')
@login_required
def quote_new_page():
    db = get_session()
    try:
        org_id = current_user.organization_id
        max_num = db.query(func.max(Quote.id)).filter_by(organization_id=org_id).scalar() or 0
        next_quote_number = f"QTE-{max_num + 1:05d}"
        return render_template('quote_new.html',
            active_page='quotes',
            user=current_user,
            divisions=get_divisions(),
            next_quote_number=next_quote_number,
        )
    finally:
        db.close()


@app.route('/api/clients/search')
@login_required
def search_clients():
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify({'clients': []})
    db = get_session()
    try:
        org_id = current_user.organization_id
        search = f"%{q}%"
        clients = db.query(Client).filter(
            Client.organization_id == org_id,
            Client.is_active == True,
            (Client.company_name.ilike(search) |
             Client.first_name.ilike(search) |
             Client.last_name.ilike(search) |
             Client.email.ilike(search))
        ).limit(10).all()
        return jsonify({'clients': [c.to_dict() for c in clients]})
    finally:
        db.close()


@app.route('/api/quotes', methods=['POST'])
@login_required
def create_quote():
    data = request.get_json()
    db = get_session()
    try:

        max_num = db.query(func.max(Quote.id)).filter_by(organization_id=current_user.organization_id).scalar() or 0
        quote_number = f"QTE-{max_num + 1:05d}"

        quote = Quote(
            organization_id=current_user.organization_id,
            division_id=data['division_id'],
            client_id=data['client_id'],
            property_id=data.get('property_id'),
            quote_number=quote_number,
            title=data['title'],
            description=data.get('description', ''),
            template_name=data.get('template_name'),
            created_by_id=current_user.id,
        )
        db.add(quote)
        db.flush()

        # Add line items
        subtotal = 0
        for i, item_data in enumerate(data.get('items', [])):
            item_total = float(item_data.get('quantity', 1)) * float(item_data.get('unit_price', 0))
            item = QuoteItem(
                quote_id=quote.id,
                description=item_data['description'],
                quantity=float(item_data.get('quantity', 1)),
                unit_price=float(item_data.get('unit_price', 0)),
                total=item_total,
                sort_order=i,
            )
            db.add(item)
            subtotal += item_total

        discount = float(data.get('discount', 0))
        quote.subtotal = subtotal
        quote.discount = discount
        after_discount = max(0, subtotal - discount)
        quote.tax_amount = after_discount * (quote.tax_rate / 100)
        quote.total = after_discount + quote.tax_amount
        if data.get('status'):
            quote.status = data['status']
        if data.get('notes'):
            quote.notes = data['notes']
        db.commit()
        return jsonify({'success': True, 'quote': quote.to_dict()})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        db.close()


# ========== CLIENTS ==========

@app.route('/clients')
@login_required
def clients_page():
    db = get_session()
    try:
        org_id = current_user.organization_id
        client_type = request.args.get('type', '')

        q = db.query(Client).filter_by(organization_id=org_id, is_active=True)
        if client_type:
            q = q.filter_by(client_type=client_type)

        clients = q.order_by(Client.company_name, Client.last_name).all()

        return render_template('clients.html',
            active_page='clients',
            user=current_user,
            divisions=get_divisions(),
            clients=[c.to_dict() for c in clients],
            client_type_filter=client_type,
        )
    finally:
        db.close()


@app.route('/clients/<int:client_id>')
@login_required
def client_detail(client_id):
    db = get_session()
    try:

        org_id = current_user.organization_id
        division_filter = request.args.get('division')
        division_filter = int(division_filter) if division_filter else None

        client = db.query(Client).filter_by(id=client_id, organization_id=org_id).first()
        if not client:
            flash('Client not found', 'error')
            return redirect(url_for('clients_page'))

        # Properties
        properties = [p.to_dict() for p in client.properties if p.is_active]

        # Contacts
        contacts = [c.to_dict() for c in client.contacts]

        # Base queries filtered to this client
        jobs_q = db.query(Job).filter_by(client_id=client_id)
        quotes_q = db.query(Quote).filter_by(client_id=client_id)
        invoices_q = db.query(Invoice).filter_by(client_id=client_id)

        if division_filter:
            jobs_q = jobs_q.filter_by(division_id=division_filter)
            quotes_q = quotes_q.filter_by(division_id=division_filter)

        # Active work: scheduled or in_progress
        active_jobs = jobs_q.filter(Job.status.in_(['scheduled', 'in_progress'])).order_by(Job.scheduled_date).all()
        # Needs attention: draft or on_hold
        needs_attention_jobs = jobs_q.filter(Job.status.in_(['draft', 'on_hold'])).order_by(Job.created_at.desc()).all()
        # Completed / past jobs
        completed_jobs = jobs_q.filter(Job.status.in_(['completed', 'invoiced'])).order_by(Job.completed_at.desc()).all()
        # All jobs for the "All Jobs" tab
        all_jobs = jobs_q.order_by(Job.created_at.desc()).all()

        def enrich_job(job):
            jd = job.to_dict()
            jd['division_name'] = job.division.name if job.division else ''
            jd['division_color'] = job.division.color if job.division else '#666'
            jd['technician_name'] = job.technician.full_name if job.technician else 'Unassigned'
            jd['property_address'] = job.property.display_address if job.property else ''
            return jd

        # Quotes
        quotes = quotes_q.order_by(Quote.created_at.desc()).all()
        quote_list = []
        for q in quotes:
            qd = q.to_dict()
            qd['division_name'] = q.division.name if q.division else ''
            qd['division_color'] = q.division.color if q.division else '#666'
            quote_list.append(qd)

        # Invoices
        invoices = invoices_q.order_by(Invoice.created_at.desc()).all()
        inv_list = [inv.to_dict() for inv in invoices]

        # Financial summary
        total_invoiced = db.query(func.coalesce(func.sum(Invoice.total), 0)).filter_by(client_id=client_id).scalar()
        total_outstanding = db.query(func.coalesce(func.sum(Invoice.balance_due), 0)).filter(
            Invoice.client_id == client_id,
            Invoice.status.in_(['sent', 'viewed', 'partial', 'overdue'])
        ).scalar()

        # Division list for this client's jobs (for filter pills)
        client_division_ids = db.query(Job.division_id).filter_by(client_id=client_id).distinct().all()
        from models import Division
        client_divisions = db.query(Division).filter(
            Division.id.in_([d[0] for d in client_division_ids if d[0]])
        ).order_by(Division.sort_order).all()

        # Client notes (starred first, then by date)
        notes = db.query(ClientNote).filter_by(client_id=client_id).order_by(
            ClientNote.is_starred.desc(), ClientNote.created_at.desc()
        ).all()
        note_list = []
        for note in notes:
            nd = note.to_dict()
            author = db.query(User).filter_by(id=note.user_id).first() if note.user_id else None
            nd['author_name'] = author.full_name if author else 'System'
            nd['author_initials'] = (
                (author.first_name[0] + (author.last_name[0] if author.last_name else ''))
                if author and author.first_name else '?'
            ).upper()
            note_list.append(nd)

        # Communications log
        comms = db.query(ClientCommunication).filter_by(client_id=client_id).order_by(
            ClientCommunication.created_at.desc()
        ).limit(50).all()
        comm_list = []
        for comm in comms:
            cd = comm.to_dict()
            author = db.query(User).filter_by(id=comm.user_id).first() if comm.user_id else None
            cd['author_name'] = author.full_name if author else 'System'
            comm_list.append(cd)

        # Communication stats
        comm_total = db.query(func.count(ClientCommunication.id)).filter_by(client_id=client_id).scalar()
        comm_sent = db.query(func.count(ClientCommunication.id)).filter(
            ClientCommunication.client_id == client_id,
            ClientCommunication.status.in_(['sent', 'delivered', 'opened'])
        ).scalar()
        comm_opened = db.query(func.count(ClientCommunication.id)).filter_by(client_id=client_id, status='opened').scalar()

        # Billing history (last 10 invoices for sidebar)
        billing_history = invoices_q.order_by(Invoice.created_at.desc()).limit(10).all()
        billing_list = [inv.to_dict() for inv in billing_history]

        return render_template('client_detail.html',
            active_page='clients',
            user=current_user,
            divisions=get_divisions(),
            client=client.to_dict(),
            client_obj=client,
            properties=properties,
            contacts=contacts,
            active_jobs=[enrich_job(j) for j in active_jobs],
            needs_attention_jobs=[enrich_job(j) for j in needs_attention_jobs],
            completed_jobs=[enrich_job(j) for j in completed_jobs],
            all_jobs=[enrich_job(j) for j in all_jobs],
            quotes=quote_list,
            invoices=inv_list,
            total_invoiced=total_invoiced,
            total_outstanding=total_outstanding,
            client_divisions=[d.to_dict() for d in client_divisions],
            active_division=division_filter,
            client_notes=note_list,
            communications=comm_list,
            comm_total=comm_total,
            comm_sent=comm_sent,
            comm_opened=comm_opened,
            billing_history=billing_list,
        )
    finally:
        db.close()


@app.route('/clients/new')
@login_required
def client_new_page():
    return render_template('client_new.html',
        active_page='clients',
        user=current_user,
        divisions=get_divisions(),
    )


@app.route('/api/clients/new', methods=['POST'])
@login_required
def create_client_full():
    """Create a client + property from the full-page form."""
    db = get_session()
    try:
        # Build client
        client = Client(
            organization_id=current_user.organization_id,
            client_type=request.form.get('client_type', 'commercial'),
            company_name=request.form.get('company_name') or None,
            first_name=request.form.get('first_name') or None,
            last_name=request.form.get('last_name') or None,
            email=request.form.get('email') or None,
            phone=request.form.get('phone') or None,
            notes=request.form.get('title_prefix') or None,
        )

        # Billing address
        billing_same = request.form.get('billing_same') == 'on'
        if billing_same:
            client.billing_address = request.form.get('street1', '')
            street2 = request.form.get('street2', '')
            if street2:
                client.billing_address += ', ' + street2
            client.billing_city = request.form.get('city') or None
            client.billing_province = request.form.get('province', 'Ontario')
            client.billing_postal_code = request.form.get('postal_code') or None
        else:
            client.billing_address = request.form.get('billing_street1', '')
            billing_street2 = request.form.get('billing_street2', '')
            if billing_street2:
                client.billing_address += ', ' + billing_street2
            client.billing_city = request.form.get('billing_city') or None
            client.billing_province = request.form.get('billing_province', 'Ontario')
            client.billing_postal_code = request.form.get('billing_postal_code') or None

        db.add(client)
        db.flush()

        # Build property
        street1 = request.form.get('street1', '').strip()
        if street1:
            address = street1
            street2 = request.form.get('street2', '').strip()
            if street2:
                address += ', ' + street2

            # Custom property fields stored as structured text in notes
            custom_fields = []
            for label, key in [
                ('Billing Dept Contact', 'billing_dept_contact'),
                ('Site Super', 'site_super'),
                ('Buzzer Code', 'buzzer_code'),
                ('Property Owner', 'property_owner'),
                ('Property Manager', 'property_manager'),
            ]:
                val = request.form.get(key, '').strip()
                if val:
                    custom_fields.append(f"{label}: {val}")
            prop_notes = '\n'.join(custom_fields) if custom_fields else None

            prop = Property(
                client_id=client.id,
                name=request.form.get('company_name') or f"{request.form.get('first_name', '')} {request.form.get('last_name', '')}".strip(),
                address=address,
                city=request.form.get('city') or None,
                province=request.form.get('province', 'Ontario'),
                postal_code=request.form.get('postal_code') or None,
                property_type=request.form.get('client_type', 'commercial'),
                notes=prop_notes,
            )
            db.add(prop)

        db.commit()

        if request.form.get('action') == 'save_and_new':
            flash('Client created successfully.', 'success')
            return redirect(url_for('client_new_page'))

        return redirect(url_for('client_detail', client_id=client.id))
    except Exception as e:
        db.rollback()
        logger.error("Error creating client: %s", e)
        flash(f'Error creating client: {e}', 'error')
        return redirect(url_for('client_new_page'))
    finally:
        db.close()


@app.route('/api/clients', methods=['POST'])
@login_required
def create_client():
    data = request.get_json()
    db = get_session()
    try:
        client = Client(
            organization_id=current_user.organization_id,
            client_type=data.get('client_type', 'commercial'),
            company_name=data.get('company_name'),
            first_name=data.get('first_name'),
            last_name=data.get('last_name'),
            email=data.get('email'),
            phone=data.get('phone'),
            billing_address=data.get('billing_address'),
            billing_city=data.get('billing_city'),
            billing_province=data.get('billing_province', 'Ontario'),
            billing_postal_code=data.get('billing_postal_code'),
            notes=data.get('notes'),
        )
        db.add(client)
        db.commit()
        return jsonify({'success': True, 'client': client.to_dict()})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/clients/<int:client_id>/properties', methods=['POST'])
@login_required
def add_property(client_id):
    data = request.get_json()
    db = get_session()
    try:
        prop = Property(
            client_id=client_id,
            name=data.get('name'),
            address=data['address'],
            city=data.get('city'),
            province=data.get('province', 'Ontario'),
            postal_code=data.get('postal_code'),
            unit_number=data.get('unit_number'),
            property_type=data.get('property_type'),
            notes=data.get('notes'),
        )
        db.add(prop)
        db.commit()
        return jsonify({'success': True, 'property': prop.to_dict()})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        db.close()


# ========== CLIENT NOTES ==========

@app.route('/api/clients/<int:client_id>/notes', methods=['POST'])
@login_required
def create_client_note(client_id):
    data = request.get_json()
    db = get_session()
    try:
        note = ClientNote(
            client_id=client_id,
            user_id=current_user.id,
            content=data['content'],
        )
        db.add(note)
        db.commit()
        nd = note.to_dict()
        nd['author_name'] = current_user.full_name
        nd['author_initials'] = (
            current_user.first_name[0] + (current_user.last_name[0] if current_user.last_name else '')
        ).upper() if current_user.first_name else '?'
        return jsonify({'success': True, 'note': nd})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/clients/<int:client_id>/notes/<int:note_id>/star', methods=['PUT'])
@login_required
def toggle_note_star(client_id, note_id):
    db = get_session()
    try:
        note = db.query(ClientNote).filter_by(id=note_id, client_id=client_id).first()
        if not note:
            return jsonify({'success': False, 'error': 'Note not found'}), 404
        note.is_starred = not note.is_starred
        db.commit()
        return jsonify({'success': True, 'is_starred': note.is_starred})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        db.close()


@app.route('/api/clients/<int:client_id>/notes/<int:note_id>', methods=['DELETE'])
@login_required
def delete_client_note(client_id, note_id):
    db = get_session()
    try:
        note = db.query(ClientNote).filter_by(id=note_id, client_id=client_id).first()
        if not note:
            return jsonify({'success': False, 'error': 'Note not found'}), 404
        db.delete(note)
        db.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        db.close()


# ========== CLIENT COMMUNICATIONS ==========

@app.route('/api/clients/<int:client_id>/communications', methods=['POST'])
@login_required
def log_communication(client_id):
    data = request.get_json()
    db = get_session()
    try:
        comm = ClientCommunication(
            client_id=client_id,
            user_id=current_user.id,
            comm_type=data.get('comm_type', 'email'),
            direction=data.get('direction', 'outbound'),
            subject=data.get('subject'),
            body=data.get('body'),
            recipient_email=data.get('recipient_email'),
            status=data.get('status', 'sent'),
            related_job_id=data.get('related_job_id'),
            related_invoice_id=data.get('related_invoice_id'),
            sent_at=datetime.now(timezone.utc) if data.get('status') != 'draft' else None,
        )
        db.add(comm)
        db.commit()
        cd = comm.to_dict()
        cd['author_name'] = current_user.full_name
        return jsonify({'success': True, 'communication': cd})
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        db.close()


# ========== INVOICES ==========

@app.route('/invoices')
@login_required
def invoices_page():
    db = get_session()
    try:
        org_id = current_user.organization_id
        status_filter = request.args.get('status', '')

        q = db.query(Invoice).filter_by(organization_id=org_id)
        if status_filter:
            q = q.filter_by(status=status_filter)

        invoices = q.order_by(Invoice.created_at.desc()).all()

        # Existing KPIs
        total_outstanding = db.query(func.coalesce(func.sum(Invoice.balance_due), 0)).filter(
            Invoice.organization_id == org_id,
            Invoice.status.in_(['sent', 'viewed', 'partial', 'overdue'])
        ).scalar()
        total_overdue = db.query(func.coalesce(func.sum(Invoice.balance_due), 0)).filter(
            Invoice.organization_id == org_id,
            Invoice.status == 'overdue'
        ).scalar()

        # Overview card counts & values
        invoices_past_due_count = db.query(func.count(Invoice.id)).filter(
            Invoice.organization_id == org_id,
            Invoice.status == 'overdue'
        ).scalar() or 0
        invoices_past_due_value = float(total_overdue or 0)

        invoices_draft_count = db.query(func.count(Invoice.id)).filter(
            Invoice.organization_id == org_id,
            Invoice.status == 'draft'
        ).scalar() or 0
        invoices_draft_value = db.query(func.coalesce(func.sum(Invoice.total), 0)).filter(
            Invoice.organization_id == org_id,
            Invoice.status == 'draft'
        ).scalar() or 0

        invoices_sent_count = db.query(func.count(Invoice.id)).filter(
            Invoice.organization_id == org_id,
            Invoice.status.in_(['sent', 'viewed'])
        ).scalar() or 0
        invoices_sent_value = db.query(func.coalesce(func.sum(Invoice.balance_due), 0)).filter(
            Invoice.organization_id == org_id,
            Invoice.status.in_(['sent', 'viewed'])
        ).scalar() or 0

        # Past-30-day metrics
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        sixty_days_ago = datetime.utcnow() - timedelta(days=60)

        invoices_issued_30d = db.query(func.count(Invoice.id)).filter(
            Invoice.organization_id == org_id,
            Invoice.issued_date >= thirty_days_ago
        ).scalar() or 0

        total_invoiced_30d = db.query(func.coalesce(func.sum(Invoice.total), 0)).filter(
            Invoice.organization_id == org_id,
            Invoice.issued_date >= thirty_days_ago
        ).scalar() or 0

        avg_invoice_30d = db.query(func.coalesce(func.avg(Invoice.total), 0)).filter(
            Invoice.organization_id == org_id,
            Invoice.issued_date >= thirty_days_ago
        ).scalar() or 0

        # Previous 30-day period for % change
        invoices_issued_prev = db.query(func.count(Invoice.id)).filter(
            Invoice.organization_id == org_id,
            Invoice.issued_date >= sixty_days_ago,
            Invoice.issued_date < thirty_days_ago
        ).scalar() or 0
        avg_invoice_prev = db.query(func.coalesce(func.avg(Invoice.total), 0)).filter(
            Invoice.organization_id == org_id,
            Invoice.issued_date >= sixty_days_ago,
            Invoice.issued_date < thirty_days_ago
        ).scalar() or 0

        issued_pct_change = 0
        if invoices_issued_prev > 0:
            issued_pct_change = round(((invoices_issued_30d - invoices_issued_prev) / invoices_issued_prev) * 100)
        avg_pct_change = 0
        if avg_invoice_prev > 0:
            avg_pct_change = round(((avg_invoice_30d - avg_invoice_prev) / avg_invoice_prev) * 100)

        # Payment time stats (median approximation & average) for paid invoices
        paid_invoices = db.query(Invoice).filter(
            Invoice.organization_id == org_id,
            Invoice.status == 'paid',
            Invoice.paid_date != None,
            Invoice.issued_date != None
        ).all()
        payment_days = sorted([
            (inv.paid_date - inv.issued_date).days
            for inv in paid_invoices
            if inv.paid_date and inv.issued_date
        ])
        if payment_days:
            mid = len(payment_days) // 2
            median_payment_days = payment_days[mid] if len(payment_days) % 2 else round((payment_days[mid - 1] + payment_days[mid]) / 2)
            avg_payment_days = round(sum(payment_days) / len(payment_days))
        else:
            median_payment_days = 0
            avg_payment_days = 0

        inv_list = []
        for inv in invoices:
            d = inv.to_dict()
            d['client_name'] = inv.client.display_name if inv.client else 'Unknown'
            d['subject'] = inv.job.title if inv.job else (inv.notes[:60] if inv.notes else '')
            inv_list.append(d)

        return render_template('invoices.html',
            active_page='invoices',
            user=current_user,
            divisions=get_divisions(),
            invoices=inv_list,
            total_outstanding=total_outstanding,
            total_overdue=total_overdue,
            status_filter=status_filter,
            statuses=[s.value for s in InvoiceStatus],
            invoices_past_due_count=invoices_past_due_count,
            invoices_past_due_value=invoices_past_due_value,
            invoices_draft_count=invoices_draft_count,
            invoices_draft_value=float(invoices_draft_value),
            invoices_sent_count=invoices_sent_count,
            invoices_sent_value=float(invoices_sent_value),
            invoices_issued_30d=invoices_issued_30d,
            total_invoiced_30d=float(total_invoiced_30d),
            avg_invoice_30d=float(avg_invoice_30d),
            issued_pct_change=issued_pct_change,
            avg_pct_change=avg_pct_change,
            median_payment_days=median_payment_days,
            avg_payment_days=avg_payment_days,
        )
    finally:
        db.close()


@app.route('/invoices/new')
@login_required
def invoice_new():
    """Client selector page for creating a new invoice (Jobber-style)."""
    db = get_session()
    try:
        org_id = current_user.organization_id
        clients = (
            db.query(Client)
            .filter_by(organization_id=org_id, is_active=True)
            .order_by(Client.updated_at.desc().nullslast(), Client.created_at.desc())
            .all()
        )
        # Pre-compute property counts and last activity for template
        now = datetime.now(timezone.utc)
        client_data = []
        for c in clients:
            prop_count = len(c.properties) if c.properties else 0
            last_activity = c.updated_at or c.created_at
            if last_activity:
                delta = now - last_activity.replace(tzinfo=timezone.utc) if last_activity.tzinfo is None else now - last_activity
                days_ago = max(delta.days, 0)
            else:
                days_ago = None
            client_data.append({
                'id': c.id,
                'display_name': c.display_name,
                'client_type': c.client_type,
                'company_name': c.company_name,
                'phone': c.phone,
                'property_count': prop_count,
                'days_ago': days_ago,
            })
        return render_template('invoice_new.html', clients=client_data)
    finally:
        db.close()


@app.route('/invoices/<int:invoice_id>')
@login_required
def invoice_detail(invoice_id):
    db = get_session()
    try:
        org_id = current_user.organization_id
        inv = db.query(Invoice).filter_by(id=invoice_id, organization_id=org_id).first()
        if not inv:
            flash('Invoice not found', 'error')
            return redirect(url_for('invoices_page'))

        client = inv.client
        prop = None
        property_address = ''
        if inv.job and inv.job.property:
            prop = inv.job.property
            property_address = prop.display_address

        items = db.query(InvoiceItem).filter_by(invoice_id=inv.id).order_by(InvoiceItem.sort_order).all()

        return render_template('invoice_detail.html',
            active_page='invoices', user=current_user, divisions=get_divisions(),
            invoice=inv.to_dict(),
            client=client.to_dict() if client else {},
            client_name=client.display_name if client else 'Unknown',
            property_address=property_address,
            invoice_items=[item.to_dict() for item in items],
        )
    finally:
        db.close()


# ========== SCHEDULE ==========

@app.route('/schedule')
@login_required
def schedule_page():
    db = get_session()
    try:
        org_id = current_user.organization_id
        active_div = get_active_division(request)

        base_q = db.query(Job).filter(
            Job.organization_id == org_id,
            Job.status.in_(['draft', 'scheduled', 'in_progress'])
        )
        if active_div:
            base_q = base_q.filter_by(division_id=active_div)

        # Scheduled jobs
        scheduled_jobs = base_q.filter(
            Job.scheduled_date != None
        ).order_by(Job.scheduled_date).all()

        # Unscheduled jobs
        unscheduled_jobs = base_q.filter(
            Job.scheduled_date == None
        ).order_by(Job.created_at.desc()).all()

        def job_to_event(job):
            prop = job.property
            location = ''
            if prop:
                parts = [p for p in [prop.address, prop.city, prop.province, prop.postal_code] if p]
                location = ', '.join(parts)
            return {
                'id': job.id,
                'title': job.title,
                'job_number': job.job_number or '',
                'start': job.scheduled_date.isoformat() if job.scheduled_date else None,
                'end': job.scheduled_end.isoformat() if job.scheduled_end else None,
                'status': job.status,
                'priority': job.priority or 'normal',
                'job_type': job.job_type or '',
                'technician': job.technician.full_name if job.technician else 'Unassigned',
                'client': job.client.display_name if job.client else '',
                'division': job.division.name if job.division else '',
                'color': job.division.color if job.division else '#2563eb',
                'location': location,
                'estimated_amount': job.estimated_amount or 0,
            }

        events = [job_to_event(j) for j in scheduled_jobs]
        unscheduled = [job_to_event(j) for j in unscheduled_jobs]

        technicians = db.query(Technician).filter_by(
            organization_id=org_id, is_active=True
        ).all()

        return render_template('schedule.html',
            active_page='schedule',
            user=current_user,
            divisions=get_divisions(),
            active_division=active_div,
            events=events,
            unscheduled=unscheduled,
            technicians=[t.to_dict() for t in technicians],
            events_json=events,
            unscheduled_json=unscheduled,
        )
    finally:
        db.close()


# ========== SETTINGS ==========

@app.route('/settings')
@login_required
def settings_page():
    db = get_session()
    try:
        org = db.query(Organization).filter_by(id=current_user.organization_id).first()
        divisions = db.query(Division).filter_by(organization_id=current_user.organization_id).order_by(Division.sort_order).all()
        technicians = db.query(Technician).filter_by(organization_id=current_user.organization_id).all()

        return render_template('settings.html',
            active_page='settings',
            user=current_user,
            divisions=get_divisions(),
            organization=org.to_dict() if org else {},
            all_divisions=[d.to_dict() for d in divisions],
            technicians=[t.to_dict() for t in technicians],
        )
    finally:
        db.close()


# ========== API: Lookup data for forms ==========

@app.route('/api/lookup/clients')
@login_required
def lookup_clients():
    db = get_session()
    try:
        clients = db.query(Client).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Client.company_name, Client.last_name).all()
        return jsonify([c.to_dict() for c in clients])
    finally:
        db.close()


@app.route('/api/lookup/properties/<int:client_id>')
@login_required
def lookup_properties(client_id):
    db = get_session()
    try:
        props = db.query(Property).filter_by(client_id=client_id, is_active=True).all()
        return jsonify([p.to_dict() for p in props])
    finally:
        db.close()


@app.route('/api/lookup/technicians')
@login_required
def lookup_technicians():
    db = get_session()
    try:
        division_id = request.args.get('division_id')
        q = db.query(Technician).filter_by(
            organization_id=current_user.organization_id, is_active=True
        )
        if division_id:
            q = q.filter_by(division_id=division_id)
        techs = q.all()
        return jsonify([t.to_dict() for t in techs])
    finally:
        db.close()


# ========== AI CHAT ==========

# Lazy-init chat engine (only when API key is present)
_chat_engine = None

def get_chat_engine():
    global _chat_engine
    if _chat_engine is None:
        from src.ai_core.chat_engine import ChatEngine
        _chat_engine = ChatEngine()
    return _chat_engine


@app.route('/api/chat', methods=['POST'])
@login_required
def chat_api():
    """AI chat endpoint with streaming support."""
    import json
    data = request.get_json()
    message = data.get('message', '').strip()
    client_id = data.get('client_id')
    mode = data.get('mode', 'general')
    session_id = data.get('session_id', f"user-{current_user.id}")

    if not message:
        return jsonify({'error': 'Message is required'}), 400

    # Check for API key
    if not os.environ.get('ANTHROPIC_API_KEY'):
        return jsonify({'error': 'ANTHROPIC_API_KEY not configured. Set it in your environment to enable AI chat.'}), 503

    db = get_session()
    try:
        from src.ai_core.context_builder import build_global_context, build_client_context
        from src.ai_core.chat_engine import ConversationMode

        # Build context
        org_id = current_user.organization_id
        context = build_global_context(db, org_id)
        if client_id:
            context += "\n\n" + build_client_context(db, int(client_id))

        # Map mode string to enum
        mode_map = {m.value: m for m in ConversationMode}
        conv_mode = mode_map.get(mode, ConversationMode.GENERAL)

        engine = get_chat_engine()

        # Stream response
        def generate():
            try:
                for chunk in engine.chat_stream(session_id, message, context, conv_mode):
                    yield f"data: {json.dumps({'text': chunk})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"

        return Response(
            stream_with_context(generate()),
            mimetype='text/event-stream',
            headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'}
        )
    finally:
        db.close()


@app.route('/api/chat/suggestions', methods=['GET'])
@login_required
def chat_suggestions():
    """Get context-aware suggested prompts."""
    client_id = request.args.get('client_id')
    db = get_session()
    try:
        from src.ai_core.context_builder import get_context_summary
        from src.ai_core.chat_engine import ChatEngine

        summary = get_context_summary(db, current_user.organization_id, client_id)
        engine = ChatEngine.__new__(ChatEngine)
        engine.sessions = {}
        prompts = engine.get_suggested_prompts(summary)
        return jsonify({'suggestions': prompts})
    except Exception:
        return jsonify({'suggestions': [
            "Give me a summary of our business this month",
            "Which clients have overdue invoices?",
            "What jobs are scheduled for this week?",
        ]})
    finally:
        db.close()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 58391))
    import webbrowser, threading
    threading.Timer(1.5, lambda: webbrowser.open(f'http://127.0.0.1:{port}')).start()
    app.run(debug=True, port=port)
