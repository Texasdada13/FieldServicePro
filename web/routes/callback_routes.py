"""Callback tracking routes."""
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import desc, or_

from models.database import get_session
from models.callback import (
    Callback, CALLBACK_REASONS, CALLBACK_SEVERITIES, CALLBACK_STATUSES,
)
from models.job import Job
from models.client import Client
from models.technician import Technician
from models.warranty import Warranty
from models.division import Division
from web.auth import role_required
from web.utils.callback_utils import generate_callback_number, get_callback_stats

callback_bp = Blueprint('callback', __name__, url_prefix='/callbacks')


def _get_divisions():
    db = get_session()
    try:
        return db.query(Division).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Division.sort_order).all()
    finally:
        db.close()


# ── List ──────────────────────────────────────────────────────────────────────

@callback_bp.route('/')
@login_required
def callback_list():
    db = get_session()
    try:
        org_id = current_user.organization_id
        status_filter = request.args.get('status', '')
        severity_filter = request.args.get('severity', '')
        search = request.args.get('search', '').strip()

        query = db.query(Callback).join(Client).filter(Client.organization_id == org_id)
        if status_filter:
            query = query.filter(Callback.status == status_filter)
        else:
            query = query.filter(Callback.status.notin_(['closed']))
        if severity_filter:
            query = query.filter(Callback.severity == severity_filter)
        if search:
            s = f'%{search}%'
            query = query.filter(or_(
                Callback.callback_number.ilike(s),
                Callback.description.ilike(s),
            ))

        callbacks = query.order_by(desc(Callback.reported_date)).all()
        stats = get_callback_stats(db, org_id)

        return render_template('callbacks/callback_list.html',
            active_page='callbacks', user=current_user, divisions=_get_divisions(),
            can_admin=current_user.role in ('owner', 'admin'),
            callbacks=callbacks, stats=stats,
            reasons=CALLBACK_REASONS, severities=CALLBACK_SEVERITIES,
            statuses=CALLBACK_STATUSES,
            status_filter=status_filter, severity_filter=severity_filter, search=search,
        )
    finally:
        db.close()


# ── Detail ────────────────────────────────────────────────────────────────────

@callback_bp.route('/<int:callback_id>')
@login_required
def callback_detail(callback_id):
    db = get_session()
    try:
        cb = db.query(Callback).filter_by(id=callback_id).first()
        if not cb:
            flash('Callback not found.', 'error')
            return redirect(url_for('callback.callback_list'))

        return render_template('callbacks/callback_detail.html',
            active_page='callbacks', user=current_user, divisions=_get_divisions(),
            can_admin=current_user.role in ('owner', 'admin'),
            callback=cb, reasons=CALLBACK_REASONS, severities=CALLBACK_SEVERITIES,
            statuses=CALLBACK_STATUSES,
        )
    finally:
        db.close()


# ── Create ────────────────────────────────────────────────────────────────────

