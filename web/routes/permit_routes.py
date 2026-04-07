"""Routes for permit management."""
from datetime import datetime
from flask import (Blueprint, render_template, request, redirect, url_for,
                   flash, jsonify, abort)
from flask_login import login_required, current_user
from models.database import get_session
from models.permit import Permit
from models.job import Job
from models.job_phase import JobPhase
from models.division import Division
from web.utils.file_utils import save_uploaded_file, get_entity_documents
from web.auth import role_required

permits_bp = Blueprint('permits', __name__)


def _get_divisions():
    db = get_session()
    try:
        return db.query(Division).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Division.sort_order).all()
    finally:
        db.close()


def _tpl_vars(**extra):
    base = dict(active_page='permits', user=current_user, divisions=_get_divisions())
    base.update(extra)
    return base


@permits_bp.route('/permits')
@login_required
def permit_list():
    db = get_session()
    try:
        org_id = current_user.organization_id
        job_id = request.args.get('job_id', type=int)
        permit_type = request.args.get('type', '')
        status = request.args.get('status', '')

        q = db.query(Permit).join(Job).filter(Job.organization_id == org_id)
        if job_id:
            q = q.filter(Permit.job_id == job_id)
        if permit_type:
            q = q.filter(Permit.permit_type == permit_type)
        if status:
            q = q.filter(Permit.status == status)

        permits = q.order_by(Permit.created_at.desc()).all()

        total = db.query(Permit).join(Job).filter(Job.organization_id == org_id).count()
        active = db.query(Permit).join(Job).filter(
            Job.organization_id == org_id,
            Permit.status.in_(['active', 'approved'])
        ).count()
        pending_inspection = db.query(Permit).join(Job).filter(
            Job.organization_id == org_id,
            Permit.status.in_(['inspection_required', 'inspection_failed'])
        ).count()
        expiring = len(Permit.get_expiring_soon(db))

        return render_template('permits/permit_list.html',
                               **_tpl_vars(
                                   permits=permits, total=total, active=active,
                                   pending_inspection=pending_inspection,
                                   expiring=expiring,
                                   filter_job_id=job_id,
                                   filter_type=permit_type,
                                   filter_status=status,
                                   permit_types=Permit.PERMIT_TYPES,
                                   status_choices=Permit.STATUS_CHOICES,
                               ))
    finally:
        db.close()


@permits_bp.route('/permits/new', methods=['GET', 'POST'])
@login_required
@role_required('owner', 'admin', 'dispatcher')
def permit_new():
    db = get_session()
    try:
        org_id = current_user.organization_id
        if request.method == 'POST':
            f = request.form
            permit = Permit(
                permit_number=f.get('permit_number', '').strip() or None,
                job_id=int(f['job_id']),
                phase_id=int(f['phase_id']) if f.get('phase_id') else None,
                permit_type=f.get('permit_type', 'other'),
                description=f.get('description', '').strip() or None,
                issuing_authority=f.get('issuing_authority', '').strip() or None,
                status=f.get('status', 'not_applied'),
                cost=float(f['cost']) if f.get('cost') else None,
                conditions=f.get('conditions', '').strip() or None,
                inspector_name=f.get('inspector_name', '').strip() or None,
                inspector_phone=f.get('inspector_phone', '').strip() or None,
                notes=f.get('notes', '').strip() or None,
                created_by=current_user.id,
            )
            for date_field in ['application_date', 'issue_date', 'expiry_date']:
                val = f.get(date_field, '').strip()
                if val:
                    try:
                        setattr(permit, date_field, datetime.strptime(val, '%Y-%m-%d').date())
                    except ValueError:
                        pass

            db.add(permit)
            db.flush()

            # Handle file uploads
            files = request.files.getlist('documents')
            for file in files:
                if file and file.filename:
                    try:
                        save_uploaded_file(db, file, entity_type='permit',
                                           entity_id=permit.id, category='permit',
                                           uploaded_by=current_user.id)
                    except Exception:
                        pass

            db.commit()
            flash('Permit created.', 'success')
            return redirect(url_for('permits.permit_detail', permit_id=permit.id))

        jobs = db.query(Job).filter(
            Job.organization_id == org_id,
            Job.status.in_(['scheduled', 'in_progress'])
        ).order_by(Job.created_at.desc()).all()
        preselect_job_id = request.args.get('job_id', type=int)
        phases = []
        if preselect_job_id:
            phases = db.query(JobPhase).filter_by(job_id=preselect_job_id).all()

        return render_template('permits/permit_form.html',
                               **_tpl_vars(
                                   permit=None, jobs=jobs, phases=phases,
                                   preselect_job_id=preselect_job_id,
                                   permit_types=Permit.PERMIT_TYPES,
                                   status_choices=Permit.STATUS_CHOICES,
                               ))
    finally:
        db.close()


