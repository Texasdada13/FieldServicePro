"""Routes for project management."""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, jsonify
from flask_login import login_required, current_user
from sqlalchemy import desc
from models.database import get_session
from models.project import Project, ProjectNote
from models.job import Job
from models.invoice import Invoice
from models.purchase_order import PurchaseOrder
from models.permit import Permit
from models.change_order import ChangeOrder
from models.client import Client, Property
from models.division import Division
from models.user import User
from models.technician import Technician
from web.auth import role_required

projects_bp = Blueprint('projects_bp', __name__)


def _get_divisions():
    db = get_session()
    try:
        return db.query(Division).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Division.sort_order).all()
    finally:
        db.close()


def _tpl_vars(**extra):
    base = dict(active_page='projects', user=current_user, divisions=_get_divisions())
    base.update(extra)
    return base


@projects_bp.route('/projects')
@login_required
def project_list():
    db = get_session()
    try:
        org_id = current_user.organization_id
        query = db.query(Project).filter_by(organization_id=org_id)

        status = request.args.get('status', '')
        search = request.args.get('search', '').strip()

        if status:
            query = query.filter(Project.status == status)
        if search:
            s = f'%{search}%'
            from sqlalchemy import or_
            query = query.filter(or_(
                Project.title.ilike(s),
                Project.project_number.ilike(s),
            ))

        projects = query.order_by(desc(Project.created_at)).all()

        # Stats
        total = db.query(Project).filter_by(organization_id=org_id).count()
        active = db.query(Project).filter_by(organization_id=org_id, status='active').count()
        planning = db.query(Project).filter_by(organization_id=org_id, status='planning').count()
        completed = db.query(Project).filter_by(organization_id=org_id, status='completed').count()

        return render_template('projects/project_list.html',
            **_tpl_vars(
                projects=projects, total=total, active_count=active,
                planning_count=planning, completed_count=completed,
                filter_status=status, search=search,
            ))
    finally:
        db.close()


@projects_bp.route('/projects/new', methods=['GET', 'POST'])
@login_required
@role_required('owner', 'admin')
def project_new():
    db = get_session()
    try:
        org_id = current_user.organization_id

        if request.method == 'POST':
            f = request.form
            project = Project(
                organization_id=org_id,
                project_number=Project.generate_project_number(db),
                title=f.get('title', '').strip(),
                description=f.get('description', '').strip() or None,
                status=f.get('status', 'planning'),
                priority=f.get('priority', 'medium'),
                percent_complete=0,
                created_by=current_user.id,
            )

            for fld in ['client_id', 'property_id', 'division_id', 'project_manager_id',
                         'site_supervisor_id', 'contract_id']:
                val = f.get(fld, '').strip()
                if val:
                    setattr(project, fld, int(val))

            for fld in ['estimated_budget', 'approved_budget']:
                val = f.get(fld, '').strip()
                if val:
                    setattr(project, fld, float(val))

            for fld in ['estimated_start_date', 'estimated_end_date']:
                val = f.get(fld, '').strip()
                if val:
                    try:
                        setattr(project, fld, datetime.strptime(val, '%Y-%m-%d').date())
                    except ValueError:
                        pass

            project.client_contact_name = f.get('client_contact_name', '').strip() or None
            project.client_contact_phone = f.get('client_contact_phone', '').strip() or None
            project.client_contact_email = f.get('client_contact_email', '').strip() or None
            project.notes = f.get('notes', '').strip() or None

            if not project.title or not project.client_id:
                flash('Title and client are required.', 'danger')
            else:
                db.add(project)
                db.commit()
                flash(f'Project {project.project_number} created.', 'success')
                return redirect(url_for('projects_bp.project_detail', project_id=project.id))

        clients = db.query(Client).filter_by(organization_id=org_id, is_active=True).order_by(Client.company_name).all()
        users = db.query(User).filter_by(organization_id=org_id, is_active=True).all()
        techs = db.query(Technician).filter_by(organization_id=org_id, is_active=True).all()

        return render_template('projects/project_form.html',
            **_tpl_vars(project=None, clients=clients, users=users, techs=techs))
    finally:
        db.close()


