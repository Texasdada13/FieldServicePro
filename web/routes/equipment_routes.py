"""Routes for equipment/asset management."""
from flask import Blueprint, render_template, request, abort, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy import desc, or_
from models.database import get_session
from models.equipment import Equipment
from models.division import Division

equipment_bp = Blueprint('equipment', __name__)


def _get_divisions():
    db = get_session()
    try:
        return db.query(Division).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Division.sort_order).all()
    finally:
        db.close()


@equipment_bp.route('/equipment')
@login_required
def equipment_list():
    db = get_session()
    try:
        org_id = current_user.organization_id
        query = db.query(Equipment).filter_by(organization_id=org_id, is_active=True)

        # Filters
        eq_type = request.args.get('type', '')
        status = request.args.get('status', '')
        search = request.args.get('search', '').strip()

        if eq_type:
            query = query.filter(Equipment.equipment_type == eq_type)
        if status:
            query = query.filter(Equipment.status == status)
        if search:
            s = f'%{search}%'
            query = query.filter(or_(
                Equipment.name.ilike(s),
                Equipment.make.ilike(s),
                Equipment.model.ilike(s),
                Equipment.serial_number.ilike(s),
                Equipment.identifier.ilike(s),
            ))

        items = query.order_by(Equipment.name).all()

        # Stats
        all_eq = db.query(Equipment).filter_by(organization_id=org_id, is_active=True)
        total = all_eq.count()
        available = all_eq.filter_by(status='available').count()
        assigned = all_eq.filter_by(status='assigned').count()
        in_maint = all_eq.filter_by(status='in_maintenance').count()
        out_svc = all_eq.filter_by(status='out_of_service').count()

        return render_template('equipment/equipment_list.html',
            active_page='equipment', user=current_user, divisions=_get_divisions(),
            items=items, total=total, available=available, assigned=assigned,
            in_maintenance=in_maint, out_of_service=out_svc,
            filter_type=eq_type, filter_status=status, search=search,
            type_choices=Equipment.TYPE_CHOICES,
            status_choices=Equipment.STATUS_CHOICES,
        )
    finally:
        db.close()


@equipment_bp.route('/equipment/new', methods=['POST'])
@login_required
def add_equipment():
    db = get_session()
    try:
        eq = Equipment(
            organization_id=current_user.organization_id,
            name=request.form.get('name', '').strip() or 'New Equipment',
            equipment_type=request.form.get('equipment_type', 'tool'),
            make=request.form.get('make', '').strip() or None,
            model=request.form.get('model', '').strip() or None,
            serial_number=request.form.get('serial_number', '').strip() or None,
            status='available',
        )
        db.add(eq)
        db.commit()
        flash(f'Equipment "{eq.name}" created.', 'success')
        return redirect(url_for('equipment.equipment_detail', equip_id=eq.id))
    finally:
        db.close()


@equipment_bp.route('/equipment/<int:equip_id>')
@login_required
def equipment_detail(equip_id):
    db = get_session()
    try:
        item = db.query(Equipment).filter_by(
            id=equip_id, organization_id=current_user.organization_id
        ).first()
        if not item:
            abort(404)

        return render_template('equipment/equipment_detail.html',
            active_page='equipment', user=current_user, divisions=_get_divisions(),
            item=item,
        )
    finally:
        db.close()
