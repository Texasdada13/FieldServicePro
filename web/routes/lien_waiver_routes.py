"""Routes for lien waiver management."""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from models.database import get_session
from models.lien_waiver import LienWaiver
from models.job import Job
from models.invoice import Invoice
from models.division import Division
from web.utils.file_utils import save_uploaded_file, get_entity_documents
from web.auth import role_required

lien_waivers_bp = Blueprint('lien_waivers', __name__)


def _get_divisions():
    db = get_session()
    try:
        return db.query(Division).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Division.sort_order).all()
    finally:
        db.close()


def _tpl_vars(**extra):
    base = dict(active_page='lien_waivers', user=current_user, divisions=_get_divisions())
    base.update(extra)
    return base


@lien_waivers_bp.route('/jobs/<int:job_id>/lien-waivers')
@login_required
def lien_waiver_list(job_id):
    """List lien waivers for a job."""
    db = get_session()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            abort(404)

        waivers = db.query(LienWaiver).filter_by(job_id=job_id).order_by(
            LienWaiver.created_at.desc()
        ).all()

        pending = [w for w in waivers if w.status not in ('accepted',)]
        accepted = [w for w in waivers if w.status == 'accepted']
        total_amount = sum(float(w.amount or 0) for w in accepted)

        return render_template('lien_waivers/lien_waiver_list.html',
                               **_tpl_vars(
                                   job=job, waivers=waivers,
                                   pending_count=len(pending),
                                   accepted_count=len(accepted),
                                   total_amount=total_amount,
                                   waiver_types=LienWaiver.WAIVER_TYPES,
                                   status_choices=LienWaiver.STATUS_CHOICES,
                                   active_page='jobs',
                               ))
    finally:
        db.close()


@lien_waivers_bp.route('/jobs/<int:job_id>/lien-waivers/new', methods=['GET', 'POST'])
@login_required
@role_required('owner', 'admin')
def lien_waiver_new(job_id):
    """Create a new lien waiver."""
    db = get_session()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            abort(404)

        if request.method == 'POST':
            f = request.form
            waiver = LienWaiver(
                job_id=job_id,
                waiver_type=f.get('waiver_type', 'conditional_progress'),
                party_type=f.get('party_type', 'subcontractor'),
                party_name=f.get('party_name', '').strip(),
                amount=float(f.get('amount') or 0) if f.get('amount') else None,
                invoice_id=int(f.get('invoice_id')) if f.get('invoice_id') else None,
                status=f.get('status', 'requested'),
                notes=f.get('notes', '').strip() or None,
                created_by=current_user.id,
            )

            for df in ['through_date', 'requested_date', 'received_date']:
                val = f.get(df, '').strip()
                if val:
                    try:
                        setattr(waiver, df, datetime.strptime(val, '%Y-%m-%d').date())
                    except ValueError:
                        pass

            db.add(waiver)
            db.flush()

            for file in request.files.getlist('documents'):
                if file and file.filename:
                    try:
                        save_uploaded_file(db, file, entity_type='lien_waiver',
                                           entity_id=waiver.id, category='lien_waiver',
                                           uploaded_by=current_user.id)
                    except Exception:
                        pass

            db.commit()
            flash('Lien waiver created.', 'success')
            return redirect(url_for('lien_waivers.lien_waiver_list', job_id=job_id))

        invoices = db.query(Invoice).filter_by(job_id=job_id).all()
        return render_template('lien_waivers/lien_waiver_form.html',
                               **_tpl_vars(
                                   waiver=None, job=job, invoices=invoices,
                                   waiver_types=LienWaiver.WAIVER_TYPES,
                                   party_types=LienWaiver.PARTY_TYPES,
                                   status_choices=LienWaiver.STATUS_CHOICES,
                                   active_page='jobs',
                               ))
    finally:
        db.close()


@lien_waivers_bp.route('/lien-waivers/<int:waiver_id>')
@login_required
def lien_waiver_detail(waiver_id):
    """View lien waiver details."""
    db = get_session()
    try:
        waiver = db.query(LienWaiver).filter_by(id=waiver_id).first()
        if not waiver:
            abort(404)
        documents = get_entity_documents(db, 'lien_waiver', waiver.id)
        return render_template('lien_waivers/lien_waiver_detail.html',
                               **_tpl_vars(
                                   waiver=waiver, documents=documents,
                                   active_page='jobs',
                               ))
    finally:
        db.close()


@lien_waivers_bp.route('/lien-waivers/<int:waiver_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('owner', 'admin')
def lien_waiver_edit(waiver_id):
    """Edit a lien waiver."""
    db = get_session()
    try:
        waiver = db.query(LienWaiver).filter_by(id=waiver_id).first()
        if not waiver:
            abort(404)

        if request.method == 'POST':
            f = request.form
            waiver.waiver_type = f.get('waiver_type', waiver.waiver_type)
            waiver.party_type = f.get('party_type', waiver.party_type)
            waiver.party_name = f.get('party_name', '').strip()
            waiver.amount = float(f.get('amount') or 0) if f.get('amount') else None
            waiver.invoice_id = int(f.get('invoice_id')) if f.get('invoice_id') else None
            waiver.status = f.get('status', waiver.status)
            waiver.notes = f.get('notes', '').strip() or None

            for df in ['through_date', 'requested_date', 'received_date']:
                val = f.get(df, '').strip()
                if val:
                    try:
                        setattr(waiver, df, datetime.strptime(val, '%Y-%m-%d').date())
                    except ValueError:
                        pass
                else:
                    setattr(waiver, df, None)

            for file in request.files.getlist('documents'):
                if file and file.filename:
                    try:
                        save_uploaded_file(db, file, entity_type='lien_waiver',
                                           entity_id=waiver.id, category='lien_waiver',
                                           uploaded_by=current_user.id)
                    except Exception:
                        pass

            db.commit()
            flash('Lien waiver updated.', 'success')
            return redirect(url_for('lien_waivers.lien_waiver_detail', waiver_id=waiver.id))

        job = waiver.job
        invoices = db.query(Invoice).filter_by(job_id=waiver.job_id).all()
        return render_template('lien_waivers/lien_waiver_form.html',
                               **_tpl_vars(
                                   waiver=waiver, job=job, invoices=invoices,
                                   waiver_types=LienWaiver.WAIVER_TYPES,
                                   party_types=LienWaiver.PARTY_TYPES,
                                   status_choices=LienWaiver.STATUS_CHOICES,
                                   active_page='jobs',
                               ))
    finally:
        db.close()


@lien_waivers_bp.route('/lien-waivers/<int:waiver_id>/delete', methods=['POST'])
@login_required
@role_required('owner', 'admin')
def lien_waiver_delete(waiver_id):
    db = get_session()
    try:
        waiver = db.query(LienWaiver).filter_by(id=waiver_id).first()
        if not waiver:
            abort(404)
        job_id = waiver.job_id
        db.delete(waiver)
        db.commit()
        flash('Lien waiver deleted.', 'success')
    finally:
        db.close()
    return redirect(url_for('lien_waivers.lien_waiver_list', job_id=job_id))