@projects_bp.route('/projects/<int:project_id>')
@login_required
def project_detail(project_id):
    db = get_session()
    try:
        project = db.query(Project).filter_by(
            id=project_id, organization_id=current_user.organization_id
        ).first()
        if not project:
            abort(404)

        # Related entities
        jobs = db.query(Job).filter_by(project_id=project.id).order_by(desc(Job.created_at)).all()
        invoices = db.query(Invoice).filter_by(project_id=project.id).order_by(desc(Invoice.created_at)).all()
        pos = db.query(PurchaseOrder).filter_by(project_id=project.id).all()
        permits_list = db.query(Permit).filter_by(project_id=project.id).all()
        notes = db.query(ProjectNote).filter_by(project_id=project.id).order_by(desc(ProjectNote.created_at)).all()

        # Also get jobs' invoices if invoice.project_id isn't set but job is
        job_ids = [j.id for j in jobs]
        if job_ids:
            job_invoices = db.query(Invoice).filter(
                Invoice.job_id.in_(job_ids), Invoice.project_id == None
            ).all()
            invoices = list(invoices) + job_invoices

        # Financial summary
        total_estimated = sum(float(j.estimated_amount or 0) for j in jobs)
        total_invoiced = sum(float(i.total or 0) for i in invoices)
        total_paid = sum(float(i.amount_paid or 0) for i in invoices)
        total_outstanding = sum(float(i.balance_due or 0) for i in invoices)
        budget = float(project.approved_budget or project.estimated_budget or 0)
        budget_variance = budget - total_estimated

        # Change orders on project jobs
        cos = []
        if job_ids:
            cos = db.query(ChangeOrder).filter(ChangeOrder.job_id.in_(job_ids)).all()

        return render_template('projects/project_detail.html',
            **_tpl_vars(
                project=project, jobs=jobs, invoices=invoices,
                purchase_orders=pos, permits=permits_list, notes=notes,
                change_orders=cos,
                total_estimated=total_estimated, total_invoiced=total_invoiced,
                total_paid=total_paid, total_outstanding=total_outstanding,
                budget=budget, budget_variance=budget_variance,
            ))
    finally:
        db.close()


