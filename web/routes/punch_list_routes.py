"""Punch List routes — list, create, detail with items, status transitions."""
from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func

from models.database import get_session
from models.punch_list import (
    PunchList, PunchListItem, PUNCH_LIST_STATUSES,
    ITEM_CATEGORIES, ITEM_SEVERITIES, ITEM_TRADES, ITEM_STATUSES,
    SEVERITY_COLORS, ITEM_STATUS_COLORS,
)
from models.project import Project
from models.technician import Technician
from models.user import User
from models.division import Division
from web.auth import role_required

punch_list_bp = Blueprint('punch_lists', __name__)


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

@punch_list_bp.route('/punch-lists')
@login_required
def punch_list_index():
    db = get_session()
    try:
        org_id = current_user.organization_id
        project_id = request.args.get('project_id', type=int)

        q = db.query(PunchList).join(Project).filter(Project.organization_id == org_id)
        if project_id:
            q = q.filter(PunchList.project_id == project_id)

        punch_lists = q.order_by(PunchList.created_at.desc()).all()
        projects = db.query(Project).filter_by(organization_id=org_id).order_by(Project.title).all()

        return render_template('punch_lists/punch_list_index.html',
            active_page='punch_lists', user=current_user, divisions=_get_divisions(),
            punch_lists=punch_lists, projects=projects, today=date.today(),
            filters={'project_id': project_id},
        )
    finally:
        db.close()


# ── Create ────────────────────────────────────────────────────────────────────

@punch_list_bp.route('/punch-lists/new', methods=['GET', 'POST'])
@punch_list_bp.route('/punch-lists/new/<int:project_id>', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'owner', 'dispatcher')
def punch_list_new(project_id=None):
    db = get_session()
    try:
        org_id = current_user.organization_id
        projects = db.query(Project).filter_by(organization_id=org_id).order_by(Project.title).all()
        project = db.query(Project).filter_by(id=project_id).first() if project_id else None

        if request.method == 'POST':
            pid = int(request.form['project_id'])
            pl = PunchList(
                punch_list_number=PunchList.next_number(db),
                project_id=pid,
                title=request.form['title'].strip(),
                description=request.form.get('description', '').strip() or None,
                inspection_date=_parse_date(request.form.get('inspection_date')) or date.today(),
                inspected_by=request.form.get('inspected_by', '').strip() or None,
                status=request.form.get('status', 'active'),
                due_date=_parse_date(request.form.get('due_date')),
                notes=request.form.get('notes', '').strip() or None,
                created_by_id=current_user.id,
            )
            db.add(pl)
            db.commit()
            flash(f'Punch list {pl.punch_list_number} created.', 'success')
            return redirect(url_for('punch_lists.punch_list_detail', pl_id=pl.id))

        return render_template('punch_lists/punch_list_form.html',
            active_page='punch_lists', user=current_user, divisions=_get_divisions(),
            pl=None, projects=projects, project=project,
        )
    finally:
        db.close()


# ── Edit ──────────────────────────────────────────────────────────────────────

@punch_list_bp.route('/punch-lists/<int:pl_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'owner', 'dispatcher')
def punch_list_edit(pl_id):
    db = get_session()
    try:
        pl = db.query(PunchList).filter_by(id=pl_id).first()
        if not pl:
            flash('Punch list not found.', 'error')
            return redirect(url_for('punch_lists.punch_list_index'))

        org_id = current_user.organization_id
        projects = db.query(Project).filter_by(organization_id=org_id).order_by(Project.title).all()

        if request.method == 'POST':
            pl.title = request.form['title'].strip()
            pl.description = request.form.get('description', '').strip() or None
            pl.inspection_date = _parse_date(request.form.get('inspection_date')) or pl.inspection_date
            pl.inspected_by = request.form.get('inspected_by', '').strip() or None
            pl.due_date = _parse_date(request.form.get('due_date'))
            pl.notes = request.form.get('notes', '').strip() or None
            db.commit()
            flash('Punch list updated.', 'success')
            return redirect(url_for('punch_lists.punch_list_detail', pl_id=pl_id))

        return render_template('punch_lists/punch_list_form.html',
            active_page='punch_lists', user=current_user, divisions=_get_divisions(),
            pl=pl, projects=projects,
        )
    finally:
        db.close()


# ── Detail ────────────────────────────────────────────────────────────────────

@punch_list_bp.route('/punch-lists/<int:pl_id>')
@login_required
def punch_list_detail(pl_id):
    db = get_session()
    try:
        pl = db.query(PunchList).filter_by(id=pl_id).first()
        if not pl:
            flash('Punch list not found.', 'error')
            return redirect(url_for('punch_lists.punch_list_index'))

        status_filter = request.args.get('status', '')
        trade_filter = request.args.get('trade', '')
        severity_filter = request.args.get('severity', '')

        q = db.query(PunchListItem).filter_by(punch_list_id=pl_id)
        if status_filter:
            q = q.filter(PunchListItem.status == status_filter)
        if trade_filter:
            q = q.filter(PunchListItem.trade == trade_filter)
        if severity_filter:
            q = q.filter(PunchListItem.severity == severity_filter)

        items = q.order_by(PunchListItem.sort_order, PunchListItem.item_number).all()
        all_items = pl.items or []

        # Stats
        status_counts = {}
        trade_counts = {}
        for item in all_items:
            status_counts[item.status] = status_counts.get(item.status, 0) + 1
            trade_counts[item.trade] = trade_counts.get(item.trade, 0) + 1

        technicians = db.query(Technician).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Technician.first_name).all()

        return render_template('punch_lists/punch_list_detail.html',
            active_page='punch_lists', user=current_user, divisions=_get_divisions(),
            pl=pl, items=items, all_items=all_items,
            status_counts=status_counts, trade_counts=trade_counts,
            technicians=technicians, today=date.today(),
            item_categories=ITEM_CATEGORIES, item_severities=ITEM_SEVERITIES,
            item_trades=ITEM_TRADES, item_statuses=ITEM_STATUSES,
            severity_colors=SEVERITY_COLORS, item_status_colors=ITEM_STATUS_COLORS,
            filters={'status': status_filter, 'trade': trade_filter, 'severity': severity_filter},
        )
    finally:
        db.close()