@callback_bp.route('/new', methods=['GET', 'POST'])
@login_required
@role_required('owner', 'admin', 'dispatcher')
def callback_new():
    db = get_session()
    try:
        org_id = current_user.organization_id
        original_job_id = request.args.get('original_job_id', type=int)

        if request.method == 'POST':
            f = request.form
            orig_job_id = int(f['original_job_id'])
            cb_job_id = int(f['callback_job_id'])
            orig_job = db.query(Job).filter_by(id=orig_job_id).first()

            cb = Callback(
                callback_number=generate_callback_number(db),
                original_job_id=orig_job_id,
                callback_job_id=cb_job_id,
                client_id=orig_job.client_id if orig_job else int(f.get('client_id', 0)),
                reason=f.get('reason', 'other'),
                description=f['description'],
                severity=f.get('severity', 'minor'),
                is_warranty='is_warranty' in f,
                warranty_id=int(f['warranty_id']) if f.get('warranty_id') else None,
                is_billable='is_billable' in f,
                root_cause=f.get('root_cause', '').strip() or None,
                corrective_action=f.get('corrective_action', '').strip() or None,
                responsible_technician_id=int(f['responsible_technician_id']) if f.get('responsible_technician_id') else None,
                customer_impact=f.get('customer_impact', '').strip() or None,
                internal_notes=f.get('internal_notes', '').strip() or None,
                reported_date=date.today(),
                status='reported',
                created_by=current_user.id,
            )
            db.add(cb)

            # Mark the callback job
            cb_job = db.query(Job).filter_by(id=cb_job_id).first()
            if cb_job:
                cb_job.is_callback = True
                cb_job.original_job_id = orig_job_id
                if cb.is_warranty:
                    cb_job.is_warranty_work = True

            db.commit()

            try:
                from web.utils.notification_service import NotificationService
                NotificationService.notify('callback_created', cb, triggered_by=current_user)
            except Exception:
                pass

            flash(f'Callback {cb.callback_number} created.', 'success')
            return redirect(url_for('callback.callback_detail', callback_id=cb.id))

        # GET
        jobs = db.query(Job).filter(
            Job.organization_id == org_id
        ).order_by(desc(Job.id)).limit(200).all()
        techs = db.query(Technician).filter_by(is_active=True).order_by(Technician.first_name).all()
        warranties = db.query(Warranty).join(Client).filter(
            Client.organization_id == org_id,
            Warranty.status.in_(['active', 'expiring_soon']),
        ).all()

        return render_template('callbacks/callback_form.html',
            active_page='callbacks', user=current_user, divisions=_get_divisions(),
            callback=None, original_job_id=original_job_id,
            jobs=jobs, technicians=techs, warranties=warranties,
            reasons=CALLBACK_REASONS, severities=CALLBACK_SEVERITIES,
        )
    finally:
        db.close()


# ── Update Status ─────────────────────────────────────────────────────────────

@callback_bp.route('/<int:callback_id>/update', methods=['POST'])
@login_required
@role_required('owner', 'admin', 'dispatcher')
def callback_update(callback_id):
    db = get_session()
    try:
        cb = db.query(Callback).filter_by(id=callback_id).first()
        if not cb:
            flash('Callback not found.', 'error')
            return redirect(url_for('callback.callback_list'))

        f = request.form
        cb.status = f.get('status', cb.status)
        cb.root_cause = f.get('root_cause', cb.root_cause)
        cb.corrective_action = f.get('corrective_action', cb.corrective_action)
        cb.internal_notes = f.get('internal_notes', cb.internal_notes)

        if cb.status in ('resolved', 'closed') and not cb.resolved_date:
            cb.resolved_date = date.today()

        db.commit()
        flash('Callback updated.', 'success')
    finally:
        db.close()
    return redirect(url_for('callback.callback_detail', callback_id=callback_id))


# ── API: Recent completed jobs for a client ───────────────────────────────────

@callback_bp.route('/api/client/<int:client_id>/recent-jobs')
@login_required
def api_recent_jobs(client_id):
    db = get_session()
    try:
        from datetime import timedelta
        cutoff = date.today() - timedelta(days=90)
        jobs = db.query(Job).filter(
            Job.client_id == client_id,
            Job.status == 'completed',
            Job.completed_at >= cutoff,
        ).order_by(desc(Job.completed_at)).all()
        return jsonify([{
            'id': j.id,
            'title': j.title,
            'job_number': j.job_number,
            'scheduled_date': j.scheduled_date.strftime('%b %d, %Y') if j.scheduled_date else '',
            'has_warranty': bool(j.warranties),
        } for j in jobs])
    finally:
        db.close()


# ── API: Active warranties for a client ───────────────────────────────────────

@callback_bp.route('/api/client/<int:client_id>/warranties')
@login_required
def api_client_warranties(client_id):
    db = get_session()
    try:
        warranties = db.query(Warranty).filter(
            Warranty.client_id == client_id,
            Warranty.status.in_(['active', 'expiring_soon']),
        ).all()
        return jsonify([{
            'id': w.id,
            'number': w.warranty_number,
            'title': w.title,
        } for w in warranties])
    finally:
        db.close()
