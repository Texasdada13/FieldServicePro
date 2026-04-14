"""Routes for Parts & Materials catalog."""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, Response
from flask_login import login_required, current_user
from sqlalchemy import or_, desc
from models.database import get_session
from models.part import Part, PART_CATEGORIES, PART_TRADES, UNIT_TYPES
from models.inventory import InventoryStock, InventoryLocation, InventoryTransaction
from models.job_material import JobMaterial
from models.division import Division
from web.utils.parts_utils import (
    generate_part_number, get_catalog_stats, export_parts_csv,
    generate_csv_template, import_parts_csv,
)

parts_bp = Blueprint('parts', __name__)


def _get_divisions():
    db = get_session()
    try:
        return db.query(Division).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Division.sort_order).all()
    finally:
        db.close()


def _can_admin():
    return current_user.role in ('owner', 'admin')


# ── Parts Catalog List ──────────────────────────────────────────
@parts_bp.route('/parts')
@login_required
def list_parts():
    db = get_session()
    try:
        org_id = current_user.organization_id
        query = db.query(Part).filter_by(organization_id=org_id)

        # Filters
        search = request.args.get('search', '').strip()
        category = request.args.get('category', '')
        trade = request.args.get('trade', '')
        low_stock_only = request.args.get('low_stock') == '1'
        show_inactive = request.args.get('inactive') == '1'

        if not show_inactive:
            query = query.filter(Part.is_active == True)

        if category:
            query = query.filter(Part.category == category)
        if trade:
            query = query.filter(Part.trade == trade)
        if search:
            s = f'%{search}%'
            query = query.filter(or_(
                Part.name.ilike(s),
                Part.part_number.ilike(s),
                Part.manufacturer.ilike(s),
                Part.barcode.ilike(s),
                Part.description.ilike(s),
            ))

        parts = query.order_by(Part.name).all()

        # Post-query filter for low stock
        if low_stock_only:
            parts = [p for p in parts if p.is_low_stock]

        stats = get_catalog_stats(db, org_id)

        return render_template('parts/parts_list.html',
            active_page='parts', user=current_user, divisions=_get_divisions(),
            parts=parts, stats=stats, can_admin=_can_admin(),
            categories=PART_CATEGORIES, trades=PART_TRADES,
            search=search, selected_category=category,
            selected_trade=trade, low_stock_only=low_stock_only,
            show_inactive=show_inactive,
        )
    finally:
        db.close()


# ── Part Detail ─────────────────────────────────────────────────
@parts_bp.route('/parts/<int:part_id>')
@login_required
def part_detail(part_id):
    db = get_session()
    try:
        part = db.query(Part).filter_by(id=part_id, organization_id=current_user.organization_id).first()
        if not part:
            flash('Part not found.', 'error')
            return redirect(url_for('parts.list_parts'))

        stocks = db.query(InventoryStock).filter_by(part_id=part.id).all()

        transactions = db.query(InventoryTransaction).filter_by(
            part_id=part.id
        ).order_by(desc(InventoryTransaction.created_at)).limit(20).all()

        job_materials = db.query(JobMaterial).filter_by(
            part_id=part.id
        ).order_by(desc(JobMaterial.created_at)).limit(20).all()

        return render_template('parts/part_detail.html',
            active_page='parts', user=current_user, divisions=_get_divisions(),
            part=part, stocks=stocks, transactions=transactions,
            job_materials=job_materials, can_admin=_can_admin(),
        )
    finally:
        db.close()


# ── Create Part ─────────────────────────────────────────────────
@parts_bp.route('/parts/new', methods=['GET', 'POST'])
@login_required
def new_part():
    db = get_session()
    try:
        org_id = current_user.organization_id

        if request.method == 'POST':
            trade = request.form.get('trade', 'general')
            part_number = request.form.get('part_number', '').strip()
            if not part_number:
                part_number = generate_part_number(db, org_id, trade)

            if db.query(Part).filter_by(part_number=part_number).first():
                flash('Part number already exists.', 'error')
                return redirect(url_for('parts.new_part'))

            part = Part(
                organization_id=org_id,
                part_number=part_number,
                name=request.form.get('name', '').strip(),
                description=request.form.get('description', '').strip() or None,
                trade=trade,
                category=request.form.get('category', 'other'),
                subcategory=request.form.get('subcategory', '').strip() or None,
                manufacturer=request.form.get('manufacturer', '').strip() or None,
                manufacturer_part_number=request.form.get('manufacturer_part_number', '').strip() or None,
                preferred_vendor_name=request.form.get('preferred_vendor_name', '').strip() or None,
                supplier_part_number=request.form.get('supplier_part_number', '').strip() or None,
                unit_of_measure=request.form.get('unit_of_measure', 'each'),
                cost_price=float(request.form.get('cost_price') or 0),
                sell_price=float(request.form.get('sell_price') or 0),
                markup_percentage=float(request.form.get('markup_percentage') or 0),
                minimum_stock_level=int(request.form.get('minimum_stock_level') or 0),
                reorder_quantity=int(request.form.get('reorder_quantity') or 0),
                max_stock_level=int(request.form.get('max_stock_level') or 0) or None,
                barcode=request.form.get('barcode', '').strip() or None,
                is_serialized='is_serialized' in request.form,
                taxable='taxable' in request.form or not request.form.get('_taxable_submitted'),
                is_active='is_active' in request.form or not request.form.get('_active_submitted'),
                notes=request.form.get('notes', '').strip() or None,
                created_by=current_user.id,
            )
            db.add(part)
            db.commit()
            flash(f'Part {part.part_number} created.', 'success')
            return redirect(url_for('parts.part_detail', part_id=part.id))

        return render_template('parts/part_form.html',
            active_page='parts', user=current_user, divisions=_get_divisions(),
            part=None, title='Add New Part',
            categories=PART_CATEGORIES, trades=PART_TRADES, units=UNIT_TYPES,
        )
    finally:
        db.close()


