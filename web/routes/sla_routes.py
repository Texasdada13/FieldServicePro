"""SLA management routes (Settings section)."""

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, abort)
from flask_login import login_required, current_user
from models.database import get_session
from models.sla import SLA, PriorityLevel
from web.auth import role_required

sla_bp = Blueprint('sla', __name__, url_prefix='/settings/slas')


def _get_divisions():
    """Fetch active divisions for the current user's org (for base template)."""
    from models import Division
    db = get_session()
    try:
        return db.query(Division).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Division.sort_order).all()
    finally:
        db.close()


def _tpl_vars(**extra):
    """Common template variables for all SLA routes."""
    base = dict(
        active_page='settings',
        user=current_user,
        divisions=_get_divisions(),
    )
    base.update(extra)
    return base


@sla_bp.route('/', methods=['GET'])
@login_required
@role_required('owner', 'admin')
def sla_list():
    db = get_session()
    try:
        slas = db.query(SLA).order_by(SLA.priority_level, SLA.sla_name).all()
        return render_template('settings/sla_list.html',
                               **_tpl_vars(slas=slas, PriorityLevel=PriorityLevel))
    finally:
        db.close()


@sla_bp.route('/new', methods=['GET', 'POST'])
@login_required
@role_required('owner', 'admin')
def sla_new():
    if request.method == 'POST':
        db = get_session()
        try:
            sla = SLA(
                sla_name             = request.form['sla_name'].strip(),
                priority_level       = PriorityLevel(request.form['priority_level']),
                response_time_hours  = float(request.form['response_time_hours']),
                resolution_time_hours= float(request.form['resolution_time_hours'])
                                        if request.form.get('resolution_time_hours') else None,
                business_hours_only  = 'business_hours_only' in request.form,
                business_hours_start = request.form.get('business_hours_start', '08:00'),
                business_hours_end   = request.form.get('business_hours_end', '17:00'),
                business_days        = ','.join(request.form.getlist('business_days'))
                                        or 'mon,tue,wed,thu,fri',
                penalties            = request.form.get('penalties', '').strip() or None,
                is_active            = 'is_active' in request.form,
            )
            db.add(sla)
            db.commit()
            flash(f'SLA "{sla.sla_name}" created successfully.', 'success')
            return redirect(url_for('sla.sla_list'))
        except Exception as e:
            db.rollback()
            flash(f'Error creating SLA: {str(e)}', 'danger')
        finally:
            db.close()

    return render_template('settings/sla_form.html',
                           **_tpl_vars(sla=None, PriorityLevel=PriorityLevel,
                                       action='new'))


@sla_bp.route('/<int:sla_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('owner', 'admin')
def sla_edit(sla_id):
    db = get_session()
    try:
        sla = db.query(SLA).filter_by(id=sla_id).first()
        if not sla:
            abort(404)

        if request.method == 'POST':
            try:
                sla.sla_name              = request.form['sla_name'].strip()
                sla.priority_level        = PriorityLevel(request.form['priority_level'])
                sla.response_time_hours   = float(request.form['response_time_hours'])
                sla.resolution_time_hours = (float(request.form['resolution_time_hours'])
                                             if request.form.get('resolution_time_hours') else None)
                sla.business_hours_only   = 'business_hours_only' in request.form
                sla.business_hours_start  = request.form.get('business_hours_start', '08:00')
                sla.business_hours_end    = request.form.get('business_hours_end', '17:00')
                sla.business_days         = ','.join(request.form.getlist('business_days')) \
                                             or 'mon,tue,wed,thu,fri'
                sla.penalties             = request.form.get('penalties', '').strip() or None
                sla.is_active             = 'is_active' in request.form
                db.commit()
                flash(f'SLA "{sla.sla_name}" updated.', 'success')
                return redirect(url_for('sla.sla_list'))
            except Exception as e:
                db.rollback()
                flash(f'Error updating SLA: {str(e)}', 'danger')

        return render_template('settings/sla_form.html',
                               **_tpl_vars(sla=sla, PriorityLevel=PriorityLevel,
                                           action='edit'))
    finally:
        db.close()


@sla_bp.route('/<int:sla_id>/delete', methods=['POST'])
@login_required
@role_required('owner', 'admin')
def sla_delete(sla_id):
    db = get_session()
    try:
        sla = db.query(SLA).filter_by(id=sla_id).first()
        if not sla:
            abort(404)
        if sla.contracts:
            flash('Cannot delete SLA -- it is assigned to active contracts.', 'warning')
            return redirect(url_for('sla.sla_list'))
        db.delete(sla)
        db.commit()
        flash('SLA deleted.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {str(e)}', 'danger')
    finally:
        db.close()
    return redirect(url_for('sla.sla_list'))


@sla_bp.route('/<int:sla_id>/toggle', methods=['POST'])
@login_required
@role_required('owner', 'admin')
def sla_toggle(sla_id):
    db = get_session()
    try:
        sla = db.query(SLA).filter_by(id=sla_id).first()
        if not sla:
            abort(404)
        sla.is_active = not sla.is_active
        db.commit()
        state = 'activated' if sla.is_active else 'deactivated'
        flash(f'SLA "{sla.sla_name}" {state}.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {str(e)}', 'danger')
    finally:
        db.close()
    return redirect(url_for('sla.sla_list'))