# ── Add Item ──────────────────────────────────────────────────────────────────

@punch_list_bp.route('/punch-lists/<int:pl_id>/items/add', methods=['POST'])
@login_required
def punch_item_add(pl_id):
    db = get_session()
    try:
        pl = db.query(PunchList).filter_by(id=pl_id).first()
        if not pl:
            flash('Punch list not found.', 'error')
            return redirect(url_for('punch_lists.punch_list_index'))

        max_num = db.query(func.max(PunchListItem.item_number)).filter_by(punch_list_id=pl_id).scalar() or 0
        max_sort = db.query(func.max(PunchListItem.sort_order)).filter_by(punch_list_id=pl_id).scalar() or 0

        item = PunchListItem(
            punch_list_id=pl_id,
            item_number=max_num + 1,
            sort_order=max_sort + 1,
            location=request.form.get('location', '').strip() or None,
            description=request.form['description'].strip(),
            category=request.form.get('category', 'other'),
            severity=request.form.get('severity', 'minor'),
            trade=request.form.get('trade', 'general'),
            status='open',
            assigned_to_id=int(request.form['assigned_to_id']) if request.form.get('assigned_to_id') else None,
            notes=request.form.get('notes', '').strip() or None,
        )
        db.add(item)

        if pl.status == 'draft':
            pl.status = 'active'

        db.commit()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'item_id': item.id, 'item_number': item.item_number})

        flash(f'Item #{item.item_number} added.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {e}', 'error')
    finally:
        db.close()
    return redirect(url_for('punch_lists.punch_list_detail', pl_id=pl_id))


# ── Item Status Update ────────────────────────────────────────────────────────

@punch_list_bp.route('/punch-lists/<int:pl_id>/items/<int:item_id>/status', methods=['POST'])
@login_required
def punch_item_status(pl_id, item_id):
    db = get_session()
    try:
        item = db.query(PunchListItem).filter_by(id=item_id, punch_list_id=pl_id).first()
        if not item:
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': 'Item not found'}), 404
            flash('Item not found.', 'error')
            return redirect(url_for('punch_lists.punch_list_detail', pl_id=pl_id))

        new_status = request.form.get('status') or (request.json.get('status') if request.is_json else None)

        allowed = {
            'open': ['assigned', 'in_progress', 'deferred'],
            'assigned': ['in_progress', 'open', 'deferred'],
            'in_progress': ['completed', 'open'],
            'completed': ['verified', 'rejected'],
            'rejected': ['assigned', 'in_progress'],
            'deferred': ['open'],
            'verified': [],
        }

        if new_status not in allowed.get(item.status, []):
            msg = f'Cannot transition from {item.status} to {new_status}.'
            if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return jsonify({'success': False, 'error': msg}), 400
            flash(msg, 'warning')
            return redirect(url_for('punch_lists.punch_list_detail', pl_id=pl_id))

        item.status = new_status
        if new_status == 'completed':
            item.completed_date = date.today()
        elif new_status == 'verified':
            item.verified_by_id = current_user.id
            item.verified_date = date.today()
        elif new_status == 'rejected':
            item.rejection_reason = request.form.get('rejection_reason', '')

        db.commit()

        pl = db.query(PunchList).filter_by(id=pl_id).first()
        if request.is_json or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': True, 'status': new_status,
                            'percent_complete': pl.percent_complete if pl else 0})

        flash(f'Item #{item.item_number} updated to {new_status.replace("_"," ")}.', 'success')
    finally:
        db.close()
    return redirect(url_for('punch_lists.punch_list_detail', pl_id=pl_id))


