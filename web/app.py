"""FieldServicePro — Main Flask Application."""

import os
import sys
import logging
from datetime import datetime, date, timezone, timedelta
from sqlalchemy import func, case, text
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, Response, stream_with_context, session, g, abort, send_from_directory
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
    SLA, PriorityLevel,
    Contract, ContractLineItem, ContractActivityLog, ContractAttachment,
    ContractType, ContractStatus, BillingFrequency, ServiceFrequency,
)
from web.auth import auth_bp, login_manager
from web.routes.sla_routes import sla_bp
from web.routes.contract_routes import contract_bp
from web.utils.sla_engine import (
    detect_contract_for_job, detect_sla_for_job,
    apply_sla_to_job, handle_job_status_change,
)
from web.cli_commands import automation_cli, recurring_cli, warranty_cli, notif_cli, project_mgmt_cli
from web.routes.po_routes import po_bp
from web.routes.phase_routes import phases_bp
from web.routes.change_order_routes import change_orders_bp
from web.routes.document_routes import documents_bp
from web.routes.permit_routes import permits_bp
from web.routes.insurance_routes import insurance_bp
from web.routes.certification_routes import certifications_bp
from web.routes.checklist_routes import checklists_bp
from web.routes.lien_waiver_routes import lien_waivers_bp
from web.portal_auth import portal_auth_bp
from web.routes.portal_routes import portal_bp
from web.routes.portal_admin_routes import portal_admin_bp
from web.routes.request_routes import requests_bp
from web.routes.payment_routes import payments_bp
from web.routes.schedule_routes import schedule_api_bp
from web.routes.equipment_routes import equipment_bp
from web.routes.project_routes import projects_bp
from web.routes.time_tracking_routes import time_tracking_bp
from web.routes.parts_routes import parts_bp
from web.routes.inventory_routes import inventory_bp
from web.routes.transfer_routes import transfers_bp
from web.routes.materials_routes import materials_bp
from web.routes.truck_stock_routes import truck_bp
from web.routes.parts_report_routes import parts_reports_bp
from web.routes.recurring_routes import recurring_bp
from web.routes.warranty_routes import warranty_bp
from web.routes.callback_routes import callback_bp
from web.routes.warranty_report_routes import warranty_reports_bp
from web.routes.communication_routes import communications_bp
from web.routes.comm_template_routes import comm_templates_bp
from web.routes.comm_report_routes import comm_reports_bp
from web.routes.expense_routes import expense_bp
from web.routes.notification_routes import notifications_bp
from web.routes.vehicle_routes import vehicle_bp
from web.routes.payroll_routes import payroll_bp
from web.routes.rfi_routes import rfi_bp
from web.routes.submittal_routes import submittal_bp
from web.routes.punch_list_routes import punch_list_bp
from web.routes.daily_log_routes import daily_log_bp
from web.routes.reports_routes import reports_bp
from web.routes.vendor_routes import vendor_bp
from web.routes.supplier_po_routes import supplier_po_bp
from web.routes.mobile import mobile_bp
from web.routes.booking_routes import booking_bp
from web.routes.feedback_routes import feedback_bp
from web.routes.advanced_reports_routes import advanced_reports_bp

# ---------- Logging ----------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
)
logger = logging.getLogger(__name__)

# ---------- App factory ----------
IS_PRODUCTION = os.environ.get('FLASK_ENV') == 'production'

app = Flask(__name__)
SECRET_KEY = os.environ.get('SECRET_KEY')
if IS_PRODUCTION and not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY env var is required in production. "
        "Set it in the Render dashboard before deploying."
    )
app.secret_key = SECRET_KEY or 'fsp-dev-secret-key-change-in-prod'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = IS_PRODUCTION

# Belt-and-suspenders: never expose the Werkzeug debugger in production,
# even if a stray FLASK_DEBUG env var or future code change tries to enable it.
if IS_PRODUCTION:
    app.config['DEBUG'] = False
    app.config['PROPAGATE_EXCEPTIONS'] = False
    app.config['TRAP_HTTP_EXCEPTIONS'] = False

# File upload config
app.config['UPLOAD_FOLDER'] = os.environ.get(
    'UPLOAD_FOLDER', os.path.join(app.instance_path, 'uploads'))
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
app.config['MAX_CONTENT_LENGTH'] = 25 * 1024 * 1024  # 25MB