# ── Edit Part ───────────────────────────────────────────────────
@parts_bp.route('/parts/<int:part_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_part(part_id):
    db = get_session()
    try:
        part = db.query(Part).filter_by(id=part_id, organization_id=current_user.organization_id).first()
        if not part:
            flash('Part not found.', 'error')
            return redirect(url_for('parts.list_parts'))

        if request.method == 'POST':
            part.name = request.form.get('name', '').strip()
            part.description = request.form.get('description', '').strip() or None
            part.trade = request.form.get('trade', part.trade)
            part.category = request.form.get('category', part.category)
            part.subcategory = request.form.get('subcategory', '').strip() or None
            part.manufacturer = request.form.get('manufacturer', '').strip() or None
            part.manufacturer_part_number = request.form.get('manufacturer_part_number', '').strip() or None
            part.preferred_vendor_name = request.form.get('preferred_vendor_name', '').strip() or None
            part.supplier_part_number = request.form.get('supplier_part_number', '').strip() or None
            part.unit_of_measure = request.form.get('unit_of_measure', part.unit_of_measure)
            part.cost_price = float(request.form.get('cost_price') or 0)
            part.sell_price = float(request.form.get('sell_price') or 0)
            part.markup_percentage = float(request.form.get('markup_percentage') or 0)
            part.minimum_stock_level = int(request.form.get('minimum_stock_level') or 0)
            part.reorder_quantity = int(request.form.get('reorder_quantity') or 0)
            part.max_stock_level = int(request.form.get('max_stock_level') or 0) or None
            part.barcode = request.form.get('barcode', '').strip() or None
            part.is_serialized = 'is_serialized' in request.form
            part.taxable = 'taxable' in request.form
            part.is_active = 'is_active' in request.form
            part.notes = request.form.get('notes', '').strip() or None
            db.commit()
            flash(f'Part {part.part_number} updated.', 'success')
            return redirect(url_for('parts.part_detail', part_id=part.id))

        return render_template('parts/part_form.html',
            active_page='parts', user=current_user, divisions=_get_divisions(),
            part=part, title=f'Edit {part.part_number}',
            categories=PART_CATEGORIES, trades=PART_TRADES, units=UNIT_TYPES,
        )
    finally:
        db.close()


# ── Toggle Active (API) ────────────────────────────────────────
@parts_bp.route('/parts/<int:part_id>/toggle-active', methods=['POST'])
@login_required
def toggle_active(part_id):
    db = get_session()
    try:
        part = db.query(Part).filter_by(id=part_id, organization_id=current_user.organization_id).first()
        if not part:
            return jsonify({'success': False, 'error': 'Not found'}), 404
        part.is_active = not part.is_active
        db.commit()
        return jsonify({'success': True, 'is_active': part.is_active})
    finally:
        db.close()


# ── CSV Export ──────────────────────────────────────────────────
@parts_bp.route('/parts/export')
@login_required
def export_parts():
    db = get_session()
    try:
        csv_data = export_parts_csv(db, current_user.organization_id)
        return Response(
            csv_data,
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment;filename=parts_catalog.csv'}
        )
    finally:
        db.close()


# ── CSV Template Download ──────────────────────────────────────
@parts_bp.route('/parts/csv-template')
@login_required
def csv_template():
    csv_data = generate_csv_template()
    return Response(
        csv_data,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment;filename=parts_import_template.csv'}
    )


# ── CSV Import ──────────────────────────────────────────────────
@parts_bp.route('/parts/import', methods=['GET', 'POST'])
@login_required
def import_parts():
    db = get_session()
    try:
        if request.method == 'POST':
            file = request.files.get('csv_file')
            if not file or not file.filename.endswith('.csv'):
                flash('Please upload a CSV file.', 'error')
                return redirect(url_for('parts.import_parts'))

            created, updated, errors = import_parts_csv(
                db, current_user.organization_id, file.stream, current_user.id
            )

            if errors:
                for err in errors[:5]:
                    flash(err, 'warning')
            flash(f'Import complete: {created} created, {updated} updated.', 'success')
            return redirect(url_for('parts.list_parts'))

        return render_template('parts/parts_import.html',
            active_page='parts', user=current_user, divisions=_get_divisions(),
        )
    finally:
        db.close()


# ── API: Search Parts ───────────────────────────────────────────
@parts_bp.route('/api/parts/search')
@login_required
def api_parts_search():
    db = get_session()
    try:
        q = request.args.get('q', '').strip()
        if len(q) < 2:
            return jsonify([])

        s = f'%{q}%'
        parts = db.query(Part).filter(
            Part.organization_id == current_user.organization_id,
            Part.is_active == True,
            or_(
                Part.name.ilike(s),
                Part.part_number.ilike(s),
                Part.barcode.ilike(s),
                Part.manufacturer_part_number.ilike(s),
            )
        ).limit(20).all()

        return jsonify([p.to_dict() for p in parts])
    finally:
        db.close()


# ── API: Part Detail ────────────────────────────────────────────
@parts_bp.route('/api/parts/<int:part_id>')
@login_required
def api_part_detail(part_id):
    db = get_session()
    try:
        part = db.query(Part).filter_by(id=part_id, organization_id=current_user.organization_id).first()
        if not part:
            return jsonify({'error': 'Not found'}), 404
        data = part.to_dict()
        data['stocks'] = [s.to_dict() for s in part.inventory_stocks]
        return jsonify(data)
    finally:
        db.close()
