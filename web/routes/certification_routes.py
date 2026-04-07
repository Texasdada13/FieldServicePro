"""Routes for technician certification management."""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user
from models.database import get_session
from models.certification import TechnicianCertification
from models.technician import Technician
from models.division import Division
from web.utils.file_utils import save_uploaded_file
from web.auth import role_required

certifications_bp = Blueprint('certifications', __name__)


def _get_divisions():
    db = get_session()
    try:
        return db.query(Division).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Division.sort_order).all()
    finally:
        db.close()


def _tpl_vars(**extra):
    base = dict(active_page='certifications', user=current_user, divisions=_get_divisions())
    base.update(extra)
    return base


@certifications_bp.route('/settings/certifications')
@login_required
def certification_matrix():
    db = get_session()
    try:
        org_id = current_user.organization_id
        technicians = db.query(Technician).filter_by(
            organization_id=org_id, is_active=True
        ).order_by(Technician.first_name).all()
        cert_types = TechnicianCertification.CERT_TYPES

        matrix = {}
        for tech in technicians:
            matrix[tech.id] = {}
            certs = db.query(TechnicianCertification).filter_by(technician_id=tech.id).all()
            for c in certs:
                c.update_status()
                matrix[tech.id][c.certification_type] = c

        total = db.query(TechnicianCertification).count()
        expired = db.query(TechnicianCertification).filter_by(status='expired').count()
        expiring_list = [c for c in db.query(TechnicianCertification).filter(
            TechnicianCertification.status == 'expiring_soon').all()]

        db.commit()

        return render_template('certifications/certification_matrix.html',
                               **_tpl_vars(
                                   technicians=technicians, cert_types=cert_types,
                                   matrix=matrix, total_certs=total,
                                   expiring_count=len(expiring_list), expired_count=expired,
                               ))
    finally:
        db.close()


@certifications_bp.route('/settings/technicians/<int:tech_id>/certifications')
@login_required
def tech_certifications(tech_id):
    db = get_session()
    try:
        tech = db.query(Technician).filter_by(id=tech_id).first()
        if not tech:
            abort(404)
        certs = db.query(TechnicianCertification).filter_by(
            technician_id=tech_id).order_by(TechnicianCertification.expiry_date.asc()).all()
        for c in certs:
            c.update_status()
        db.commit()

        return render_template('certifications/tech_certifications.html',
                               **_tpl_vars(technician=tech, certifications=certs,
                                           cert_types=TechnicianCertification.CERT_TYPES))
    finally:
        db.close()


@certifications_bp.route('/settings/technicians/<int:tech_id>/certifications/new', methods=['GET', 'POST'])
@login_required
@role_required('owner', 'admin')
def certification_new(tech_id):
    db = get_session()
    try:
        tech = db.query(Technician).filter_by(id=tech_id).first()
        if not tech:
            abort(404)

        if request.method == 'POST':
            f = request.form
            cert = TechnicianCertification(
                technician_id=tech_id,
                certification_type=f.get('certification_type', 'other'),
                certification_name=f.get('certification_name', '').strip(),
                issuing_body=f.get('issuing_body', '').strip() or None,
                certificate_number=f.get('certificate_number', '').strip() or None,
                is_required=f.get('is_required') == 'on',
                renewal_reminder_days=int(f.get('renewal_reminder_days') or 30),
                notes=f.get('notes', '').strip() or None,
                created_by=current_user.id,
            )
            for df in ['issue_date', 'expiry_date']:
                val = f.get(df, '').strip()
                if val:
                    try:
                        setattr(cert, df, datetime.strptime(val, '%Y-%m-%d').date())
                    except ValueError:
                        pass

            cert.update_status()
            db.add(cert)
            db.flush()

            for file in request.files.getlist('documents'):
                if file and file.filename:
                    try:
                        save_uploaded_file(db, file, entity_type='certification',
                                           entity_id=cert.id, category='certification',
                                           uploaded_by=current_user.id)
                    except Exception:
                        pass

            db.commit()
            flash(f'Certification added for {tech.full_name}.', 'success')
            return redirect(url_for('certifications.tech_certifications', tech_id=tech_id))

        return render_template('certifications/certification_form.html',
                               **_tpl_vars(cert=None, technician=tech,
                                           cert_types=TechnicianCertification.CERT_TYPES))
    finally:
        db.close()


@certifications_bp.route('/settings/certifications/<int:cert_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('owner', 'admin')
def certification_edit(cert_id):
    db = get_session()
    try:
        cert = db.query(TechnicianCertification).filter_by(id=cert_id).first()
        if not cert:
            abort(404)
        tech = cert.technician

        if request.method == 'POST':
            f = request.form
            cert.certification_type = f.get('certification_type', cert.certification_type)
            cert.certification_name = f.get('certification_name', '').strip()
            cert.issuing_body = f.get('issuing_body', '').strip() or None
            cert.certificate_number = f.get('certificate_number', '').strip() or None
            cert.is_required = f.get('is_required') == 'on'
            cert.renewal_reminder_days = int(f.get('renewal_reminder_days') or 30)
            cert.notes = f.get('notes', '').strip() or None

            for df in ['issue_date', 'expiry_date']:
                val = f.get(df, '').strip()
                if val:
                    try:
                        setattr(cert, df, datetime.strptime(val, '%Y-%m-%d').date())
                    except ValueError:
                        pass
                elif df == 'expiry_date':
                    cert.expiry_date = None

            cert.update_status()

            for file in request.files.getlist('documents'):
                if file and file.filename:
                    try:
                        save_uploaded_file(db, file, entity_type='certification',
                                           entity_id=cert.id, category='certification',
                                           uploaded_by=current_user.id)
                    except Exception:
                        pass

            db.commit()
            flash('Certification updated.', 'success')
            return redirect(url_for('certifications.tech_certifications', tech_id=cert.technician_id))

        return render_template('certifications/certification_form.html',
                               **_tpl_vars(cert=cert, technician=tech,
                                           cert_types=TechnicianCertification.CERT_TYPES))
    finally:
        db.close()


@certifications_bp.route('/settings/certifications/<int:cert_id>/delete', methods=['POST'])
@login_required
@role_required('owner', 'admin')
def certification_delete(cert_id):
    db = get_session()
    try:
        cert = db.query(TechnicianCertification).filter_by(id=cert_id).first()
        if not cert:
            abort(404)
        tech_id = cert.technician_id
        db.delete(cert)
        db.commit()
        flash('Certification deleted.', 'success')
    finally:
        db.close()
    return redirect(url_for('certifications.tech_certifications', tech_id=tech_id))
