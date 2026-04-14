"""Warranty CRUD + claims routes."""
from datetime import date, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import desc

from models.database import get_session
from models.warranty import (
    Warranty, WarrantyClaim,
    WARRANTY_TYPES, WARRANTY_STATUSES, CLAIM_TYPES, CLAIM_STATUSES,
)
from models.job import Job
from models.client import Client, Property
from models.division import Division
from web.auth import role_required
from web.utils.warranty_utils import (
    generate_warranty_number, generate_claim_number,
    refresh_all_warranty_statuses, get_warranty_stats,
)

warranty_bp = Blueprint('warranty', __name__, url_prefix='/warranties')


def _get_divisions():
    db = get_session()
    try:
        return db.query(Division).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Division.sort_order).all()
    finally:
        db.close()


# ── List ──────────────────────────────────────────────────────────────────────

@warranty_bp.route('/')
@login_required
def warranty_list():
    db = get_session()
    try:
        org_id = current_user.organization_id
        refresh_all_warranty_statuses(db)

        status_filter = request.args.get('status', '')
        client_filter = request.args.get('client_id', '')
        type_filter = request.args.get('warranty_type', '')
        expiring = request.args.get('expiring_soon', '')

        query = db.query(Warranty).join(Client).filter(Client.organization_id == org_id)
        if status_filter:
            query = query.filter(Warranty.status == status_filter)
        if expiring == '1':
            query = query.filter(Warranty.status == 'expiring_soon')
        if client_filter:
            query = query.filter(Warranty.client_id == int(client_filter))
        if type_filter:
            query = query.filter(Warranty.warranty_type == type_filter)

        warranties = query.order_by(desc(Warranty.created_at)).all()
        stats = get_warranty_stats(db)
        clients = db.query(Client).filter_by(organization_id=org_id).order_by(Client.company_name).all()

        return render_template('warranties/warranty_list.html',
            active_page='warranties', user=current_user, divisions=_get_divisions(),
            can_admin=current_user.role in ('owner', 'admin'),
            warranties=warranties, stats=stats, clients=clients,
            warranty_types=WARRANTY_TYPES, warranty_statuses=WARRANTY_STATUSES,
            status_filter=status_filter, client_filter=client_filter,
            type_filter=type_filter, expiring_filter=expiring,
        )
    finally:
        db.close()


# ── Detail ────────────────────────────────────────────────────────────────────

@warranty_bp.route('/<int:warranty_id>')
@login_required
def warranty_detail(warranty_id):
    db = get_session()
    try:
        warranty = db.query(Warranty).filter_by(id=warranty_id).first()
        if not warranty:
            flash('Warranty not found.', 'error')
            return redirect(url_for('warranty.warranty_list'))

        warranty.refresh_status()
        db.commit()

        return render_template('warranties/warranty_detail.html',
            active_page='warranties', user=current_user, divisions=_get_divisions(),
            can_admin=current_user.role in ('owner', 'admin'),
            warranty=warranty,
            claim_types=CLAIM_TYPES, claim_statuses=CLAIM_STATUSES,
        )
    finally:
        db.close()


# ── Create ────────────────────────────────────────────────────────────────────

@warranty_bp.route('/new', methods=['GET', 'POST'])
@login_required
@role_required('owner', 'admin', 'dispatcher')
def warranty_new():
    db = get_session()
    try:
        org_id = current_user.organization_id
        job_id = request.args.get('job_id', type=int)
        prefill_job = db.query(Job).filter_by(id=job_id).first() if job_id else None

        if request.method == 'POST':
            return _handle_save(db, None)

        clients = db.query(Client).filter_by(organization_id=org_id).order_by(Client.company_name).all()
        jobs = db.query(Job).filter(
            Job.organization_id == org_id, Job.status == 'completed'
        ).order_by(desc(Job.id)).limit(200).all()

        return render_template('warranties/warranty_form.html',
            active_page='warranties', user=current_user, divisions=_get_divisions(),
            warranty=None, prefill_job=prefill_job,
            clients=clients, jobs=jobs, warranty_types=WARRANTY_TYPES,
        )
    finally:
        db.close()


# ── Edit ──────────────────────────────────────────────────────────────────────

