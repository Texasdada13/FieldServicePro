"""Supplier Purchase Order routes — CRUD + receiving."""
from datetime import date, datetime, timedelta
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from models.database import get_session
from models.vendor import Vendor
from models.supplier_po import SupplierPurchaseOrder, SupplierPOLineItem, SPO_STATUSES
from models.vendor_payment import VendorPayment
from models.part import Part
from models.division import Division
from web.auth import role_required

supplier_po_bp = Blueprint('supplier_pos', __name__)


def _get_divisions():
    db = get_session()
    try:
        return db.query(Division).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Division.sort_order).all()
    finally:
        db.close()


# ── List ──────────────────────────────────────────────────────────────────────

@supplier_po_bp.route('/supplier-pos')
@login_required
def spo_list():
    db = get_session()
    try:
        status_filter = request.args.get('status', '')
        vendor_id = request.args.get('vendor_id', type=int)

        q = db.query(SupplierPurchaseOrder)
        if status_filter:
            q = q.filter(SupplierPurchaseOrder.status == status_filter)
        if vendor_id:
            q = q.filter(SupplierPurchaseOrder.vendor_id == vendor_id)

        pos = q.order_by(SupplierPurchaseOrder.order_date.desc()).all()

        # Stats
        total_open = sum(float(po.balance_due) for po in pos if po.status not in ('cancelled', 'received'))
        pending_count = sum(1 for po in pos if po.status in ('submitted', 'acknowledged'))
        receiving_count = sum(1 for po in pos if po.status == 'partially_received')

        vendors = db.query(Vendor).filter_by(is_active=True).order_by(Vendor.company_name).all()

        return render_template('supplier_pos/spo_list.html',
            active_page='supplier_pos', user=current_user, divisions=_get_divisions(),
            pos=pos, total_open=total_open, pending_count=pending_count,
            receiving_count=receiving_count, vendors=vendors,
            spo_statuses=SPO_STATUSES,
            filters={'status': status_filter, 'vendor_id': vendor_id},
        )
    finally:
        db.close()


# ── Detail ────────────────────────────────────────────────────────────────────

@supplier_po_bp.route('/supplier-pos/<int:po_id>')
@login_required
def spo_detail(po_id):
    db = get_session()
    try:
        po = db.query(SupplierPurchaseOrder).filter_by(id=po_id).first()
        if not po:
            flash('PO not found.', 'error')
            return redirect(url_for('supplier_pos.spo_list'))

        payments = db.query(VendorPayment).filter_by(po_id=po_id).order_by(VendorPayment.payment_date.desc()).all()

        return render_template('supplier_pos/spo_detail.html',
            active_page='supplier_pos', user=current_user, divisions=_get_divisions(),
            po=po, payments=payments,
        )
    finally:
        db.close()


# ── Create ────────────────────────────────────────────────────────────────────

@supplier_po_bp.route('/supplier-pos/new', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'owner', 'dispatcher')
def spo_new():
    db = get_session()
    try:
        vendors = db.query(Vendor).filter_by(is_active=True).order_by(Vendor.company_name).all()
        parts = db.query(Part).order_by(Part.name).limit(200).all()
        preselect_vendor = request.args.get('vendor_id', type=int)

        if request.method == 'POST':
            f = request.form
            vendor_id = int(f['vendor_id'])
            vendor = db.query(Vendor).filter_by(id=vendor_id).first()

            po = SupplierPurchaseOrder(
                po_number=SupplierPurchaseOrder.generate_po_number(db),
                vendor_id=vendor_id,
                status='draft',
                order_date=datetime.strptime(f['order_date'], '%Y-%m-%d').date() if f.get('order_date') else date.today(),
                expected_delivery_date=datetime.strptime(f['expected_delivery_date'], '%Y-%m-%d').date() if f.get('expected_delivery_date') else None,
                tax_rate=float(f.get('tax_rate', 13)),
                shipping_cost=float(f.get('shipping_cost', 0) or 0),
                payment_terms=vendor.payment_terms if vendor else 'net_30',
                delivery_address=f.get('delivery_address', '').strip() or None,
                shipping_method=f.get('shipping_method', '').strip() or None,
                job_id=int(f['job_id']) if f.get('job_id') else None,
                project_id=int(f['project_id']) if f.get('project_id') else None,
                notes=f.get('notes', '').strip() or None,
                internal_notes=f.get('internal_notes', '').strip() or None,
                requested_by=current_user.id,
                created_by=current_user.id,
            )
            db.add(po)
            db.flush()

            # Line items
            descriptions = f.getlist('item_description[]')
            quantities = f.getlist('item_quantity[]')
            prices = f.getlist('item_price[]')
            part_ids = f.getlist('item_part_id[]')

            for i, desc in enumerate(descriptions):
                if not desc.strip():
                    continue
                li = SupplierPOLineItem(
                    po_id=po.id,
                    part_id=int(part_ids[i]) if i < len(part_ids) and part_ids[i] else None,
                    description=desc.strip(),
                    quantity_ordered=int(quantities[i]) if i < len(quantities) and quantities[i] else 1,
                    unit_price=float(prices[i]) if i < len(prices) and prices[i] else 0,
                    sort_order=i,
                )
                db.add(li)

            po.recalculate_totals()

            # Compute payment due date
            if vendor:
                po.payment_due_date = po.order_date + timedelta(days=vendor.payment_days)

            # Auto-submit if requested
            if f.get('submit_action') == 'submit':
                po.status = 'submitted'

            db.commit()
            flash(f'Supplier PO {po.po_number} created.', 'success')
            return redirect(url_for('supplier_pos.spo_detail', po_id=po.id))

        return render_template('supplier_pos/spo_form.html',
            active_page='supplier_pos', user=current_user, divisions=_get_divisions(),
            po=None, vendors=vendors, parts=parts,
            preselect_vendor=preselect_vendor, today=date.today(),
        )
    finally:
        db.close()