@projects_bp.route('/projects/<int:project_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('owner', 'admin')
def project_edit(project_id):
    db = get_session()
    try:
        project = db.query(Project).filter_by(
            id=project_id, organization_id=current_user.organization_id
        ).first()
        if not project:
            abort(404)

        if request.method == 'POST':
            f = request.form
            project.title = f.get('title', project.title).strip()
            project.description = f.get('description', '').strip() or None
            project.status = f.get('status', project.status)
            project.priority = f.get('priority', project.priority)
            project.percent_complete = int(f.get('percent_complete', project.percent_complete) or 0)

            for fld in ['client_id', 'property_id', 'division_id', 'project_manager_id',
                         'site_supervisor_id', 'contract_id']:
                val = f.get(fld, '').strip()
                setattr(project, fld, int(val) if val else None)

            for fld in ['estimated_budget', 'approved_budget']:
                val = f.get(fld, '').strip()
                setattr(project, fld, float(val) if val else None)

            for fld in ['estimated_start_date', 'estimated_end_date', 'actual_start_date', 'actual_end_date']:
                val = f.get(fld, '').strip()
                if val:
                    try:
                        setattr(project, fld, datetime.strptime(val, '%Y-%m-%d').date())
                    except ValueError:
                        pass
                else:
                    setattr(project, fld, None)

            project.client_contact_name = f.get('client_contact_name', '').strip() or None
            project.client_contact_phone = f.get('client_contact_phone', '').strip() or None
            project.client_contact_email = f.get('client_contact_email', '').strip() or None
            project.notes = f.get('notes', '').strip() or None

            db.commit()
            flash('Project updated.', 'success')
            return redirect(url_for('projects_bp.project_detail', project_id=project.id))

        org_id = current_user.organization_id
        clients = db.query(Client).filter_by(organization_id=org_id, is_active=True).order_by(Client.company_name).all()
        users = db.query(User).filter_by(organization_id=org_id, is_active=True).all()
        techs = db.query(Technician).filter_by(organization_id=org_id, is_active=True).all()

        return render_template('projects/project_form.html',
            **_tpl_vars(project=project, clients=clients, users=users, techs=techs))
    finally:
        db.close()


@projects_bp.route('/projects/<int:project_id>/notes', methods=['POST'])
@login_required
def project_add_note(project_id):
    db = get_session()
    try:
        project = db.query(Project).filter_by(
            id=project_id, organization_id=current_user.organization_id
        ).first()
        if not project:
            return jsonify({'success': False, 'error': 'Not found'}), 404

        data = request.get_json() or request.form
        content = (data.get('content') or '').strip()
        if not content:
            return jsonify({'success': False, 'error': 'Content required'}), 400

        note = ProjectNote(
            project_id=project.id,
            content=content,
            note_type=data.get('note_type', 'general'),
            created_by=current_user.id,
        )
        db.add(note)
        db.commit()
        flash('Note added.', 'success')
        return redirect(url_for('projects_bp.project_detail', project_id=project_id))
    finally:
        db.close()


@projects_bp.route('/projects/<int:project_id>/link-job', methods=['POST'])
@login_required
@role_required('owner', 'admin', 'dispatcher')
def project_link_job(project_id):
    """Link an existing standalone job to this project."""
    db = get_session()
    try:
        project = db.query(Project).filter_by(
            id=project_id, organization_id=current_user.organization_id
        ).first()
        if not project:
            abort(404)

        job_id = request.form.get('job_id', '').strip()
        if job_id:
            job = db.query(Job).filter_by(id=int(job_id), organization_id=current_user.organization_id).first()
            if job:
                job.project_id = project.id
                db.commit()
                flash(f'Job {job.job_number} linked to project.', 'success')
            else:
                flash('Job not found.', 'danger')
        return redirect(url_for('projects_bp.project_detail', project_id=project_id))
    finally:
        db.close()


@projects_bp.route('/projects/<int:project_id>/unlink-job/<int:job_id>', methods=['POST'])
@login_required
@role_required('owner', 'admin')
def project_unlink_job(project_id, job_id):
    """Remove a job from this project (doesn't delete the job)."""
    db = get_session()
    try:
        job = db.query(Job).filter_by(
            id=job_id, organization_id=current_user.organization_id
        ).first()
        if job and job.project_id == project_id:
            job.project_id = None
            db.commit()
            flash(f'Job {job.job_number} removed from project.', 'success')
        return redirect(url_for('projects_bp.project_detail', project_id=project_id))
    finally:
        db.close()


@projects_bp.route('/projects/<int:project_id>/delete', methods=['POST'])
@login_required
@role_required('owner', 'admin')
def project_delete(project_id):
    """Delete a project (unlinks all related entities, doesn't delete them)."""
    db = get_session()
    try:
        project = db.query(Project).filter_by(
            id=project_id, organization_id=current_user.organization_id
        ).first()
        if not project:
            abort(404)

        # Unlink related entities
        db.query(Job).filter_by(project_id=project.id).update({Job.project_id: None})
        db.query(Invoice).filter_by(project_id=project.id).update({Invoice.project_id: None})
        db.query(PurchaseOrder).filter_by(project_id=project.id).update({PurchaseOrder.project_id: None})
        db.query(Permit).filter_by(project_id=project.id).update({Permit.project_id: None})

        # Delete notes
        db.query(ProjectNote).filter_by(project_id=project.id).delete()

        db.delete(project)
        db.commit()
        flash(f'Project {project.project_number} deleted.', 'success')
        return redirect(url_for('projects_bp.project_list'))
    finally:
        db.close()