@warranty_bp.route('/<int:warranty_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('owner', 'admin', 'dispatcher')
def warranty_edit(warranty_id):
    db = get_session()
    try:
        org_id = current_user.organization_id
        warranty = db.query(Warranty).filter_by(id=warranty_id).first()
        if not warranty:
            flash('Warranty not found.', 'error')
            return redirect(url_for('warranty.warranty_list'))

        if request.method == 'POST':
            return _handle_save(db, warranty)

        clients = db.query(Client).filter_by(organization_id=org_id).order_by(Client.company_name).all()
        jobs = db.query(Job).filter(
            Job.organization_id == org_id, Job.status == 'completed'
        ).order_by(desc(Job.id)).limit(200).all()

        return render_template('warranties/warranty_form.html',
            active_page='warranties', user=current_user, divisions=_get_divisions(),
            warranty=warranty, prefill_job=None,
            clients=clients, jobs=jobs, warranty_types=WARRANTY_TYPES,
        )
    finally:
        db.close()


def _handle_save(db, warranty):
    f = request.form
    is_new = warranty is None
    try:
        duration = int(f.get('duration_months', 12))
        start = date.fromisoformat(f['start_date'])
        end = date.fromisoformat(f['end_date']) if f.get('end_date') else start + timedelta(days=30 * duration)
        max_claim = float(f['max_claim_value']) if f.get('max_claim_value') else None

        if is_new:
            warranty = Warranty(
                warranty_number=generate_warranty_number(db),
                created_by=current_user.id,
            )
            db.add(warranty)

        warranty.job_id = int(f['job_id'])
        warranty.client_id = int(f['client_id'])
        warranty.property_id = int(f['property_id']) if f.get('property_id') else None
        warranty.title = f['title']
        warranty.description = f.get('description', '').strip() or None
        warranty.warranty_type = f['warranty_type']
        warranty.coverage_scope = f.get('coverage_scope', '').strip() or None
        warranty.start_date = start
        warranty.end_date = end
        warranty.duration_months = duration
        warranty.max_claim_value = max_claim
        warranty.covers_parts = 'covers_parts' in f
        warranty.covered_parts = f.get('covered_parts', '').strip() or None
        warranty.manufacturer_warranty_info = f.get('manufacturer_warranty_info', '').strip() or None
        warranty.manufacturer_warranty_end_date = date.fromisoformat(f['manufacturer_warranty_end_date']) if f.get('manufacturer_warranty_end_date') else None
        warranty.equipment_serial_number = f.get('equipment_serial_number', '').strip() or None
        warranty.model_number = f.get('model_number', '').strip() or None
        warranty.notes = f.get('notes', '').strip() or None
        warranty.terms_and_conditions = f.get('terms_and_conditions', '').strip() or None
        warranty.refresh_status()
        db.commit()

        if is_new:
            try:
                from web.utils.notification_service import NotificationService
                NotificationService.notify('warranty_created', warranty, triggered_by=current_user)
            except Exception:
                pass

        flash(f"Warranty {'created' if is_new else 'updated'}: {warranty.warranty_number}", 'success')
        return redirect(url_for('warranty.warranty_detail', warranty_id=warranty.id))
    except Exception as e:
        db.rollback()
        flash(f'Error: {e}', 'error')
        return redirect(request.referrer or url_for('warranty.warranty_list'))


# ── Void ──────────────────────────────────────────────────────────────────────

@warranty_bp.route('/<int:warranty_id>/void', methods=['POST'])
@login_required
@role_required('owner', 'admin')
def warranty_void(warranty_id):
    db = get_session()
    try:
        warranty = db.query(Warranty).filter_by(id=warranty_id).first()
        if warranty:
            warranty.status = 'voided'
            warranty.voided_reason = request.form.get('voided_reason', '')
            warranty.voided_date = date.today()
            db.commit()
            flash(f'Warranty {warranty.warranty_number} voided.', 'warning')
    finally:
        db.close()
    return redirect(url_for('warranty.warranty_detail', warranty_id=warranty_id))


# ── Claims ────────────────────────────────────────────────────────────────────

@warranty_bp.route('/<int:warranty_id>/claims/new', methods=['POST'])
@login_required
@role_required('owner', 'admin', 'dispatcher')
def claim_new(warranty_id):
    db = get_session()
    try:
        warranty = db.query(Warranty).filter_by(id=warranty_id).first()
        if not warranty:
            flash('Warranty not found.', 'error')
            return redirect(url_for('warranty.warranty_list'))

        f = request.form
        claim = WarrantyClaim(
            claim_number=generate_claim_number(db),
            warranty_id=warranty_id,
            job_id=int(f['job_id']),
            description=f['description'],
            claim_type=f.get('claim_type', 'parts_and_labor'),
            labor_cost=float(f.get('labor_cost', 0) or 0),
            parts_cost=float(f.get('parts_cost', 0) or 0),
            claimed_date=date.today(),
            status='open',
            created_by=current_user.id,
        )
        db.add(claim)
        warranty.total_claimed = float(warranty.total_claimed or 0) + claim.total_cost
        db.commit()
        flash(f'Claim {claim.claim_number} created.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {e}', 'error')
    finally:
        db.close()
    return redirect(url_for('warranty.warranty_detail', warranty_id=warranty_id))


@warranty_bp.route('/claims/<int:claim_id>/update', methods=['POST'])
@login_required
@role_required('owner', 'admin', 'dispatcher')
def claim_update(claim_id):
    db = get_session()
    try:
        claim = db.query(WarrantyClaim).filter_by(id=claim_id).first()
        if not claim:
            flash('Claim not found.', 'error')
            return redirect(url_for('warranty.warranty_list'))

        f = request.form
        old_cost = claim.total_cost
        claim.status = f.get('status', claim.status)
        claim.resolution = f.get('resolution', claim.resolution)
        claim.denied_reason = f.get('denied_reason', claim.denied_reason)
        claim.labor_cost = float(f.get('labor_cost', claim.labor_cost) or 0)
        claim.parts_cost = float(f.get('parts_cost', claim.parts_cost) or 0)
        if claim.status in ('completed', 'denied'):
            claim.resolved_date = date.today()

        warranty = claim.warranty
        warranty.total_claimed = float(warranty.total_claimed or 0) + (claim.total_cost - old_cost)
        db.commit()
        flash('Claim updated.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {e}', 'error')
    finally:
        db.close()
    return redirect(url_for('warranty.warranty_detail', warranty_id=claim.warranty_id))


# ── API ───────────────────────────────────────────────────────────────────────

@warranty_bp.route('/api/client/<int:client_id>/properties')
@login_required
def api_client_properties(client_id):
    db = get_session()
    try:
        props = db.query(Property).filter_by(client_id=client_id).all()
        return jsonify([{'id': p.id, 'address': p.display_address} for p in props])
    finally:
        db.close()


@warranty_bp.route('/api/client/<int:client_id>/jobs')
@login_required
def api_client_jobs(client_id):
    db = get_session()
    try:
        jobs = db.query(Job).filter(
            Job.client_id == client_id, Job.status == 'completed'
        ).order_by(desc(Job.id)).limit(50).all()
        return jsonify([{
            'id': j.id, 'title': j.title, 'job_number': j.job_number,
            'completed_date': j.completed_at.isoformat() if j.completed_at else '',
        } for j in jobs])
    finally:
        db.close()


@warranty_bp.route('/api/job/<int:job_id>/costs')
@login_required
def api_job_costs(job_id):
    """Return labor + parts costs from time entries and materials for claim pre-fill."""
    db = get_session()
    try:
        from sqlalchemy import func
        from models.time_entry import TimeEntry
        from models.job_material import JobMaterial

        labor = db.query(func.sum(TimeEntry.labor_cost)).filter(
            TimeEntry.job_id == job_id
        ).scalar() or 0

        parts = db.query(func.sum(JobMaterial.total_cost)).filter(
            JobMaterial.job_id == job_id, JobMaterial.quantity > 0
        ).scalar() or 0

        return jsonify({
            'labor_cost': round(float(labor), 2),
            'parts_cost': round(float(parts), 2),
            'total': round(float(labor) + float(parts), 2),
        })
    finally:
        db.close()


@warranty_bp.route('/api/job/<int:job_id>/warranty-status')
@login_required
def api_job_warranty_status(job_id):
    """Check if a job has an active warranty."""
    db = get_session()
    try:
        warranty = db.query(Warranty).filter(
            Warranty.job_id == job_id,
            Warranty.status.in_(['active', 'expiring_soon'])
        ).first()
        if warranty:
            return jsonify({
                'has_warranty': True,
                'warranty_id': warranty.id,
                'warranty_number': warranty.warranty_number,
                'title': warranty.title,
                'end_date': warranty.end_date.strftime('%b %d, %Y') if warranty.end_date else '',
                'days_remaining': warranty.days_remaining,
            })
        return jsonify({'has_warranty': False})
    finally:
        db.close()