# Email config (Flask-Mail, optional — portal emails degrade gracefully if unconfigured)
app.config.setdefault('MAIL_SERVER', os.environ.get('MAIL_SERVER', 'localhost'))
app.config.setdefault('MAIL_PORT', int(os.environ.get('MAIL_PORT', 587)))
app.config.setdefault('MAIL_USE_TLS', os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true')
app.config.setdefault('MAIL_USERNAME', os.environ.get('MAIL_USERNAME'))
app.config.setdefault('MAIL_PASSWORD', os.environ.get('MAIL_PASSWORD'))
app.config.setdefault('MAIL_DEFAULT_SENDER', os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@fieldservicepro.com'))
app.config.setdefault('MAIL_USE_SSL', os.environ.get('MAIL_USE_SSL', 'false').lower() == 'true')

# Initialize Flask-Mail (optional — degrades gracefully)
try:
    from flask_mail import Mail
    mail = Mail(app)
except ImportError:
    mail = None
    logger.info("flask-mail not installed — email features will use console fallback")

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
app.register_blueprint(sla_bp)
app.register_blueprint(contract_bp)
app.register_blueprint(automation_cli)
app.register_blueprint(recurring_cli)
app.register_blueprint(notif_cli)
app.register_blueprint(project_mgmt_cli)
app.register_blueprint(warranty_cli)
app.register_blueprint(po_bp)
app.register_blueprint(phases_bp)
app.register_blueprint(change_orders_bp)
app.register_blueprint(documents_bp)
app.register_blueprint(permits_bp)
app.register_blueprint(insurance_bp)
app.register_blueprint(certifications_bp)
app.register_blueprint(checklists_bp)
app.register_blueprint(lien_waivers_bp)
app.register_blueprint(portal_auth_bp)
app.register_blueprint(portal_bp)
app.register_blueprint(portal_admin_bp)
app.register_blueprint(requests_bp)
app.register_blueprint(payments_bp)
app.register_blueprint(schedule_api_bp)
app.register_blueprint(equipment_bp)
app.register_blueprint(projects_bp)
app.register_blueprint(time_tracking_bp)
app.register_blueprint(parts_bp)
app.register_blueprint(inventory_bp)
app.register_blueprint(transfers_bp)
app.register_blueprint(materials_bp)
app.register_blueprint(truck_bp)
app.register_blueprint(parts_reports_bp)
app.register_blueprint(recurring_bp)
app.register_blueprint(warranty_bp)
app.register_blueprint(callback_bp)
app.register_blueprint(warranty_reports_bp)
app.register_blueprint(communications_bp)
app.register_blueprint(comm_templates_bp)
app.register_blueprint(comm_reports_bp)
app.register_blueprint(expense_bp)
app.register_blueprint(notifications_bp)
app.register_blueprint(vehicle_bp)
app.register_blueprint(payroll_bp)
app.register_blueprint(rfi_bp)
app.register_blueprint(submittal_bp)
app.register_blueprint(punch_list_bp)
app.register_blueprint(daily_log_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(vendor_bp)
app.register_blueprint(supplier_po_bp)
app.register_blueprint(mobile_bp)
app.register_blueprint(booking_bp)
app.register_blueprint(feedback_bp)
app.register_blueprint(advanced_reports_bp)


@app.before_request
def block_portal_from_internal():
    """Prevent portal users from accessing internal routes."""
    from flask import session as flask_session
    if flask_session.get('portal_user_id') and request.endpoint:
        # Allow portal routes and static files
        if (request.endpoint
            and not request.endpoint.startswith('portal')
            and request.endpoint != 'static'):
            abort(403)


# Make datetime.now available in templates
app.jinja_env.globals['now'] = datetime.now
app.jinja_env.globals['now_utc'] = datetime.utcnow


@app.template_filter('format_number')
def format_number_filter(value):
    """Format integers with comma separators: 42500 -> 42,500"""
    try:
        return f'{int(value):,}'
    except (TypeError, ValueError):
        return str(value) if value is not None else '0'


@app.template_filter('unread_notification_count')
def unread_notification_count_filter(user):
    """Template filter: {{ current_user | unread_notification_count }}"""
    try:
        from models.notification import Notification
        db = get_session()
        count = db.query(Notification).filter_by(recipient_id=user.id, is_read=False).count()
        db.close()
        return count
    except Exception:
        return 0


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


# ── Lightweight automation on request (runs at most once per hour) ──
@app.before_request
def run_background_checks():
    """Run contract expiry and SLA breach checks periodically."""
    _last_run_key = '_automation_last_run'
    now = datetime.utcnow()
    last_run = getattr(app, _last_run_key, None)
    if last_run is None or (now - last_run) > timedelta(hours=1):
        setattr(app, _last_run_key, now)
        try:
            from web.utils.contract_automation import (
                check_expired_contracts, check_sla_breaches
            )
            db = get_session()
            check_expired_contracts(db)
            check_sla_breaches(db)
            db.close()
        except Exception:
            pass  # Never let automation errors break normal requests


# ── Mobile detection middleware ──
@app.before_request
def mobile_detection():
    """Detect mobile UA and set banner/preference flags."""
    from web.routes.mobile.middleware import should_show_mobile_banner, is_mobile_ua
    g.show_mobile_banner = False
    g.is_mobile = False
    if request.path.startswith('/static') or request.path.startswith('/auth'):
        return
    g.is_mobile = is_mobile_ua()
    if current_user.is_authenticated and should_show_mobile_banner():
        g.show_mobile_banner = True


@app.route('/set-mobile-pref')
def set_mobile_pref():
    """Set/clear mobile view preferences."""
    pref = request.args.get('pref', 'mobile')
    next_url = request.args.get('next', '/')
    if pref == 'mobile':
        session.pop('force_desktop', None)
        session['force_mobile'] = True
        return redirect(url_for('mobile.dashboard'))
    elif pref == 'desktop':
        session.pop('force_mobile', None)
        session['force_desktop'] = True
        session['mobile_banner_dismissed'] = True
        return redirect(next_url)
    elif pref == 'dismiss':
        session['mobile_banner_dismissed'] = True
        return redirect(next_url)
    return redirect(next_url)


# ── Mobile notification count context processor ──
@app.context_processor
def mobile_context():
    """Inject mobile-specific context variables."""
    notification_count = 0
    if current_user.is_authenticated:
        try:
            from models.notification import Notification
            db = get_session()
            notification_count = db.query(Notification).filter_by(
                recipient_id=current_user.id, is_read=False
            ).count()
            db.close()
        except Exception:
            pass
    return dict(notification_count=notification_count)


# ── Context processor: pending approval badge count ──
@app.context_processor
def inject_approval_count():
    count = 0
    if current_user.is_authenticated and current_user.role in ('owner', 'admin'):
        try:
            db = get_session()
            count = db.query(Invoice).filter(
                Invoice.organization_id == current_user.organization_id,
                Invoice.approval_status == 'pending'
            ).count()
            db.close()
        except Exception:
            pass
    # Pending CO count
    co_count = 0
    if current_user.is_authenticated and current_user.role in ('owner', 'admin', 'dispatcher'):
        try:
            from models.change_order import ChangeOrder
            db2 = get_session()
            co_count = db2.query(ChangeOrder).join(Job).filter(
                Job.organization_id == current_user.organization_id,
                ChangeOrder.status.in_(['submitted', 'pending_approval'])
            ).count()
            db2.close()
        except Exception:
            pass

    # New service request count
    new_request_count = 0
    if current_user.is_authenticated:
        try:
            from models.service_request import ServiceRequest
            db3 = get_session()
            new_request_count = db3.query(ServiceRequest).filter_by(
                organization_id=current_user.organization_id, status='new'
            ).count()
            db3.close()
        except Exception:
            pass

    # Active project count
    active_project_count = 0
    if current_user.is_authenticated:
        try:
            from models.project import Project
            db4 = get_session()
            active_project_count = db4.query(Project).filter_by(
                organization_id=current_user.organization_id, status='active'
            ).count()
            db4.close()
        except Exception:
            pass

    # Permission helpers for templates
    from web.utils.permissions import (
        can_manage_phase, can_approve_change_order,
        can_edit_change_order, can_create_change_order_fn,
    )
    return {
        'pending_approval_count': count,
        'pending_co_count': co_count,
        'new_request_count': new_request_count,
        'active_project_count': active_project_count,
        'pending_time_approvals': _get_pending_time_approvals(),
        'low_stock_count': _get_low_stock_count(),
        'recurring_alert_count': _get_recurring_alert_count(),
        'warranty_expiring_count': _get_warranty_expiring_count(),
        'open_callbacks_count': _get_open_callbacks_count(),
        'overdue_followups_count': _get_overdue_followups_count(),
        'pending_expenses_count': _get_pending_expenses_count(),
        'g_unread_notif_count': _get_unread_notif_count(),
        'open_rfi_count': _get_open_rfi_count(),
        'pending_sub_count': _get_pending_sub_count(),
        'pending_spo_count': _get_pending_spo_count(),
        'feedback_badge_count': _get_feedback_badge_count(),
        'all_clients': _get_all_clients_for_quicklog(),
        'comm_templates': _get_comm_templates_for_quicklog(),
        'can_manage_phase': can_manage_phase,
        'can_approve_change_order': can_approve_change_order,
        'can_edit_change_order': can_edit_change_order,
        'can_create_change_order_fn': can_create_change_order_fn,
    }


def _get_pending_time_approvals():
    """Get count of pending time entry approvals."""
    try:
        if current_user.is_authenticated and current_user.role in ('owner', 'admin'):
            from models.time_entry import TimeEntry
            db5 = get_session()
            count = db5.query(TimeEntry).filter_by(status='submitted').count()
            db5.close()
            return count
    except Exception:
        pass
    return 0


def _get_low_stock_count():
    """Get count of low-stock parts for sidebar badge."""
    try:
        if current_user.is_authenticated:
            from web.utils.parts_utils import get_low_stock_count
            db6 = get_session()
            count = get_low_stock_count(db6, current_user.organization_id)
            db6.close()
            return count
    except Exception:
        pass
    return 0


def _get_warranty_expiring_count():
    try:
        if current_user.is_authenticated:
            from sqlalchemy import func as _func
            from models.warranty import Warranty
            db8 = get_session()
            count = db8.query(_func.count(Warranty.id)).filter(Warranty.status == 'expiring_soon').scalar() or 0
            db8.close()
            return count
    except Exception:
        pass
    return 0


def _get_open_callbacks_count():
    try:
        if current_user.is_authenticated:
            from sqlalchemy import func as _func
            from models.callback import Callback
            db9 = get_session()
            count = db9.query(_func.count(Callback.id)).filter(
                Callback.status.notin_(['resolved', 'closed'])
            ).scalar() or 0
            db9.close()
            return count
    except Exception:
        pass
    return 0


def _get_pending_expenses_count():
    try:
        if current_user.is_authenticated and current_user.role in ('owner', 'admin'):
            from models.expense import Expense
            from sqlalchemy import func as _f
            db_pe = get_session()
            count = db_pe.query(_f.count(Expense.id)).filter(Expense.status == 'submitted').scalar() or 0
            db_pe.close()
            return count
    except Exception:
        pass
    return 0


def _get_unread_notif_count():
    try:
        if current_user.is_authenticated:
            from web.utils.notification_service import NotificationService
            return NotificationService.get_unread_count(current_user.id)
    except Exception:
        pass
    return 0


def _get_open_rfi_count():
    try:
        if current_user.is_authenticated:
            from models.rfi import RFI
            db = get_session()
            count = db.query(RFI).filter(RFI.status.in_(['open', 'pending_response'])).count()
            db.close()
            return count
    except Exception:
        pass
    return 0


def _get_pending_sub_count():
    try:
        if current_user.is_authenticated:
            from models.submittal import Submittal
            db = get_session()
            count = db.query(Submittal).filter(Submittal.status.in_(['submitted', 'under_review'])).count()
            db.close()
            return count
    except Exception:
        pass
    return 0


def _get_pending_spo_count():
    try:
        if current_user.is_authenticated and current_user.role in ('owner', 'admin', 'dispatcher'):
            from models.supplier_po import SupplierPurchaseOrder
            db = get_session()
            count = db.query(SupplierPurchaseOrder).filter(
                SupplierPurchaseOrder.status.in_(['submitted', 'acknowledged', 'partially_received'])
            ).count()
            db.close()
            return count
    except Exception:
        pass
    return 0


def _get_feedback_badge_count():
    """Count negative feedback needing follow-up."""
    try:
        if current_user.is_authenticated and current_user.role in ('owner', 'admin', 'dispatcher'):
            from models.feedback_survey import FeedbackSurvey
            db = get_session()
            count = db.query(FeedbackSurvey).filter(
                FeedbackSurvey.follow_up_required == True,
                FeedbackSurvey.follow_up_completed == False,
                FeedbackSurvey.status == 'completed',
            ).count()
            db.close()
            return count
    except Exception:
        pass
    return 0


def _get_client_communications(db, client_id):
    try:
        from models.communication import CommunicationLog
        return db.query(CommunicationLog).filter_by(client_id=client_id).order_by(CommunicationLog.communication_date.desc()).limit(20).all()
    except Exception:
        return []


def _count_client_communications(db, client_id):
    try:
        from models.communication import CommunicationLog
        from sqlalchemy import func as _f
        return db.query(_f.count(CommunicationLog.id)).filter_by(client_id=client_id).scalar() or 0
    except Exception:
        return 0


def _get_all_clients_for_quicklog():
    try:
        if current_user.is_authenticated:
            from models.client import Client as _Client
            db_ql = get_session()
            clients = db_ql.query(_Client).filter_by(organization_id=current_user.organization_id).order_by(_Client.company_name).all()
            db_ql.close()
            return clients
    except Exception:
        pass
    return []


def _get_comm_templates_for_quicklog():
    try:
        if current_user.is_authenticated:
            from models.communication import CommunicationTemplate as _CT
            db_ct = get_session()
            templates = db_ct.query(_CT).filter_by(is_active=True).order_by(_CT.name).all()
            db_ct.close()
            return templates
    except Exception:
        pass
    return []


def _get_overdue_followups_count():
    try:
        if current_user.is_authenticated:
            from web.utils.communication_utils import get_overdue_follow_up_count
            db10 = get_session()
            count = get_overdue_follow_up_count(db10)
            db10.close()
            return count
    except Exception:
        pass
    return 0


def _get_comm_overdue_for_dashboard(db):
    try:
        from models.communication import CommunicationLog
        return db.query(CommunicationLog).filter(
            CommunicationLog.follow_up_required == True,
            CommunicationLog.follow_up_completed == False,
            CommunicationLog.follow_up_date < date.today()
        ).count()
    except Exception:
        return 0


def _get_comm_due_today_for_dashboard(db):
    try:
        from models.communication import CommunicationLog
        return db.query(CommunicationLog).filter(
            CommunicationLog.follow_up_required == True,
            CommunicationLog.follow_up_completed == False,
            CommunicationLog.follow_up_date == date.today()
        ).count()
    except Exception:
        return 0


def _get_pm_dashboard_stats(db):
    """Project management stats for the dashboard."""
    try:
        from models.rfi import RFI
        from models.submittal import Submittal
        from models.punch_list import PunchList
        from models.daily_log import DailyLog
        today_date = date.today()

        open_rfis = db.query(RFI).filter(RFI.status.in_(['open', 'pending_response'])).count()
        overdue_rfis = db.query(RFI).filter(
            RFI.status.notin_(['answered', 'closed', 'void']),
            RFI.date_required != None, RFI.date_required < today_date,
        ).count()
        pending_submittals = db.query(Submittal).filter(
            Submittal.status.in_(['submitted', 'under_review'])
        ).count()
        active_pls = db.query(PunchList).filter(
            PunchList.status.in_(['active', 'in_progress'])
        ).all()
        avg_complete = round(sum(pl.percent_complete for pl in active_pls) / len(active_pls)) if active_pls else None
        logs_today = db.query(DailyLog).filter_by(log_date=today_date).count()

        return {
            'open_rfis': open_rfis, 'overdue_rfis': overdue_rfis,
            'pending_submittals': pending_submittals,
            'active_punch_lists': len(active_pls),
            'punch_list_avg_complete': avg_complete,
            'logs_today': logs_today,
        }
    except Exception:
        return {'open_rfis': 0, 'overdue_rfis': 0, 'pending_submittals': 0,
                'active_punch_lists': 0, 'punch_list_avg_complete': None, 'logs_today': 0}


def _get_warranty_dashboard_stats(db):
    try:
        from web.utils.warranty_utils import get_warranty_stats
        return get_warranty_stats(db)
    except Exception:
        return {'total_active': 0, 'expiring_soon': 0, 'expired_this_month': 0, 'claims_this_month': 0}


def _get_callback_dashboard_stats(db):
    try:
        from web.utils.callback_utils import get_callback_stats
        return get_callback_stats(db, current_user.organization_id)
    except Exception:
        return {'open_callbacks': 0, 'resolved_this_month': 0, 'callback_rate': 0, 'recent_callbacks': 0}


def _get_recurring_alert_count():
    """Get count of overdue + due-soon recurring schedules for sidebar badge."""
    try:
        if current_user.is_authenticated and current_user.role in ('owner', 'admin', 'dispatcher'):
            from web.utils.recurring_engine import get_dashboard_summary
            db7 = get_session()
            summary = get_dashboard_summary(db7, current_user.organization_id)
            db7.close()
            return summary.get('alert_count', 0)
    except Exception:
        pass
    return 0


# ========== HEALTH CHECK (Render uses this) ==========

@app.route('/robots.txt')
def robots_txt():
    """Serve robots.txt at the conventional top-level URL."""
    return send_from_directory(app.static_folder, 'robots.txt', mimetype='text/plain')


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


@app.errorhandler(403)
def forbidden(e):
    return render_template('errors/403.html',
                           active_page='', user=current_user,
                           divisions=[]), 403


@app.errorhandler(404)
def not_found(e):
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Not found'}), 404
    flash('Page not found.', 'warning')
    return redirect(url_for('dashboard'))


@app.errorhandler(500)
def server_error(e):
    """Branded 500 page. Logs full stack trace to stdout for Render log search."""
    logger.exception("Internal server error: %s", e)
    if request.path.startswith('/api/'):
        return jsonify({'error': 'Internal server error'}), 500
    return render_template('errors/500.html',
                           active_page='', user=current_user,
                           divisions=[]), 500


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

        # ── Contract & SLA dashboard widgets ──
        in_30_days = today + timedelta(days=30)
        expiring_contracts = (db.query(Contract)
                               .filter(
                                   Contract.organization_id == org_id,
                                   Contract.status == ContractStatus.active,
                                   Contract.end_date >= today,
                                   Contract.end_date <= in_30_days
                               )
                               .order_by(Contract.end_date.asc())
                               .limit(5)
                               .all())

        from web.utils.sla_engine import get_sla_alert_jobs
        sla_alert_jobs = get_sla_alert_jobs(db, limit=5)

        month_ago = datetime.utcnow() - timedelta(days=30)
        sla_jobs_month = (db.query(Job)
                            .filter(
                                Job.organization_id == org_id,
                                Job.sla_id.isnot(None),
                                Job.actual_resolution_time.isnot(None),
                                Job.actual_resolution_time >= month_ago
                            )
                            .all())
        sla_perf_pct = None
        if sla_jobs_month:
            met_count = sum(1 for j in sla_jobs_month if j.sla_resolution_met)
            sla_perf_pct = round(met_count / len(sla_jobs_month) * 100, 1)

        # ── Commercial dashboard widgets ──
        # AR Summary
        outstanding_invs = db.query(Invoice).filter(
            Invoice.organization_id == org_id,
            Invoice.status.in_(['sent', 'overdue', 'partial'])
        ).all()
        total_ar = sum(float(inv.balance_due or 0) for inv in outstanding_invs)
        overdue_amount = sum(float(inv.balance_due or 0) for inv in outstanding_invs if inv.days_overdue > 0)

        # Avg days to payment (paid invoices last 90 days)
        ninety_ago = datetime.utcnow() - timedelta(days=90)
        paid_invs = db.query(Invoice).filter(
            Invoice.organization_id == org_id,
            Invoice.status == 'paid',
            Invoice.updated_at >= ninety_ago,
            Invoice.due_date.isnot(None),
        ).all()
        avg_days_to_payment = 0
        if paid_invs:
            def _days_to_pay(inv):
                if not inv.updated_at or not inv.issued_date:
                    return 0
                end = inv.updated_at.date() if hasattr(inv.updated_at, 'date') else inv.updated_at
                start = inv.issued_date.date() if hasattr(inv.issued_date, 'date') else inv.issued_date
                return max(0, (end - start).days)
            avg_days_to_payment = round(
                sum(_days_to_pay(inv) for inv in paid_invs) / len(paid_invs), 1
            )

        # Pending approvals
        pending_approvals = db.query(Invoice).filter(
            Invoice.organization_id == org_id,
            Invoice.approval_status == 'pending'
        ).count()

        # Expiring POs
        from models.purchase_order import PurchaseOrder
        soon_30 = today + timedelta(days=30)
        expiring_pos = db.query(PurchaseOrder).filter(
            PurchaseOrder.organization_id == org_id,
            PurchaseOrder.status == 'active',
            PurchaseOrder.expiry_date.isnot(None),
            PurchaseOrder.expiry_date >= today,
            PurchaseOrder.expiry_date <= soon_30,
        ).order_by(PurchaseOrder.expiry_date).all()

        # ── Compliance alerts ──
        compliance_alerts = []
        try:
            from web.utils.compliance_checks import get_all_compliance_alerts
            compliance_alerts = get_all_compliance_alerts(db)
        except Exception:
            pass

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
            # Contracts & SLA widgets
            expiring_contracts=expiring_contracts,
            sla_alert_jobs=sla_alert_jobs,
            sla_perf_pct=sla_perf_pct,
            sla_jobs_count=len(sla_jobs_month),
            # Commercial widgets
            total_ar=total_ar,
            overdue_amount=overdue_amount,
            avg_days_to_payment=avg_days_to_payment,
            pending_approvals=pending_approvals,
            expiring_pos=expiring_pos,
            compliance_alerts=compliance_alerts,
            warranty_stats=_get_warranty_dashboard_stats(db),
            callback_stats=_get_callback_dashboard_stats(db),
            comm_overdue_count=_get_comm_overdue_for_dashboard(db),
            comm_due_today_count=_get_comm_due_today_for_dashboard(db),
            pm_stats=_get_pm_dashboard_stats(db),
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

        # Project filter
        project_filter = request.args.get('project_filter', '')
        if project_filter == 'has_project':
            q = q.filter(Job.project_id.isnot(None))
        elif project_filter == 'standalone':
            q = q.filter(Job.project_id.is_(None))

        jobs = q.order_by(Job.created_at.desc()).all()

        # Get related data
        job_list = []
        for job in jobs:
            jd = job.to_dict()
            jd['client_name'] = job.client.display_name if job.client else 'Unknown'
            jd['project_number'] = job.project.project_number if job.project else None
            jd['project_id'] = job.project_id
            jd['division_name'] = job.division.name if job.division else ''
            jd['division_color'] = job.division.color if job.division else '#666'
            jd['technician_name'] = job.technician.full_name if job.technician else 'Unassigned'
            jd['property_address'] = job.property.display_address if job.property else ''
            jd['contract_number'] = job.contract.contract_number if job.contract else None
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
        # Callback handling
        if data.get('is_callback') and data.get('original_job_id'):
            job.is_callback = True
            job.original_job_id = int(data['original_job_id'])
            # Check if original job has warranty
            from models.warranty import Warranty as _Warranty
            orig_warranty = db.query(_Warranty).filter(
                _Warranty.job_id == int(data['original_job_id']),
                _Warranty.status.in_(['active', 'expiring_soon']),
            ).first()
            if orig_warranty:
                job.is_warranty_work = True

        db.add(job)
        db.flush()

        # SLA Integration: auto-detect contract and apply SLA deadlines
        manual_contract_id = data.get('contract_id')
        if manual_contract_id:
            contract = db.query(Contract).filter_by(id=int(manual_contract_id)).first()
        else:
            contract = detect_contract_for_job(db, data['client_id'],
                                                data.get('property_id'))
        if contract:
            sla = detect_sla_for_job(contract, data.get('priority', 'normal'))
            apply_sla_to_job(job, contract, sla, created_at=job.created_at)

        # Auto-create callback record if this is a callback job
        if job.is_callback and job.original_job_id:
            from models.callback import Callback
            from web.utils.callback_utils import generate_callback_number
            cb = Callback(
                callback_number=generate_callback_number(db),
                original_job_id=job.original_job_id,
                callback_job_id=job.id,
                client_id=job.client_id,
                reason='other',
                description=f'Callback for job {job.original_job_id}',
                severity='minor',
                is_warranty=job.is_warranty_work,
                reported_date=date.today(),
                status='reported',
                created_by=current_user.id,
            )
            db.add(cb)

        db.commit()

        # Notification triggers
        try:
            from web.utils.notification_service import NotificationService
            NotificationService.notify('job_created', job, triggered_by=current_user)
            if job.assigned_technician_id and job.scheduled_date:
                NotificationService.notify('job_scheduled', job, triggered_by=current_user)
        except Exception:
            pass

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

        # SLA visibility: technicians only see SLA on their own jobs
        show_sla_details = True
        if current_user.role == 'technician':
            tech_id = getattr(current_user, 'technician_id', None)
            if not tech_id or job.assigned_technician_id != tech_id:
                show_sla_details = False

        # Financial summary for job
        financial_summary = {
            'invoiced_total': total_invoiced,
            'remaining': float(job.current_contract_value) - total_invoiced,
        }

        # Activity log
        activity_log = []
        for phase in job.phases:
            activity_log.append({
                'timestamp': phase.updated_at,
                'title': f'Phase {phase.phase_number} -- {phase.status_label}',
                'description': phase.completion_notes or phase.title,
                'icon': 'layers', 'type_class': 'primary',
                'actor': phase.assigned_technician.full_name if phase.assigned_technician else None,
            })
        for co in job.change_orders:
            activity_log.append({
                'timestamp': co.created_at,
                'title': f'Change Order {co.change_order_number}',
                'description': f'{co.title} -- {co.status_label}',
                'icon': 'file-diff', 'type_class': 'warning',
                'actor': co.created_by.full_name if co.created_by else None,
            })
        activity_log.append({
            'timestamp': job.created_at,
            'title': 'Job Created', 'description': job.title,
            'icon': 'plus-circle', 'type_class': 'success', 'actor': None,
        })
        activity_log = sorted(
            [e for e in activity_log if e['timestamp']],
            key=lambda x: x['timestamp'], reverse=True
        )

        active_tab = request.args.get('tab', 'overview')
        can_edit_phases = current_user.role in ('owner', 'admin', 'dispatcher')

        # Compliance data
        from web.utils.compliance_checks import get_job_compliance_status
        from models.permit import Permit
        from models.checklist import CompletedChecklist
        from models.lien_waiver import LienWaiver
        compliance_status = get_job_compliance_status(db, job.id)
        job_permits = db.query(Permit).filter_by(job_id=job.id).order_by(Permit.created_at.desc()).all()
        job_checklists = db.query(CompletedChecklist).filter_by(job_id=job.id).order_by(
            CompletedChecklist.completed_at.desc()).all()
        job_lien_waivers = db.query(LienWaiver).filter_by(job_id=job.id).order_by(
            LienWaiver.created_at.desc()).all()
        from web.utils.file_utils import get_entity_documents
        job_documents = get_entity_documents(db, 'job', job.id,
                                              include_confidential=current_user.role in ('owner', 'admin'))

        # Materials data
        from models.job_material import JobMaterial
        from models.inventory import InventoryLocation
        from web.utils.materials_utils import get_job_material_summary
        job_materials = db.query(JobMaterial).filter_by(job_id=job.id).order_by(JobMaterial.added_at.desc()).all()
        material_summary = get_job_material_summary(db, job.id)
        inv_locations = db.query(InventoryLocation).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(InventoryLocation.name).all()
        job_phases = job.phases if job.is_multi_phase else []

        # Cost breakdown
        from web.utils.job_costing import get_job_cost_breakdown
        cost_breakdown = get_job_cost_breakdown(db, job)

        return render_template('job_detail.html',
            active_page='jobs', user=current_user, divisions=get_divisions(),
            job=job.to_dict(), job_obj=job, show_sla_details=show_sla_details,
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
            financial_summary=financial_summary,
            activity_log=activity_log,
            active_tab=active_tab,
            can_edit_phases=can_edit_phases,
            compliance_status=compliance_status,
            job_permits=job_permits,
            job_checklists=job_checklists,
            job_lien_waivers=job_lien_waivers,
            job_documents=job_documents,
            job_materials=job_materials,
            material_summary=material_summary,
            inv_locations=inv_locations,
            job_phases=job_phases,
            can_admin=current_user.role in ('owner', 'admin'),
            cost_breakdown=cost_breakdown,
            job_communications=_get_job_communications(db, job.id),
            job_comm_count=_count_job_communications(db, job.id),
        )
    finally:
        db.close()


def _get_job_communications(db, job_id):
    try:
        from models.communication import CommunicationLog
        return db.query(CommunicationLog).filter_by(job_id=job_id).order_by(CommunicationLog.communication_date.desc()).all()
    except Exception:
        return []


def _count_job_communications(db, job_id):
    try:
        from models.communication import CommunicationLog
        from sqlalchemy import func as _f
        return db.query(_f.count(CommunicationLog.id)).filter_by(job_id=job_id).scalar() or 0
    except Exception:
        return 0


@app.route('/jobs/<int:job_id>/pm-notes', methods=['POST'])
@login_required
def update_pm_notes(job_id):
    """Save project manager notes for a job."""
    if current_user.role not in ('owner', 'admin', 'dispatcher'):
        abort(403)
    db = get_session()
    try:
        job = db.query(Job).filter_by(id=job_id, organization_id=current_user.organization_id).first()
        if not job:
            abort(404)
        job.project_manager_notes = request.form.get('project_manager_notes', '')
        db.commit()
        flash('PM notes saved.', 'success')
    finally:
        db.close()
    return redirect(url_for('job_detail', job_id=job_id))


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
        new_status = data['status']
        override = data.get('compliance_override', False)

        # Compliance gates
        if not override:
            from web.utils.compliance_checks import check_job_can_start, check_job_can_complete
            warnings = []
            if new_status == 'in_progress':
                ok, warnings = check_job_can_start(db, job.id)
            elif new_status == 'completed':
                ok, warnings = check_job_can_complete(db, job.id)

            if warnings:
                can_override = current_user.role in ('owner', 'admin')
                return jsonify({
                    'success': False,
                    'compliance_warnings': warnings,
                    'can_override': can_override,
                    'error': 'Compliance warnings must be resolved or overridden.',
                }), 409

        # SLA tracking: record response/resolution times on status transitions
        if job.sla_id:
            handle_job_status_change(job, new_status)
        else:
            job.status = new_status
        if new_status == 'completed':
            job.completed_at = datetime.now(timezone.utc)
        if new_status == 'in_progress' and not job.started_at:
            job.started_at = datetime.now(timezone.utc)
        db.commit()

        # Notification triggers
        try:
            from web.utils.notification_service import NotificationService
            NotificationService.notify('job_status_changed', job, triggered_by=current_user,
                                       extra_context={'status': new_status})
            if new_status == 'completed':
                NotificationService.notify('job_completed', job, triggered_by=current_user)
            elif new_status == 'on_hold':
                NotificationService.notify('job_on_hold', job, triggered_by=current_user)
        except Exception:
            pass

        # Check if we should prompt for warranty on completion
        prompt_warranty = False
        if new_status == 'completed':
            from models.warranty import Warranty
            has_warranty = db.query(Warranty).filter_by(job_id=job_id).first()
            if not has_warranty:
                prompt_warranty = True

        return jsonify({'success': True, 'job': job.to_dict(), 'prompt_warranty': prompt_warranty})
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

        status_filter = request.args.get('status', '')

        q = db.query(Quote).filter_by(organization_id=org_id)
        if active_div:
            q = q.filter_by(division_id=active_div)
        if status_filter:
            q = q.filter_by(status=status_filter)

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
            status_filter=status_filter,
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

        # Notification: quote sent
        if data.get('status') == 'sent':
            try:
                from web.utils.notification_service import NotificationService
                NotificationService.notify('quote_sent', quote, triggered_by=current_user)
            except Exception:
                pass

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

        # Contracts for this client
        client_contracts = db.query(Contract).filter_by(client_id=client_id)\
                             .order_by(Contract.status, Contract.start_date.desc()).all()

        # SLA compliance for this client
        client_jobs_with_sla = db.query(Job).filter(
            Job.client_id == client_id,
            Job.sla_id.isnot(None),
            Job.actual_resolution_time.isnot(None)
        ).all()
        sla_compliance_pct = None
        if client_jobs_with_sla:
            met = sum(1 for j in client_jobs_with_sla if j.sla_resolution_met)
            sla_compliance_pct = round(met / len(client_jobs_with_sla) * 100, 1)

        # Purchase Orders for this client
        from models.purchase_order import PurchaseOrder
        client_pos = db.query(PurchaseOrder).filter_by(client_id=client_id)\
                       .order_by(PurchaseOrder.created_at.desc()).all()

        # Aging snapshot
        outstanding_invs = db.query(Invoice).filter(
            Invoice.client_id == client_id,
            Invoice.organization_id == org_id,
            Invoice.status.in_(['sent', 'overdue', 'partial']),
        ).all()
        aging = {'current': 0.0, 'days_1_30': 0.0, 'days_31_60': 0.0,
                 'days_61_90': 0.0, 'days_90_plus': 0.0, 'total': 0.0}
        for inv in outstanding_invs:
            bal = float(inv.balance_due or 0)
            if bal <= 0:
                continue
            bucket = inv.aging_bucket
            col = {'current': 'current', '1_30': 'days_1_30', '31_60': 'days_31_60',
                   '61_90': 'days_61_90', '90_plus': 'days_90_plus'}.get(bucket, 'current')
            aging[col] += bal
            aging['total'] += bal

        credit_available = None
        if client.credit_limit:
            credit_available = float(client.credit_limit) - aging['total']

        today_date = date.today()
        if today_date.month == 1:
            default_stmt_start = date(today_date.year - 1, 12, 1)
        else:
            default_stmt_start = date(today_date.year, today_date.month - 1, 1)

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
            contracts=client_contracts,
            sla_compliance_pct=sla_compliance_pct,
            purchase_orders=client_pos,
            aging=aging,
            credit_available=credit_available,
            today=today_date,
            default_stmt_start=default_stmt_start,
            default_stmt_end=today_date,
            client_projects=client.projects if hasattr(client, 'projects') else [],
            active_warranties=client.warranties if hasattr(client, 'warranties') else [],
            client_callbacks=client.callbacks if hasattr(client, 'callbacks') else [],
            client_communications=_get_client_communications(db, client_id),
            client_comm_count=_count_client_communications(db, client_id),
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


# ========== Client Statements ==========

@app.route('/clients/<int:client_id>/statement')
@login_required
def client_statement(client_id):
    """Generate statement for a single client."""
    if current_user.role == 'technician':
        abort(403)
    db = get_session()
    try:
        org_id = current_user.organization_id
        client = db.query(Client).filter_by(id=client_id, organization_id=org_id).first()
        if not client:
            flash('Client not found', 'error')
            return redirect(url_for('clients_page'))

        today = date.today()

        # Default to previous month
        if today.month == 1:
            def_start = date(today.year - 1, 12, 1)
        else:
            def_start = date(today.year, today.month - 1, 1)
        def_end = date(today.year, today.month, 1) - timedelta(days=1)

        start_str = request.args.get('start_date', def_start.isoformat())
        end_str = request.args.get('end_date', def_end.isoformat())
        try:
            start_date = date.fromisoformat(start_str)
            end_date = date.fromisoformat(end_str)
        except ValueError:
            flash('Invalid date range.', 'danger')
            return redirect(url_for('client_detail', client_id=client_id))

        # Invoices in period
        invoices_in_period = db.query(Invoice).filter(
            Invoice.client_id == client_id,
            Invoice.organization_id == org_id,
            Invoice.issued_date >= datetime.combine(start_date, datetime.min.time()),
            Invoice.issued_date <= datetime.combine(end_date, datetime.max.time()),
            Invoice.status != 'void',
        ).order_by(Invoice.issued_date).all()

        # Opening balance
        prior_invoices = db.query(Invoice).filter(
            Invoice.client_id == client_id,
            Invoice.organization_id == org_id,
            Invoice.issued_date < datetime.combine(start_date, datetime.min.time()),
            Invoice.status.in_(['sent', 'overdue', 'partial']),
        ).all()
        opening_balance = sum(float(inv.balance_due or 0) for inv in prior_invoices)

        # Payments in period
        payments_in_period = db.query(Payment).join(Invoice).filter(
            Invoice.client_id == client_id,
            Invoice.organization_id == org_id,
            Payment.payment_date >= datetime.combine(start_date, datetime.min.time()),
            Payment.payment_date <= datetime.combine(end_date, datetime.max.time()),
        ).order_by(Payment.payment_date).all()

        new_charges = sum(float(inv.total or 0) for inv in invoices_in_period)
        payments_rcvd = sum(float(p.amount or 0) for p in payments_in_period)
        closing_balance = opening_balance + new_charges - payments_rcvd

        # Aging summary
        outstanding = db.query(Invoice).filter(
            Invoice.client_id == client_id,
            Invoice.organization_id == org_id,
            Invoice.status.in_(['sent', 'overdue', 'partial']),
        ).all()
        aging = {'current': 0.0, 'days_1_30': 0.0, 'days_31_60': 0.0,
                 'days_61_90': 0.0, 'days_90_plus': 0.0, 'total': 0.0}
        for inv in outstanding:
            bal = float(inv.balance_due or 0)
            if bal <= 0:
                continue
            bucket = inv.aging_bucket
            col = {'current': 'current', '1_30': 'days_1_30', '31_60': 'days_31_60',
                   '61_90': 'days_61_90', '90_plus': 'days_90_plus'}.get(bucket, 'current')
            aging[col] += bal
            aging['total'] += bal

        from models.settings import OrganizationSettings
        settings = OrganizationSettings.get_or_create(db, org_id)

        ctx = dict(
            client=client, start_date=start_date, end_date=end_date,
            invoices=invoices_in_period, payments=payments_in_period,
            opening_balance=opening_balance, new_charges=new_charges,
            payments_received=payments_rcvd, closing_balance=closing_balance,
            aging=aging, today=today, settings=settings,
            active_page='clients', user=current_user, divisions=get_divisions(),
        )

        fmt = request.args.get('format', 'html')
        if fmt == 'pdf':
            html_content = render_template('clients/statement.html', **ctx, print_mode=True)
            try:
                from weasyprint import HTML as WPHtml
                pdf_bytes = WPHtml(string=html_content).write_pdf()
                return Response(
                    pdf_bytes, mimetype='application/pdf',
                    headers={'Content-Disposition': f'attachment; filename="statement_{client_id}_{end_str}.pdf"'},
                )
            except ImportError:
                flash('PDF generation requires WeasyPrint. Install with: pip install weasyprint', 'warning')

        return render_template('clients/statement.html', **ctx, print_mode=False)
    finally:
        db.close()


@app.route('/clients/<int:client_id>/statement/email', methods=['POST'])
@login_required
def email_statement(client_id):
    """Email statement to client (placeholder — requires email utility)."""
    db = get_session()
    try:
        client = db.query(Client).filter_by(
            id=client_id, organization_id=current_user.organization_id
        ).first()
        if not client:
            return jsonify({'error': 'Client not found'}), 404

        billing_email = client.billing_email or client.email
        if not billing_email:
            return jsonify({'error': 'No billing email on file for this client.'}), 400

        # Email sending would go here — placeholder response
        return jsonify({
            'success': True,
            'sent_to': billing_email,
            'message': 'Statement email queued (email service not yet configured).',
        })
    finally:
        db.close()


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


@app.route('/invoices/new', methods=['GET', 'POST'])
@login_required
def invoice_new():
    """Create a new invoice with full commercial billing support."""
    if current_user.role not in ('owner', 'admin', 'dispatcher'):
        abort(403)

    from web.utils.payment_terms import calculate_due_date
    from web.utils.po_utils import handle_po_linking
    from models.settings import OrganizationSettings

    db = get_session()
    try:
        org_id = current_user.organization_id
        clients = db.query(Client).filter_by(
            organization_id=org_id, is_active=True
        ).order_by(Client.company_name, Client.last_name).all()
        jobs = db.query(Job).filter(
            Job.organization_id == org_id,
            Job.status.notin_(['cancelled'])
        ).order_by(Job.created_at.desc()).limit(50).all()
        divs = db.query(Division).filter_by(
            organization_id=org_id, is_active=True
        ).order_by(Division.sort_order).all()

        if request.method == 'POST':
            f = request.form
            settings = OrganizationSettings.get_or_create(db, org_id)

            # Parse dates
            invoice_date_str = f.get('invoice_date', '')
            invoice_date = date.fromisoformat(invoice_date_str) if invoice_date_str else date.today()
            terms = f.get('payment_terms', 'net_30')
            custom_days = int(f.get('custom_payment_days') or 0)
            due_date_str = f.get('due_date', '')
            if due_date_str:
                due_dt = date.fromisoformat(due_date_str)
            else:
                due_dt = calculate_due_date(invoice_date, terms, custom_days)

            client_id = int(f.get('client_id')) if f.get('client_id') else None
            client = db.query(Client).filter_by(id=client_id).first() if client_id else None

            # Build invoice
            inv = Invoice(
                organization_id=org_id,
                client_id=client_id,
                job_id=int(f.get('job_id')) if f.get('job_id') else None,
                invoice_number=settings.next_invoice_number(db),
                status=f.get('status', 'draft'),
                issued_date=datetime.combine(invoice_date, datetime.min.time()),
                due_date=datetime.combine(due_dt, datetime.min.time()) if due_dt else None,
                payment_terms=terms,
                cost_code=f.get('cost_code', '').strip() or None,
                department=f.get('department', '').strip() or None,
                billing_contact=f.get('billing_contact', '').strip() or None,
                po_number_display=f.get('po_number_display', '').strip() or None,
                notes=f.get('notes', '').strip() or None,
                approval_status='not_required',
                created_by_id=current_user.id,
            )
            db.add(inv)
            db.flush()

            # Parse line items
            descs = f.getlist('item_desc[]')
            qtys = f.getlist('item_qty[]')
            rates = f.getlist('item_rate[]')
            taxed_indices = set(f.getlist('item_tax[]'))

            subtotal = 0.0
            tax_total = 0.0
            tax_rate = 13.0
            tax_exempt = client.tax_exempt if client else False

            for i, desc in enumerate(descs):
                if not desc.strip():
                    continue
                qty = float(qtys[i] if i < len(qtys) else 1)
                rate_val = float(rates[i] if i < len(rates) else 0)
                is_taxable = str(i) in taxed_indices
                line_total = qty * rate_val
                line_tax = line_total * (tax_rate / 100) if is_taxable and not tax_exempt else 0

                item = InvoiceItem(
                    invoice_id=inv.id,
                    description=desc.strip(),
                    quantity=qty,
                    unit_price=rate_val,
                    total=line_total,
                    sort_order=i,
                )
                db.add(item)
                subtotal += line_total
                tax_total += line_tax

            inv.subtotal = subtotal
            inv.tax_rate = tax_rate
            inv.tax_amount = 0 if tax_exempt else tax_total
            inv.total = subtotal + (0 if tax_exempt else tax_total)
            inv.balance_due = inv.total
            db.flush()

            # PO linking
            try:
                warnings = handle_po_linking(db, inv, f.get('po_id'))
                for w in warnings:
                    flash(w, 'warning')
            except ValueError as exc:
                db.rollback()
                flash(str(exc), 'danger')
                return redirect(url_for('invoice_new'))

            # Approval status
            if client and settings.requires_approval(inv.total, client.client_type):
                inv.approval_status = 'pending'

            db.commit()

            if inv.approval_status == 'pending':
                flash(f'Invoice {inv.invoice_number} created and awaiting approval.', 'info')
            else:
                flash(f'Invoice {inv.invoice_number} created.', 'success')
            return redirect(url_for('invoice_detail', invoice_id=inv.id))

        # GET
        return render_template('invoice_new.html',
            active_page='invoices', user=current_user, divisions=get_divisions(),
            clients=clients,
            jobs=jobs,
            all_divisions=[d.to_dict() for d in divs],
            invoice=None,
            today=date.today(),
        )
    finally:
        db.close()


@app.route('/api/invoices/prefill-materials/<int:job_id>')
@login_required
def invoice_prefill_materials(job_id):
    """Return billable verified materials as JSON for invoice line item prefill."""
    db = get_session()
    try:
        from web.utils.materials_utils import get_billable_materials_for_invoice
        items = get_billable_materials_for_invoice(db, job_id)
        return jsonify(items)
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
            invoice_obj=inv,
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

        # Phase events
        from models.job_phase import JobPhase
        phase_events = []
        phases_with_dates = db.query(JobPhase).join(Job).filter(
            Job.organization_id == org_id,
            JobPhase.scheduled_start_date.isnot(None),
            JobPhase.status.notin_(['skipped', 'completed']),
        ).all()

        # Conflict detection
        from collections import defaultdict
        tech_phases = defaultdict(list)
        for p in phases_with_dates:
            if p.assigned_technician_id and p.scheduled_start_date:
                tech_phases[p.assigned_technician_id].append(p)

        conflict_ids = set()
        for tid, tlist in tech_phases.items():
            sorted_p = sorted(tlist, key=lambda x: x.scheduled_start_date)
            for i in range(len(sorted_p)):
                for j in range(i + 1, len(sorted_p)):
                    a, b = sorted_p[i], sorted_p[j]
                    a_end = a.scheduled_end_date or a.scheduled_start_date
                    if a_end >= b.scheduled_start_date:
                        conflict_ids.add(a.id)
                        conflict_ids.add(b.id)

        phase_colors = {'not_started': '#6c757d', 'scheduled': '#0dcaf0', 'in_progress': '#0d6efd', 'on_hold': '#ffc107'}
        for p in phases_with_dates:
            evt = {
                'id': f'phase-{p.id}',
                'title': f'[{p.job.job_number}] P{p.phase_number}: {p.title[:25]}',
                'start': p.scheduled_start_date.isoformat(),
                'color': phase_colors.get(p.status, '#6c757d'),
                'url': f'/jobs/{p.job_id}#phases',
                'type': 'phase',
                'has_conflict': p.id in conflict_ids,
            }
            if p.scheduled_end_date:
                evt['end'] = p.scheduled_end_date.isoformat()
            phase_events.append(evt)

        all_events = events + phase_events
        phases_with_conflicts = [p for p in phases_with_dates if p.id in conflict_ids]

        technicians = db.query(Technician).filter_by(
            organization_id=org_id, is_active=True
        ).all()

        return render_template('schedule.html',
            active_page='schedule',
            user=current_user,
            divisions=get_divisions(),
            active_division=active_div,
            events=all_events,
            unscheduled=unscheduled,
            technicians=[t.to_dict() for t in technicians],
            events_json=all_events,
            unscheduled_json=unscheduled,
            phases_with_conflicts=phases_with_conflicts,
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

        from models.settings import OrganizationSettings
        org_settings = OrganizationSettings.get_or_create(db, current_user.organization_id)

        return render_template('settings.html',
            active_page='settings',
            user=current_user,
            divisions=get_divisions(),
            organization=org.to_dict() if org else {},
            all_divisions=[d.to_dict() for d in divisions],
            technicians=[t.to_dict() for t in technicians],
            org_settings=org_settings,
        )
    finally:
        db.close()



# ========== CONTRACTS -- moved to web/routes/contract_routes.py ==========


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


# ========== Bulk Statements ==========

@app.route('/invoices/statements')
@login_required
def bulk_statements():
    if current_user.role not in ('owner', 'admin'):
        abort(403)

    db = get_session()
    try:
        org_id = current_user.organization_id
        today = date.today()
        if today.month == 1:
            start_date = date(today.year - 1, 12, 1)
        else:
            start_date = date(today.year, today.month - 1, 1)

        # Commercial clients with outstanding balances
        from sqlalchemy import distinct
        client_ids_with_balance = db.query(distinct(Invoice.client_id)).filter(
            Invoice.organization_id == org_id,
            Invoice.status.in_(['sent', 'overdue', 'partial']),
        ).all()
        client_ids = [r[0] for r in client_ids_with_balance]

        clients_with_balance = db.query(Client).filter(
            Client.id.in_(client_ids),
            Client.organization_id == org_id,
        ).order_by(Client.company_name, Client.last_name).all()

        client_totals = []
        for client in clients_with_balance:
            outstanding = db.query(func.coalesce(func.sum(Invoice.balance_due), 0)).filter(
                Invoice.client_id == client.id,
                Invoice.status.in_(['sent', 'overdue', 'partial']),
            ).scalar() or 0
            client_totals.append({
                'client': client,
                'outstanding': float(outstanding),
                'billing_email': client.billing_email or client.email,
            })

        return render_template('invoices/bulk_statements.html',
            active_page='invoices', user=current_user, divisions=get_divisions(),
            client_totals=client_totals,
            start_date=start_date, end_date=today,
        )
    finally:
        db.close()


# ========== AR Aging Report ==========

@app.route('/invoices/aging')
@login_required
def aging_report():
    if current_user.role == 'technician':
        abort(403)
    from collections import defaultdict
    db = get_session()
    try:
        org_id = current_user.organization_id

        f_client_id = request.args.get('client_id', type=int)
        f_division_id = request.args.get('division_id', type=int)
        f_overdue = request.args.get('overdue_only', 'false').lower() == 'true'
        f_sort = request.args.get('sort', 'total')
        f_dir = request.args.get('dir', 'desc')

        q = db.query(Invoice).filter(
            Invoice.organization_id == org_id,
            Invoice.status.in_(['sent', 'overdue', 'partial'])
        )
        if f_client_id:
            q = q.filter(Invoice.client_id == f_client_id)

        invoices = q.all()
        today = date.today()

        def _build_row():
            return {'client': None, 'current': 0.0, 'days_1_30': 0.0,
                    'days_31_60': 0.0, 'days_61_90': 0.0, 'days_90_plus': 0.0,
                    'total': 0.0, 'invoice_count': 0}

        rows = defaultdict(_build_row)
        for inv in invoices:
            if not inv.due_date:
                continue
            remaining = float(inv.balance_due or 0)
            if remaining <= 0:
                continue

            row = rows[inv.client_id]
            row['client'] = inv.client
            row['total'] += remaining
            row['invoice_count'] += 1

            bucket = inv.aging_bucket
            if bucket == 'current':
                row['current'] += remaining
            elif bucket == '1_30':
                row['days_1_30'] += remaining
            elif bucket == '31_60':
                row['days_31_60'] += remaining
            elif bucket == '61_90':
                row['days_61_90'] += remaining
            else:
                row['days_90_plus'] += remaining

        aging_data = list(rows.values())

        if f_overdue:
            aging_data = [r for r in aging_data
                          if r['days_1_30'] + r['days_31_60'] + r['days_61_90'] + r['days_90_plus'] > 0]

        sort_map = {
            'client': lambda r: (r['client'].display_name or '').lower() if r['client'] else '',
            'total': lambda r: r['total'],
            'current': lambda r: r['current'],
            'days_1_30': lambda r: r['days_1_30'],
            'days_31_60': lambda r: r['days_31_60'],
            'days_61_90': lambda r: r['days_61_90'],
            'days_90_plus': lambda r: r['days_90_plus'],
        }
        aging_data.sort(key=sort_map.get(f_sort, sort_map['total']), reverse=(f_dir == 'desc'))

        totals = {k: sum(r[k] for r in aging_data) for k in
                  ['current', 'days_1_30', 'days_31_60', 'days_61_90', 'days_90_plus', 'total']}

        clients = db.query(Client).filter_by(
            organization_id=org_id, is_active=True
        ).order_by(Client.company_name, Client.last_name).all()

        return render_template('invoices/aging_report.html',
            active_page='invoices', user=current_user, divisions=get_divisions(),
            aging_data=aging_data, totals=totals, clients=clients,
            filters={'client_id': f_client_id, 'division_id': f_division_id,
                     'overdue_only': f_overdue, 'sort': f_sort, 'dir': f_dir},
            today=today,
        )
    finally:
        db.close()


# ========== Invoice Approval Workflow ==========

@app.route('/invoices/approvals')
@login_required
def approval_queue():
    from models.settings import OrganizationSettings
    db = get_session()
    try:
        org_id = current_user.organization_id
        settings = OrganizationSettings.get_or_create(db, org_id)
        if current_user.role not in settings.approval_role_list:
            abort(403)

        pending = db.query(Invoice).filter(
            Invoice.organization_id == org_id,
            Invoice.approval_status == 'pending'
        ).order_by(Invoice.created_at.asc()).all()

        now = datetime.utcnow()
        pending_data = []
        for inv in pending:
            d = inv.to_dict()
            d['client_name'] = inv.client.display_name if inv.client else 'Unknown'
            d['job_title'] = inv.job.title if inv.job else None
            d['days_waiting'] = (now - inv.created_at).days if inv.created_at else 0
            pending_data.append(d)

        return render_template('invoices/approval_queue.html',
            active_page='invoices', user=current_user, divisions=get_divisions(),
            pending_invoices=pending_data,
            settings=settings.to_dict(),
        )
    finally:
        db.close()


@app.route('/invoices/<int:invoice_id>/approve', methods=['POST'])
@login_required
def approve_invoice(invoice_id):
    from models.settings import OrganizationSettings
    db = get_session()
    try:
        org_id = current_user.organization_id
        settings = OrganizationSettings.get_or_create(db, org_id)
        if current_user.role not in settings.approval_role_list:
            return jsonify({'error': 'Unauthorized'}), 403

        invoice = db.query(Invoice).filter_by(id=invoice_id, organization_id=org_id).first()
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404
        if invoice.approval_status != 'pending':
            return jsonify({'error': 'Invoice is not pending approval'}), 400

        invoice.approval_status = 'approved'
        invoice.approved_by = current_user.id
        invoice.approved_at = datetime.utcnow()
        invoice.rejection_reason = None
        db.commit()

        try:
            from web.utils.notification_service import NotificationService
            NotificationService.notify('item_approved', invoice, triggered_by=current_user)
        except Exception:
            pass

        if request.is_json:
            return jsonify({'success': True, 'invoice_number': invoice.invoice_number})

        flash(f'Invoice {invoice.invoice_number} approved.', 'success')
        return redirect(request.referrer or url_for('approval_queue'))
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        db.close()


@app.route('/invoices/<int:invoice_id>/reject', methods=['POST'])
@login_required
def reject_invoice(invoice_id):
    from models.settings import OrganizationSettings
    db = get_session()
    try:
        org_id = current_user.organization_id
        settings = OrganizationSettings.get_or_create(db, org_id)
        if current_user.role not in settings.approval_role_list:
            return jsonify({'error': 'Unauthorized'}), 403

        invoice = db.query(Invoice).filter_by(id=invoice_id, organization_id=org_id).first()
        if not invoice:
            return jsonify({'error': 'Invoice not found'}), 404

        data = request.get_json(force=True, silent=True) or {}
        reason = (data.get('reason') or '').strip()
        if not reason:
            return jsonify({'error': 'A rejection reason is required.'}), 400

        invoice.approval_status = 'rejected'
        invoice.rejection_reason = reason
        invoice.status = 'draft'
        db.commit()

        try:
            from web.utils.notification_service import NotificationService
            NotificationService.notify('item_rejected', invoice, triggered_by=current_user,
                                       extra_context={'reason': reason})
        except Exception:
            pass

        if request.is_json:
            return jsonify({'success': True, 'invoice_number': invoice.invoice_number})

        flash(f'Invoice {invoice.invoice_number} rejected and returned to draft.', 'warning')
        return redirect(request.referrer or url_for('approval_queue'))
    except Exception as e:
        db.rollback()
        return jsonify({'error': str(e)}), 400
    finally:
        db.close()


@app.route('/settings/approvals', methods=['POST'])
@login_required
def save_approval_settings():
    from models.settings import OrganizationSettings
    if current_user.role not in ('owner', 'admin'):
        abort(403)

    db = get_session()
    try:
        org_id = current_user.organization_id
        settings = OrganizationSettings.get_or_create(db, org_id)
        settings.invoice_approval_enabled = 'invoice_approval_enabled' in request.form
        threshold = request.form.get('invoice_approval_threshold', '').strip()
        settings.invoice_approval_threshold = float(threshold) if threshold else None
        settings.invoice_approval_roles = request.form.get('invoice_approval_roles', 'owner,admin')
        settings.updated_by = current_user.id
        db.commit()
        flash('Approval settings saved.', 'success')
    finally:
        db.close()
    return redirect(url_for('settings_page'))


@app.route('/settings/warranty', methods=['POST'])
@login_required
def save_warranty_settings():
    from models.settings import OrganizationSettings
    if current_user.role not in ('owner', 'admin'):
        abort(403)
    db = get_session()
    try:
        org_id = current_user.organization_id
        settings = OrganizationSettings.get_or_create(db, org_id)
        settings.default_labor_warranty_months = int(request.form.get('default_labor_warranty_months', 12))
        settings.default_parts_warranty_months = int(request.form.get('default_parts_warranty_months', 12))
        mcv = request.form.get('default_max_claim_value', '').strip()
        settings.default_max_claim_value = float(mcv) if mcv else None
        settings.callback_lookback_days = int(request.form.get('callback_lookback_days', 90))
        settings.callback_rate_threshold = float(request.form.get('callback_rate_threshold', 5.0))
        settings.auto_create_warranty_on_completion = 'auto_create_warranty_on_completion' in request.form
        settings.default_warranty_terms = request.form.get('default_warranty_terms', '').strip() or None
        db.commit()
        flash('Warranty settings saved.', 'success')
    finally:
        db.close()
    return redirect(url_for('settings_page'))


@app.route('/settings/communications', methods=['POST'])
@login_required
def save_comm_settings():
    from models.settings import OrganizationSettings
    if current_user.role not in ('owner', 'admin'):
        abort(403)
    db = get_session()
    try:
        org_id = current_user.organization_id
        settings = OrganizationSettings.get_or_create(db, org_id)
        settings.inactive_client_alert_days = int(request.form.get('inactive_client_alert_days', 7))
        settings.default_follow_up_days = int(request.form.get('default_follow_up_days', 3))
        settings.require_comm_log_on_status_change = 'require_comm_log_on_status_change' in request.form
        db.commit()
        flash('Communication settings saved.', 'success')
    finally:
        db.close()
    return redirect(url_for('settings_page'))


@app.route('/settings/expenses', methods=['POST'])
@login_required
def save_expense_settings():
    from models.settings import OrganizationSettings
    if current_user.role not in ('owner', 'admin'):
        abort(403)
    db = get_session()
    try:
        org_id = current_user.organization_id
        settings = OrganizationSettings.get_or_create(db, org_id)
        for field in ['expense_approval_threshold', 'expense_receipt_required_threshold', 'mileage_rate', 'default_expense_markup']:
            val = request.form.get(field, '').strip()
            if val:
                setattr(settings, field, float(val))
            else:
                setattr(settings, field, None)
        settings.expense_approval_roles = request.form.get('expense_approval_roles', 'owner,admin').strip()
        db.commit()
        flash('Expense settings saved.', 'success')
    finally:
        db.close()
    return redirect(url_for('settings_page'))


@app.route('/settings/notifications/global', methods=['POST'])
@login_required
def save_notification_settings():
    from models.settings import OrganizationSettings
    if current_user.role not in ('owner', 'admin'):
        abort(403)
    db = get_session()
    try:
        settings = OrganizationSettings.get_or_create(db, current_user.organization_id)
        # Boolean fields
        for field in ('notifications_enabled', 'client_notifications_enabled', 'sms_enabled'):
            setattr(settings, field, request.form.get(field) == '1')
        # Integer fields
        for field in ('notification_polling_interval', 'appointment_reminder_hours'):
            val = request.form.get(field, '').strip()
            if val:
                setattr(settings, field, int(val))
        # String fields
        for field in ('email_from_name', 'email_from_address', 'email_reply_to',
                      'sms_provider', 'sms_api_key', 'sms_from_number', 'invoice_reminder_days'):
            setattr(settings, field, request.form.get(field, '').strip() or None)
        db.commit()
        flash('Notification settings saved.', 'success')
    finally:
        db.close()
    return redirect(url_for('settings_page'))


# ========== API: Invoice PO Linking ==========

@app.route('/api/invoices/<int:invoice_id>/link-po', methods=['POST'])
@login_required
def api_invoice_link_po(invoice_id):
    """Link or unlink a PO to an invoice. POST { po_id: int|null }"""
    from web.utils.po_utils import handle_po_linking
    db = get_session()
    try:
        org_id = current_user.organization_id
        invoice = db.query(Invoice).filter_by(id=invoice_id, organization_id=org_id).first()
        if not invoice:
            return jsonify({'success': False, 'error': 'Invoice not found'}), 404

        data = request.get_json(force=True)
        new_po_id = data.get('po_id')

        try:
            warnings = handle_po_linking(db, invoice, new_po_id)
            db.commit()
            return jsonify({
                'success': True,
                'warnings': warnings,
                'po_number': invoice.po_number_display,
            })
        except ValueError as exc:
            db.rollback()
            return jsonify({'success': False, 'error': str(exc)}), 400
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        db.close()


@app.route('/api/invoices/<int:invoice_id>/set-terms', methods=['POST'])
@login_required
def api_invoice_set_terms(invoice_id):
    """Set payment terms and recalculate due date. POST { payment_terms, custom_days }"""
    from web.utils.payment_terms import calculate_due_date
    db = get_session()
    try:
        org_id = current_user.organization_id
        invoice = db.query(Invoice).filter_by(id=invoice_id, organization_id=org_id).first()
        if not invoice:
            return jsonify({'success': False, 'error': 'Invoice not found'}), 404

        data = request.get_json(force=True)
        invoice.payment_terms = data.get('payment_terms', 'net_30')
        invoice.calculate_due_date()
        db.commit()
        return jsonify({
            'success': True,
            'due_date': invoice.due_date.isoformat() if invoice.due_date else None,
            'payment_terms': invoice.payment_terms,
        })
    except Exception as e:
        db.rollback()
        return jsonify({'success': False, 'error': str(e)}), 400
    finally:
        db.close()


# ========== API: Billing / Payment Terms ==========

@app.route('/api/payment-terms/due-date', methods=['GET'])
@login_required
def api_due_date():
    """AJAX: calculate due date from invoice_date + terms."""
    from web.utils.payment_terms import calculate_due_date, PAYMENT_TERMS_LABELS

    invoice_date_str = request.args.get('invoice_date', '')
    terms = request.args.get('terms', 'net_30')
    custom_days = request.args.get('custom_days', None)

    try:
        if invoice_date_str:
            inv_date = date.fromisoformat(invoice_date_str)
        else:
            inv_date = date.today()
        due = calculate_due_date(inv_date, terms, custom_days)
        return jsonify({
            'due_date': due.isoformat(),
            'due_date_display': due.strftime('%B %d, %Y'),
            'label': PAYMENT_TERMS_LABELS.get(terms, terms),
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/client/<int:client_id>/billing-defaults', methods=['GET'])
@app.route('/api/clients/<int:client_id>/billing', methods=['GET'])
@login_required
def api_client_billing_defaults(client_id):
    """AJAX: Return client billing defaults for invoice form auto-population."""
    from web.utils.payment_terms import get_terms_for_client

    db = get_session()
    try:
        client = db.query(Client).filter_by(
            id=client_id, organization_id=current_user.organization_id
        ).first()
        if not client:
            return jsonify({'error': 'Client not found'}), 404

        defaults = get_terms_for_client(client)

        # Outstanding balance
        outstanding = db.query(func.coalesce(func.sum(Invoice.balance_due), 0)).filter(
            Invoice.client_id == client_id,
            Invoice.status.in_(['sent', 'overdue', 'partial'])
        ).scalar() or 0

        credit_limit = float(client.credit_limit) if client.credit_limit else None
        available_credit = (credit_limit - float(outstanding)) if credit_limit else None

        return jsonify({
            'payment_terms': defaults['terms'],
            'custom_days': defaults['custom_days'],
            'due_date': defaults['due_date'].isoformat(),
            'due_date_display': defaults['due_date'].strftime('%B %d, %Y'),
            'require_po': client.require_po,
            'tax_exempt': client.tax_exempt,
            'tax_exempt_number': client.tax_exempt_number,
            'billing_contact_name': client.billing_contact_name,
            'billing_email': client.billing_email,
            'credit_limit': credit_limit,
            'outstanding_balance': float(outstanding),
            'available_credit': available_credit,
            'is_commercial': client.client_type == 'commercial',
        })
    finally:
        db.close()


# ========== API: Chat ==========

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