@permits_bp.route('/permits/<int:permit_id>')
@login_required
def permit_detail(permit_id):
    db = get_session()
    try:
        permit = db.query(Permit).filter_by(id=permit_id).first()
        if not permit:
            abort(404)
        documents = get_entity_documents(db, 'permit', permit.id)
        return render_template('permits/permit_detail.html',
                               **_tpl_vars(permit=permit, documents=documents))
    finally:
        db.close()


@permits_bp.route('/permits/<int:permit_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('owner', 'admin', 'dispatcher')
def permit_edit(permit_id):
    db = get_session()
    try:
        permit = db.query(Permit).filter_by(id=permit_id).first()
        if not permit:
            abort(404)

        if request.method == 'POST':
            f = request.form
            permit.permit_number = f.get('permit_number', '').strip() or None
            permit.job_id = int(f['job_id'])
            permit.phase_id = int(f['phase_id']) if f.get('phase_id') else None
            permit.permit_type = f.get('permit_type', 'other')
            permit.description = f.get('description', '').strip() or None
            permit.issuing_authority = f.get('issuing_authority', '').strip() or None
            permit.status = f.get('status', permit.status)
            permit.cost = float(f['cost']) if f.get('cost') else None
            permit.conditions = f.get('conditions', '').strip() or None
            permit.inspector_name = f.get('inspector_name', '').strip() or None
            permit.inspector_phone = f.get('inspector_phone', '').strip() or None
            permit.notes = f.get('notes', '').strip() or None

            for date_field in ['application_date', 'issue_date', 'expiry_date']:
                val = f.get(date_field, '').strip()
                if val:
                    try:
                        setattr(permit, date_field, datetime.strptime(val, '%Y-%m-%d').date())
                    except ValueError:
                        pass
                else:
                    setattr(permit, date_field, None)

            files = request.files.getlist('documents')
            for file in files:
                if file and file.filename:
                    try:
                        save_uploaded_file(db, file, entity_type='permit',
                                           entity_id=permit.id, category='permit',
                                           uploaded_by=current_user.id)
                    except Exception:
                        pass

            db.commit()
            flash('Permit updated.', 'success')
            return redirect(url_for('permits.permit_detail', permit_id=permit.id))

        org_id = current_user.organization_id
        jobs = db.query(Job).filter(
            Job.organization_id == org_id,
            Job.status.in_(['scheduled', 'in_progress'])
        ).order_by(Job.created_at.desc()).all()
        phases = db.query(JobPhase).filter_by(job_id=permit.job_id).all()

        return render_template('permits/permit_form.html',
                               **_tpl_vars(
                                   permit=permit, jobs=jobs, phases=phases,
                                   preselect_job_id=permit.job_id,
                                   permit_types=Permit.PERMIT_TYPES,
                                   status_choices=Permit.STATUS_CHOICES,
                               ))
    finally:
        db.close()


@permits_bp.route('/permits/<int:permit_id>/add-inspection', methods=['POST'])
@login_required
@role_required('owner', 'admin', 'dispatcher')
def permit_add_inspection(permit_id):
    db = get_session()
    try:
        permit = db.query(Permit).filter_by(id=permit_id).first()
        if not permit:
            abort(404)

        inspection_date = request.form.get('inspection_date', '').strip()
        result = request.form.get('result', 'passed')
        inspector = request.form.get('inspector', '').strip() or None
        notes = request.form.get('inspection_notes', '').strip() or None

        if not inspection_date:
            flash('Inspection date required.', 'danger')
            return redirect(url_for('permits.permit_detail', permit_id=permit_id))

        permit.add_inspection(inspection_date, result, inspector, notes)
        db.commit()
        flash(f'Inspection recorded: {result}', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {str(e)}', 'danger')
    finally:
        db.close()
    return redirect(url_for('permits.permit_detail', permit_id=permit_id))


@permits_bp.route('/permits/<int:permit_id>/delete', methods=['POST'])
@login_required
@role_required('owner', 'admin')
def permit_delete(permit_id):
    db = get_session()
    try:
        permit = db.query(Permit).filter_by(id=permit_id).first()
        if not permit:
            abort(404)
        job_id = permit.job_id
        db.delete(permit)
        db.commit()
        flash('Permit deleted.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {str(e)}', 'danger')
    finally:
        db.close()
    return redirect(url_for('permits.permit_list', job_id=job_id))


# -- API: Phases for job (used in permit form) --

@permits_bp.route('/api/jobs/<int:job_id>/phases')
@login_required
def api_job_phases(job_id):
    db = get_session()
    try:
        phases = db.query(JobPhase).filter_by(job_id=job_id)\
                   .order_by(JobPhase.sort_order).all()
        return jsonify([{
            'id': p.id,
            'name': f"Phase {p.phase_number}: {p.title}",
            'status': p.status,
        } for p in phases])
    finally:
        db.close()
