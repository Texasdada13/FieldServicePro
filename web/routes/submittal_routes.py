"""Submittal routes — list, detail, create, edit, review, revise."""
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from models.database import get_session
from models.submittal import Submittal, SUBMITTAL_TYPES, SUBMITTAL_STATUSES, STATUS_COLORS
from models.project import Project
from models.job import Job
from models.job_phase import JobPhase
from models.user import User
from models.division import Division
from web.auth import role_required

submittal_bp = Blueprint('submittals', __name__)


def _get_divisions():
    db = get_session()
    try:
        return db.query(Division).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Division.sort_order).all()
    finally:
        db.close()


def _parse_date(val):
    if not val:
        return None
    try:
        return datetime.strptime(val, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


# ── List ──────────────────────────────────────────────────────────────────────

@submittal_bp.route('/submittals')
@login_required
def submittal_list():
    db = get_session()
    try:
        org_id = current_user.organization_id
        project_id = request.args.get('project_id', type=int)
        status_filter = request.args.get('status', '')
        type_filter = request.args.get('submittal_type', '')

        q = db.query(Submittal).join(Project).filter(Project.organization_id == org_id)
        if project_id:
            q = q.filter(Submittal.project_id == project_id)
        if status_filter:
            q = q.filter(Submittal.status == status_filter)
        if type_filter:
            q = q.filter(Submittal.submittal_type == type_filter)

        submittals = q.order_by(Submittal.date_submitted.desc()).all()

        from web.utils.submittal_utils import get_submittal_stats
        stats = get_submittal_stats(db, project_id=project_id)
        projects = db.query(Project).filter_by(organization_id=org_id).order_by(Project.title).all()

        return render_template('submittals/submittal_list.html',
            active_page='submittals', user=current_user, divisions=_get_divisions(),
            submittals=submittals, stats=stats, projects=projects,
            submittal_types=SUBMITTAL_TYPES, submittal_statuses=SUBMITTAL_STATUSES,
            today=date.today(),
            filters={'project_id': project_id, 'status': status_filter, 'submittal_type': type_filter},
        )
    finally:
        db.close()


# ── Detail ────────────────────────────────────────────────────────────────────

@submittal_bp.route('/submittals/<int:sub_id>')
@login_required
def submittal_detail(sub_id):
    db = get_session()
    try:
        sub = db.query(Submittal).filter_by(id=sub_id).first()
        if not sub:
            flash('Submittal not found.', 'error')
            return redirect(url_for('submittals.submittal_list'))

        # Build revision chain
        revisions = []
        current = sub
        while current.previous_submittal:
            revisions.append(current.previous_submittal)
            current = current.previous_submittal

        return render_template('submittals/submittal_detail.html',
            active_page='submittals', user=current_user, divisions=_get_divisions(),
            sub=sub, revisions=revisions, submittal_types=SUBMITTAL_TYPES,
            today=date.today(),
        )
    finally:
        db.close()


# ── Create ────────────────────────────────────────────────────────────────────

@submittal_bp.route('/submittals/new', methods=['GET', 'POST'])
@submittal_bp.route('/submittals/new/<int:project_id>', methods=['GET', 'POST'])
@login_required
def submittal_new(project_id=None):
    db = get_session()
    try:
        org_id = current_user.organization_id
        projects = db.query(Project).filter_by(organization_id=org_id).order_by(Project.title).all()
        users = db.query(User).filter_by(organization_id=org_id, is_active=True).order_by(User.first_name).all()
        jobs = db.query(Job).filter_by(project_id=project_id).all() if project_id else []
        project = db.query(Project).filter_by(id=project_id).first() if project_id else None

        if request.method == 'POST':
            pid = int(request.form['project_id'])
            qty = int(request.form['quantity']) if request.form.get('quantity') else None
            unit_cost = float(request.form['unit_cost']) if request.form.get('unit_cost') else None
            total_cost = (qty * unit_cost) if qty and unit_cost else (float(request.form['total_cost']) if request.form.get('total_cost') else None)

            sub = Submittal(
                submittal_number=Submittal.next_number(db, pid),
                project_id=pid,
                job_id=int(request.form['job_id']) if request.form.get('job_id') else None,
                phase_id=int(request.form['phase_id']) if request.form.get('phase_id') else None,
                title=request.form['title'].strip(),
                description=request.form.get('description', '').strip() or None,
                spec_section=request.form.get('spec_section', '').strip() or None,
                submittal_type=request.form.get('submittal_type', 'product_data'),
                manufacturer=request.form.get('manufacturer', '').strip() or None,
                model_number=request.form.get('model_number', '').strip() or None,
                product_description=request.form.get('product_description', '').strip() or None,
                quantity=qty, unit_cost=unit_cost, total_cost=total_cost,
                alternatives_considered=request.form.get('alternatives_considered', '').strip() or None,
                submitted_by_id=current_user.id,
                submitted_to=request.form.get('submitted_to', '').strip() or None,
                submitted_to_email=request.form.get('submitted_to_email', '').strip() or None,
                status=request.form.get('status', 'draft'),
                date_submitted=date.today(),
                date_required=_parse_date(request.form.get('date_required')),
                lead_time_days=int(request.form['lead_time_days']) if request.form.get('lead_time_days') else None,
                notes=request.form.get('notes', '').strip() or None,
            )
            db.add(sub)
            db.commit()
            flash(f'Submittal {sub.submittal_number} created.', 'success')
            return redirect(url_for('submittals.submittal_detail', sub_id=sub.id))

        return render_template('submittals/submittal_form.html',
            active_page='submittals', user=current_user, divisions=_get_divisions(),
            sub=None, projects=projects, users=users, jobs=jobs, project=project,
            submittal_types=SUBMITTAL_TYPES,
        )
    finally:
        db.close()


# ── Edit ──────────────────────────────────────────────────────────────────────

@submittal_bp.route('/submittals/<int:sub_id>/edit', methods=['GET', 'POST'])
@login_required
def submittal_edit(sub_id):
    db = get_session()
    try:
        sub = db.query(Submittal).filter_by(id=sub_id).first()
        if not sub:
            flash('Submittal not found.', 'error')
            return redirect(url_for('submittals.submittal_list'))

        if sub.status in ('approved', 'void'):
            flash('Cannot edit an approved or voided submittal.', 'warning')
            return redirect(url_for('submittals.submittal_detail', sub_id=sub_id))

        org_id = current_user.organization_id
        projects = db.query(Project).filter_by(organization_id=org_id).order_by(Project.title).all()
        jobs = db.query(Job).filter_by(project_id=sub.project_id).all()

        if request.method == 'POST':
            sub.title = request.form['title'].strip()
            sub.description = request.form.get('description', '').strip() or None
            sub.spec_section = request.form.get('spec_section', '').strip() or None
            sub.submittal_type = request.form.get('submittal_type', sub.submittal_type)
            sub.manufacturer = request.form.get('manufacturer', '').strip() or None
            sub.model_number = request.form.get('model_number', '').strip() or None
            sub.product_description = request.form.get('product_description', '').strip() or None
            sub.quantity = int(request.form['quantity']) if request.form.get('quantity') else None
            sub.unit_cost = float(request.form['unit_cost']) if request.form.get('unit_cost') else None
            sub.total_cost = (sub.quantity * sub.unit_cost) if sub.quantity and sub.unit_cost else None
            sub.submitted_to = request.form.get('submitted_to', '').strip() or None
            sub.submitted_to_email = request.form.get('submitted_to_email', '').strip() or None
            sub.date_required = _parse_date(request.form.get('date_required'))
            sub.lead_time_days = int(request.form['lead_time_days']) if request.form.get('lead_time_days') else None
            sub.notes = request.form.get('notes', '').strip() or None
            db.commit()
            flash(f'Submittal {sub.submittal_number} updated.', 'success')
            return redirect(url_for('submittals.submittal_detail', sub_id=sub_id))

        return render_template('submittals/submittal_form.html',
            active_page='submittals', user=current_user, divisions=_get_divisions(),
            sub=sub, projects=projects, jobs=jobs, project=sub.project,
            submittal_types=SUBMITTAL_TYPES,
        )
    finally:
        db.close()


# ── Review ────────────────────────────────────────────────────────────────────

@submittal_bp.route('/submittals/<int:sub_id>/review', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'owner', 'dispatcher')
def submittal_review(sub_id):
    db = get_session()
    try:
        sub = db.query(Submittal).filter_by(id=sub_id).first()
        if not sub:
            flash('Submittal not found.', 'error')
            return redirect(url_for('submittals.submittal_list'))

        if request.method == 'POST':
            new_status = request.form['status']
            sub.status = new_status
            sub.review_comments = request.form.get('review_comments', '').strip() or None
            sub.reviewer_name = request.form.get('reviewer_name', '').strip() or None
            sub.date_reviewed = date.today()

            if new_status in ('approved', 'approved_as_noted') and sub.lead_time_days:
                sub.delivery_date = date.today() + timedelta(days=sub.lead_time_days)

            db.commit()

            try:
                from web.utils.notification_service import NotificationService
                NotificationService.notify('system', sub, triggered_by=current_user,
                                           title=f'Submittal {sub.submittal_number} - {new_status.replace("_"," ").title()}',
                                           message=f'"{sub.title}" review decision: {new_status.replace("_"," ").title()}.',
                                           override_recipients=[sub.submitted_by] if sub.submitted_by else None)
            except Exception:
                pass

            flash(f'Submittal {sub.submittal_number} marked as {new_status.replace("_"," ").title()}.', 'success')
            return redirect(url_for('submittals.submittal_detail', sub_id=sub_id))

        return render_template('submittals/submittal_review.html',
            active_page='submittals', user=current_user, divisions=_get_divisions(),
            sub=sub, submittal_statuses=SUBMITTAL_STATUSES,
        )
    finally:
        db.close()


# ── Revise ────────────────────────────────────────────────────────────────────

@submittal_bp.route('/submittals/<int:sub_id>/revise', methods=['POST'])
@login_required
def submittal_revise(sub_id):
    db = get_session()
    try:
        orig = db.query(Submittal).filter_by(id=sub_id).first()
        if not orig or orig.status != 'revise_and_resubmit':
            flash('Only "Revise and Resubmit" submittals can be revised.', 'warning')
            return redirect(url_for('submittals.submittal_detail', sub_id=sub_id))

        revision = Submittal(
            submittal_number=Submittal.next_number(db, orig.project_id),
            project_id=orig.project_id, job_id=orig.job_id, phase_id=orig.phase_id,
            title=orig.title, description=orig.description, spec_section=orig.spec_section,
            submittal_type=orig.submittal_type,
            manufacturer=orig.manufacturer, model_number=orig.model_number,
            product_description=orig.product_description,
            quantity=orig.quantity, unit_cost=orig.unit_cost,
            submitted_by_id=current_user.id,
            submitted_to=orig.submitted_to, submitted_to_email=orig.submitted_to_email,
            status='draft', date_submitted=date.today(), date_required=orig.date_required,
            lead_time_days=orig.lead_time_days,
            revision_number=orig.revision_number + 1,
            previous_submittal_id=orig.id,
        )
        db.add(revision)
        db.commit()
        flash(f'Revision {revision.submittal_number} (Rev {revision.revision_number}) created.', 'success')
        return redirect(url_for('submittals.submittal_edit', sub_id=revision.id))
    finally:
        db.close()