# ── Receive Items ─────────────────────────────────────────────────────────────

@supplier_po_bp.route('/supplier-pos/<int:po_id>/receive', methods=['POST'])
@login_required
@role_required('admin', 'owner', 'dispatcher')
def spo_receive(po_id):
    db = get_session()
    try:
        po = db.query(SupplierPurchaseOrder).filter_by(id=po_id).first()
        if not po:
            flash('PO not found.', 'error')
            return redirect(url_for('supplier_pos.spo_list'))

        f = request.form
        any_received = False
        for item in po.line_items:
            qty_key = f'receive_{item.id}'
            qty = int(f.get(qty_key, 0) or 0)
            if qty > 0:
                item.quantity_received = min(item.quantity_received + qty, item.quantity_ordered)
                item.received_date = date.today()
                any_received = True

        if any_received:
            # Update PO status based on receipt progress
            total_ordered = sum(i.quantity_ordered for i in po.line_items)
            total_received = sum(i.quantity_received for i in po.line_items)
            if total_received >= total_ordered:
                po.status = 'received'
                po.actual_delivery_date = date.today()
            elif total_received > 0:
                po.status = 'partially_received'

            db.commit()
            flash(f'Items received for {po.po_number}.', 'success')
        else:
            flash('No quantities entered.', 'warning')
    finally:
        db.close()
    return redirect(url_for('supplier_pos.spo_detail', po_id=po_id))


# ── Print / PDF ──────────────────────────────────────────────────────────────

@supplier_po_bp.route('/supplier-pos/<int:po_id>/print')
@login_required
def spo_print(po_id):
    db = get_session()
    try:
        po = db.query(SupplierPurchaseOrder).filter_by(id=po_id).first()
        if not po:
            flash('PO not found.', 'error')
            return redirect(url_for('supplier_pos.spo_list'))

        return render_template('supplier_pos/spo_print.html',
            po=po, now=datetime.now(),
        )
    finally:
        db.close()


# ── Status Changes ────────────────────────────────────────────────────────────

@supplier_po_bp.route('/supplier-pos/<int:po_id>/submit', methods=['POST'])
@login_required
def spo_submit(po_id):
    db = get_session()
    try:
        po = db.query(SupplierPurchaseOrder).filter_by(id=po_id).first()
        if po and po.status == 'draft':
            po.status = 'submitted'
            db.commit()
            flash(f'{po.po_number} submitted.', 'success')
    finally:
        db.close()
    return redirect(url_for('supplier_pos.spo_detail', po_id=po_id))


@supplier_po_bp.route('/supplier-pos/<int:po_id>/cancel', methods=['POST'])
@login_required
@role_required('admin', 'owner')
def spo_cancel(po_id):
    db = get_session()
    try:
        po = db.query(SupplierPurchaseOrder).filter_by(id=po_id).first()
        if po and po.status not in ('received', 'cancelled'):
            po.status = 'cancelled'
            db.commit()
            flash(f'{po.po_number} cancelled.', 'warning')
    finally:
        db.close()
    return redirect(url_for('supplier_pos.spo_detail', po_id=po_id))