# ── Bulk Assign ───────────────────────────────────────────────────────────────

@punch_list_bp.route('/punch-lists/<int:pl_id>/items/bulk-assign', methods=['POST'])
@login_required
@role_required('admin', 'owner', 'dispatcher')
def punch_items_bulk_assign(pl_id):
    db = get_session()
    try:
        tech_id = int(request.form['technician_id']) if request.form.get('technician_id') else None
        item_ids = request.form.getlist('item_ids', type=int)

        if not tech_id or not item_ids:
            flash('Select items and a technician.', 'warning')
            return redirect(url_for('punch_lists.punch_list_detail', pl_id=pl_id))

        count = 0
        for item_id in item_ids:
            item = db.query(PunchListItem).filter_by(id=item_id, punch_list_id=pl_id).first()
            if item and item.status in ('open', 'assigned', 'rejected'):
                item.assigned_to_id = tech_id
                item.status = 'assigned'
                count += 1

        db.commit()
        tech = db.query(Technician).filter_by(id=tech_id).first()
        flash(f'{count} items assigned to {tech.full_name if tech else "technician"}.', 'success')
    finally:
        db.close()
    return redirect(url_for('punch_lists.punch_list_detail', pl_id=pl_id))


# ── Complete / Accept ─────────────────────────────────────────────────────────

@punch_list_bp.route('/punch-lists/<int:pl_id>/complete', methods=['POST'])
@login_required
@role_required('admin', 'owner', 'dispatcher')
def punch_list_complete(pl_id):
    db = get_session()
    try:
        pl = db.query(PunchList).filter_by(id=pl_id).first()
        if pl and pl.has_critical_open:
            flash('Cannot complete: critical items still open.', 'error')
        elif pl:
            pl.status = 'completed'
            db.commit()
            flash('Punch list marked complete.', 'success')
    finally:
        db.close()
    return redirect(url_for('punch_lists.punch_list_detail', pl_id=pl_id))


@punch_list_bp.route('/punch-lists/<int:pl_id>/accept', methods=['POST'])
@login_required
@role_required('admin', 'owner')
def punch_list_accept(pl_id):
    db = get_session()
    try:
        pl = db.query(PunchList).filter_by(id=pl_id).first()
        if pl:
            pl.status = 'accepted'
            pl.accepted_by = request.form.get('accepted_by', '').strip() or None
            pl.accepted_date = date.today()
            db.commit()
            flash('Punch list accepted.', 'success')
    finally:
        db.close()
    return redirect(url_for('punch_lists.punch_list_detail', pl_id=pl_id))


# ── Print View ────────────────────────────────────────────────────────────────

@punch_list_bp.route('/punch-lists/<int:pl_id>/print')
@login_required
def punch_list_print(pl_id):
    db = get_session()
    try:
        pl = db.query(PunchList).filter_by(id=pl_id).first()
        if not pl:
            flash('Punch list not found.', 'error')
            return redirect(url_for('punch_lists.punch_list_index'))
        items = db.query(PunchListItem).filter_by(punch_list_id=pl_id).order_by(
            PunchListItem.sort_order, PunchListItem.item_number).all()
        return render_template('punch_lists/punch_list_print.html',
            pl=pl, items=items, today=date.today(),
        )
    finally:
        db.close()


# ── Edit Item ─────────────────────────────────────────────────────────────────

@punch_list_bp.route('/punch-lists/<int:pl_id>/items/<int:item_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'owner', 'dispatcher')
def punch_item_edit(pl_id, item_id):
    db = get_session()
    try:
        pl = db.query(PunchList).filter_by(id=pl_id).first()
        item = db.query(PunchListItem).filter_by(id=item_id, punch_list_id=pl_id).first()
        if not pl or not item:
            flash('Not found.', 'error')
            return redirect(url_for('punch_lists.punch_list_index'))

        technicians = db.query(Technician).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Technician.first_name).all()

        if request.method == 'POST':
            item.location = request.form.get('location', '').strip() or None
            item.description = request.form['description'].strip()
            item.category = request.form.get('category', 'other')
            item.severity = request.form.get('severity', 'minor')
            item.trade = request.form.get('trade', 'general')
            old_assignee = item.assigned_to_id
            item.assigned_to_id = int(request.form['assigned_to_id']) if request.form.get('assigned_to_id') else None
            item.notes = request.form.get('notes', '').strip() or None
            if item.assigned_to_id and item.assigned_to_id != old_assignee:
                item.status = 'assigned'
            db.commit()
            flash(f'Item #{item.item_number} updated.', 'success')
            return redirect(url_for('punch_lists.punch_list_detail', pl_id=pl_id))

        return render_template('punch_lists/punch_item_edit.html',
            active_page='punch_lists', user=current_user, divisions=_get_divisions(),
            pl=pl, item=item, technicians=technicians,
        )
    finally:
        db.close()
