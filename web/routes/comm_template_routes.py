"""Communication Template CRUD — /settings/communication-templates."""
from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from models.database import get_session
from models.communication import (
    CommunicationTemplate, COMM_TYPES, COMM_PRIORITIES,
)
from models.division import Division
from web.auth import role_required

comm_templates_bp = Blueprint('comm_templates', __name__,
                               url_prefix='/settings/communication-templates')


def _get_divisions():
    db = get_session()
    try:
        return db.query(Division).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Division.sort_order).all()
    finally:
        db.close()


@comm_templates_bp.route('/')
@login_required
def template_list():
    db = get_session()
    try:
        templates = db.query(CommunicationTemplate).order_by(CommunicationTemplate.name).all()

        return render_template('communications/template_list.html',
            active_page='settings', user=current_user, divisions=_get_divisions(),
            templates=templates, comm_types=COMM_TYPES,
        )
    finally:
        db.close()


@comm_templates_bp.route('/new', methods=['GET', 'POST'])
@login_required
@role_required('owner', 'admin')
def template_new():
    db = get_session()
    try:
        if request.method == 'POST':
            t = _save_template(db, None)
            flash(f'Template "{t.name}" created.', 'success')
            return redirect(url_for('comm_templates.template_list'))

        return render_template('communications/template_form.html',
            active_page='settings', user=current_user, divisions=_get_divisions(),
            template=None, comm_types=COMM_TYPES, comm_priorities=COMM_PRIORITIES,
        )
    finally:
        db.close()


@comm_templates_bp.route('/<int:tid>/edit', methods=['GET', 'POST'])
@login_required
@role_required('owner', 'admin')
def template_edit(tid):
    db = get_session()
    try:
        t = db.query(CommunicationTemplate).filter_by(id=tid).first()
        if not t:
            flash('Template not found.', 'error')
            return redirect(url_for('comm_templates.template_list'))

        if request.method == 'POST':
            _save_template(db, t)
            flash(f'Template "{t.name}" updated.', 'success')
            return redirect(url_for('comm_templates.template_list'))

        return render_template('communications/template_form.html',
            active_page='settings', user=current_user, divisions=_get_divisions(),
            template=t, comm_types=COMM_TYPES, comm_priorities=COMM_PRIORITIES,
        )
    finally:
        db.close()


@comm_templates_bp.route('/<int:tid>/delete', methods=['POST'])
@login_required
@role_required('owner', 'admin')
def template_delete(tid):
    db = get_session()
    try:
        t = db.query(CommunicationTemplate).filter_by(id=tid).first()
        if t:
            db.delete(t)
            db.commit()
            flash('Template deleted.', 'warning')
    finally:
        db.close()
    return redirect(url_for('comm_templates.template_list'))


@comm_templates_bp.route('/<int:tid>/toggle', methods=['POST'])
@login_required
@role_required('owner', 'admin')
def template_toggle(tid):
    db = get_session()
    try:
        t = db.query(CommunicationTemplate).filter_by(id=tid).first()
        if t:
            t.is_active = not t.is_active
            db.commit()
            return jsonify({'success': True, 'is_active': t.is_active})
        return jsonify({'success': False}), 404
    finally:
        db.close()


def _save_template(db, template):
    is_new = template is None
    if is_new:
        template = CommunicationTemplate(created_by_id=current_user.id)
        db.add(template)

    f = request.form
    template.name = f.get('name', '').strip()
    template.communication_type = f.get('communication_type', 'other')
    template.subject_template = f.get('subject_template', '').strip()
    template.description_template = f.get('description_template', '').strip() or None
    template.follow_up_required = 'follow_up_required' in f
    fu_days = f.get('follow_up_days')
    template.follow_up_days = int(fu_days) if fu_days and fu_days.isdigit() else None
    template.default_priority = f.get('default_priority', 'normal')
    template.is_active = 'is_active' in f or not f.get('_active_submitted')
    db.commit()
    return template
