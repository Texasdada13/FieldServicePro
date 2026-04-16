"""Vendor CRUD routes."""
from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from models.database import get_session
from models.vendor import Vendor, VENDOR_TYPES, VENDOR_STATUSES, PAYMENT_TERMS
from models.vendor_price import VendorPrice
from models.supplier_po import SupplierPurchaseOrder
from models.vendor_payment import VendorPayment
from models.division import Division
from web.auth import role_required

vendor_bp = Blueprint('vendors', __name__)

TRADE_CATEGORIES = ['plumbing', 'hvac', 'electrical', 'general', 'roofing', 'mechanical', 'fire_protection']


def _get_divisions():
    db = get_session()
    try:
        return db.query(Division).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Division.sort_order).all()
    finally:
        db.close()


# ── List ──────────────────────────────────────────────────────────────────────

@vendor_bp.route('/vendors')
@login_required
def vendor_list():
    db = get_session()
    try:
        from web.utils.vendor_utils import get_vendor_stats
        stats = get_vendor_stats(db)

        search = request.args.get('search', '').strip()
        status_filter = request.args.get('status', '')
        type_filter = request.args.get('vendor_type', '')

        q = db.query(Vendor)
        if search:
            q = q.filter(Vendor.company_name.ilike(f'%{search}%') | Vendor.vendor_number.ilike(f'%{search}%'))
        if status_filter:
            q = q.filter(Vendor.status == status_filter)
        if type_filter:
            q = q.filter(Vendor.vendor_type == type_filter)

        vendors = q.order_by(Vendor.company_name).all()

        return render_template('vendors/vendor_list.html',
            active_page='vendors', user=current_user, divisions=_get_divisions(),
            vendors=vendors, stats=stats,
            vendor_types=VENDOR_TYPES, vendor_statuses=VENDOR_STATUSES,
            filters={'search': search, 'status': status_filter, 'vendor_type': type_filter},
        )
    finally:
        db.close()


# ── Detail ────────────────────────────────────────────────────────────────────

@vendor_bp.route('/vendors/<int:vendor_id>')
@login_required
def vendor_detail(vendor_id):
    db = get_session()
    try:
        vendor = db.query(Vendor).filter_by(id=vendor_id).first()
        if not vendor:
            flash('Vendor not found.', 'error')
            return redirect(url_for('vendors.vendor_list'))

        tab = request.args.get('tab', 'overview')
        prices = db.query(VendorPrice).filter_by(vendor_id=vendor_id).all() if tab == 'pricing' else []
        pos = db.query(SupplierPurchaseOrder).filter_by(vendor_id=vendor_id).order_by(
            SupplierPurchaseOrder.order_date.desc()).all() if tab in ('pos', 'overview') else []
        payments = db.query(VendorPayment).filter_by(vendor_id=vendor_id).order_by(
            VendorPayment.payment_date.desc()).all() if tab == 'payments' else []

        from sqlalchemy import func
        from models.part import Part
        total_spent = float(db.query(func.coalesce(func.sum(SupplierPurchaseOrder.total), 0)).filter(
            SupplierPurchaseOrder.vendor_id == vendor_id,
            SupplierPurchaseOrder.status != 'cancelled').scalar() or 0)

        parts_list = db.query(Part).order_by(Part.name).limit(200).all() if tab == 'pricing' else []

        return render_template('vendors/vendor_detail.html',
            active_page='vendors', user=current_user, divisions=_get_divisions(),
            vendor=vendor, tab=tab, prices=prices, pos=pos, payments=payments,
            total_spent=total_spent, parts_list=parts_list, today=date.today(),
            vendor_types=dict(VENDOR_TYPES), payment_terms_map=dict(PAYMENT_TERMS),
        )
    finally:
        db.close()


# ── Create ────────────────────────────────────────────────────────────────────

@vendor_bp.route('/vendors/new', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'owner')
def vendor_new():
    db = get_session()
    try:
        all_divisions = db.query(Division).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Division.sort_order).all()

        if request.method == 'POST':
            f = request.form
            vendor = Vendor(
                vendor_number=Vendor.generate_vendor_number(db),
                company_name=f['company_name'].strip(),
                doing_business_as=f.get('doing_business_as', '').strip() or None,
                vendor_type=f.get('vendor_type', 'parts_supplier'),
                status=f.get('status', 'active'),
                contact_name=f.get('contact_name', '').strip() or None,
                contact_email=f.get('contact_email', '').strip() or None,
                contact_phone=f.get('contact_phone', '').strip() or None,
                phone=f.get('phone', '').strip() or None,
                email=f.get('email', '').strip() or None,
                website=f.get('website', '').strip() or None,
                address_line1=f.get('address_line1', '').strip() or None,
                city=f.get('city', '').strip() or None,
                state_province=f.get('state_province', '').strip() or None,
                postal_code=f.get('postal_code', '').strip() or None,
                country=f.get('country', 'Canada'),
                payment_terms=f.get('payment_terms', 'net_30'),
                tax_id=f.get('tax_id', '').strip() or None,
                currency=f.get('currency', 'CAD'),
                account_number=f.get('account_number', '').strip() or None,
                notes=f.get('notes', '').strip() or None,
                division_id=int(f['division_id']) if f.get('division_id') else None,
                created_by=current_user.id,
            )
            vendor.trade_categories = f.getlist('trade_categories')
            db.add(vendor)
            db.commit()
            flash(f'Vendor {vendor.vendor_number} created.', 'success')
            return redirect(url_for('vendors.vendor_detail', vendor_id=vendor.id))

        return render_template('vendors/vendor_form.html',
            active_page='vendors', user=current_user, divisions=_get_divisions(),
            vendor=None, vendor_types=VENDOR_TYPES, vendor_statuses=VENDOR_STATUSES,
            payment_terms=PAYMENT_TERMS, trade_categories=TRADE_CATEGORIES,
            all_divisions=all_divisions, mode='new',
        )
    finally:
        db.close()


# ── Edit ──────────────────────────────────────────────────────────────────────

@vendor_bp.route('/vendors/<int:vendor_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'owner')
def vendor_edit(vendor_id):
    db = get_session()
    try:
        vendor = db.query(Vendor).filter_by(id=vendor_id).first()
        if not vendor:
            flash('Vendor not found.', 'error')
            return redirect(url_for('vendors.vendor_list'))

        all_divisions = db.query(Division).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Division.sort_order).all()

        if request.method == 'POST':
            f = request.form
            vendor.company_name = f['company_name'].strip()
            vendor.doing_business_as = f.get('doing_business_as', '').strip() or None
            vendor.vendor_type = f.get('vendor_type', 'parts_supplier')
            vendor.status = f.get('status', vendor.status)
            vendor.contact_name = f.get('contact_name', '').strip() or None
            vendor.contact_email = f.get('contact_email', '').strip() or None
            vendor.contact_phone = f.get('contact_phone', '').strip() or None
            vendor.phone = f.get('phone', '').strip() or None
            vendor.email = f.get('email', '').strip() or None
            vendor.website = f.get('website', '').strip() or None
            vendor.address_line1 = f.get('address_line1', '').strip() or None
            vendor.city = f.get('city', '').strip() or None
            vendor.state_province = f.get('state_province', '').strip() or None
            vendor.postal_code = f.get('postal_code', '').strip() or None
            vendor.payment_terms = f.get('payment_terms', 'net_30')
            vendor.tax_id = f.get('tax_id', '').strip() or None
            vendor.account_number = f.get('account_number', '').strip() or None
            vendor.notes = f.get('notes', '').strip() or None
            vendor.division_id = int(f['division_id']) if f.get('division_id') else None
            vendor.trade_categories = f.getlist('trade_categories')
            db.commit()
            flash('Vendor updated.', 'success')
            return redirect(url_for('vendors.vendor_detail', vendor_id=vendor_id))

        return render_template('vendors/vendor_form.html',
            active_page='vendors', user=current_user, divisions=_get_divisions(),
            vendor=vendor, vendor_types=VENDOR_TYPES, vendor_statuses=VENDOR_STATUSES,
            payment_terms=PAYMENT_TERMS, trade_categories=TRADE_CATEGORIES,
            all_divisions=all_divisions, mode='edit',
        )
    finally:
        db.close()


# ── Deactivate ────────────────────────────────────────────────────────────────

@vendor_bp.route('/vendors/<int:vendor_id>/deactivate', methods=['POST'])
@login_required
@role_required('admin', 'owner')
def vendor_deactivate(vendor_id):
    db = get_session()
    try:
        vendor = db.query(Vendor).filter_by(id=vendor_id).first()
        if vendor:
            vendor.status = 'inactive'
            vendor.is_active = False
            db.commit()
            flash(f'{vendor.company_name} deactivated.', 'info')
    finally:
        db.close()
    return redirect(url_for('vendors.vendor_list'))


# ── Add Vendor Price ──────────────────────────────────────────────────────────

@vendor_bp.route('/vendors/<int:vendor_id>/prices/add', methods=['POST'])
@login_required
@role_required('admin', 'owner', 'dispatcher')
def add_vendor_price(vendor_id):
    db = get_session()
    try:
        f = request.form
        vp = VendorPrice(
            vendor_id=vendor_id,
            part_id=int(f['part_id']),
            vendor_part_number=f.get('vendor_part_number', '').strip() or None,
            unit_price=float(f['unit_price']),
            minimum_order_quantity=int(f.get('minimum_order_quantity', 1) or 1),
            bulk_price=float(f['bulk_price']) if f.get('bulk_price') else None,
            bulk_threshold=int(f['bulk_threshold']) if f.get('bulk_threshold') else None,
            lead_time_days=int(f['lead_time_days']) if f.get('lead_time_days') else None,
            is_preferred=f.get('is_preferred') == 'on' or f.get('is_preferred') == '1',
            price_valid_until=datetime.strptime(f['price_valid_until'], '%Y-%m-%d').date() if f.get('price_valid_until') else None,
            notes=f.get('notes', '').strip() or None,
        )
        db.add(vp)
        db.commit()
        flash('Pricing record added.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {e}', 'error')
    finally:
        db.close()
    return redirect(url_for('vendors.vendor_detail', vendor_id=vendor_id, tab='pricing'))


@vendor_bp.route('/vendors/prices/<int:price_id>/delete', methods=['POST'])
@login_required
@role_required('admin', 'owner')
def delete_vendor_price(price_id):
    db = get_session()
    try:
        vp = db.query(VendorPrice).filter_by(id=price_id).first()
        if vp:
            vid = vp.vendor_id
            db.delete(vp)
            db.commit()
            flash('Pricing record removed.', 'info')
            return redirect(url_for('vendors.vendor_detail', vendor_id=vid, tab='pricing'))
    finally:
        db.close()
    return redirect(url_for('vendors.vendor_list'))


# ── Record Vendor Payment ─────────────────────────────────────────────────────

@vendor_bp.route('/vendors/<int:vendor_id>/payments/record', methods=['POST'])
@login_required
@role_required('admin', 'owner')
def record_vendor_payment(vendor_id):
    db = get_session()
    try:
        f = request.form
        payment = VendorPayment(
            payment_number=VendorPayment.generate_payment_number(db),
            vendor_id=vendor_id,
            po_id=int(f['po_id']) if f.get('po_id') else None,
            amount=float(f['amount']),
            payment_date=datetime.strptime(f['payment_date'], '%Y-%m-%d').date() if f.get('payment_date') else date.today(),
            payment_method=f.get('payment_method', 'bank_transfer'),
            reference_number=f.get('reference_number', '').strip() or None,
            memo=f.get('memo', '').strip() or None,
            status='completed',
            created_by=current_user.id,
        )
        db.add(payment)

        # Update PO payment if linked
        if payment.po_id:
            po = db.query(SupplierPurchaseOrder).filter_by(id=payment.po_id).first()
            if po:
                po.amount_paid = float(po.amount_paid or 0) + float(payment.amount)
                if po.amount_paid >= float(po.total or 0):
                    po.payment_status = 'paid'
                else:
                    po.payment_status = 'partially_paid'

        # Update vendor balance
        vendor = db.query(Vendor).filter_by(id=vendor_id).first()
        if vendor:
            vendor.current_balance = max(0, float(vendor.current_balance or 0) - float(payment.amount))

        db.commit()
        flash(f'Payment {payment.payment_number} recorded: ${payment.amount:,.2f}', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {e}', 'error')
    finally:
        db.close()
    return redirect(url_for('vendors.vendor_detail', vendor_id=vendor_id, tab='payments'))


# ── API: vendor search ────────────────────────────────────────────────────────

@vendor_bp.route('/vendors/api/search')
@login_required
def vendor_api_search():
    db = get_session()
    try:
        term = request.args.get('q', '').strip()
        q = db.query(Vendor).filter(Vendor.is_active == True)
        if term:
            q = q.filter(Vendor.company_name.ilike(f'%{term}%'))
        vendors = q.order_by(Vendor.company_name).limit(20).all()
        return jsonify([{'id': v.id, 'text': v.display_name, 'vendor_number': v.vendor_number} for v in vendors])
    finally:
        db.close()


# ── Price Comparison ──────────────────────────────────────────────────────────

@vendor_bp.route('/vendors/price-comparison')
@login_required
def price_comparison():
    db = get_session()
    try:
        from models.part import Part
        parts = db.query(Part).order_by(Part.name).limit(200).all()
        part_id = request.args.get('part_id', type=int)
        selected_part = None
        vendor_prices = []

        if part_id:
            selected_part = db.query(Part).filter_by(id=part_id).first()
            vendor_prices = db.query(VendorPrice).filter_by(part_id=part_id).all()
            vendor_prices.sort(key=lambda vp: float(vp.unit_price))

        return render_template('vendors/price_comparison.html',
            active_page='vendors', user=current_user, divisions=_get_divisions(),
            parts=parts, selected_part=selected_part, vendor_prices=vendor_prices,
        )
    finally:
        db.close()


# ── CSV Import Vendor Pricing ─────────────────────────────────────────────────

@vendor_bp.route('/vendors/<int:vendor_id>/prices/import', methods=['POST'])
@login_required
@role_required('admin', 'owner')
def import_vendor_pricing(vendor_id):
    import csv, io
    db = get_session()
    try:
        file = request.files.get('csv_file')
        if not file:
            flash('No file uploaded.', 'error')
            return redirect(url_for('vendors.vendor_detail', vendor_id=vendor_id, tab='pricing'))

        from models.part import Part
        stream = io.StringIO(file.stream.read().decode('utf-8-sig'))
        reader = csv.DictReader(stream)
        imported = updated = 0
        errors = []

        for i, row in enumerate(reader, start=2):
            part_number = row.get('part_number', '').strip()
            if not part_number:
                continue
            part = db.query(Part).filter_by(part_number=part_number).first()
            if not part:
                errors.append(f"Row {i}: Part '{part_number}' not found")
                continue
            try:
                unit_price = float(row.get('unit_price', '0'))
            except ValueError:
                errors.append(f"Row {i}: Invalid price")
                continue

            existing = db.query(VendorPrice).filter_by(vendor_id=vendor_id, part_id=part.id).first()
            if existing:
                existing.unit_price = unit_price
                existing.vendor_part_number = row.get('vendor_part_number', '').strip() or existing.vendor_part_number
                if row.get('bulk_price'):
                    existing.bulk_price = float(row['bulk_price'])
                if row.get('bulk_threshold'):
                    existing.bulk_threshold = int(row['bulk_threshold'])
                if row.get('lead_time_days'):
                    existing.lead_time_days = int(row['lead_time_days'])
                updated += 1
            else:
                vp = VendorPrice(
                    vendor_id=vendor_id, part_id=part.id,
                    vendor_part_number=row.get('vendor_part_number', '').strip() or None,
                    unit_price=unit_price,
                    bulk_price=float(row['bulk_price']) if row.get('bulk_price') else None,
                    bulk_threshold=int(row['bulk_threshold']) if row.get('bulk_threshold') else None,
                    lead_time_days=int(row['lead_time_days']) if row.get('lead_time_days') else None,
                )
                db.add(vp)
                imported += 1

        db.commit()
        msg = f'Import: {imported} added, {updated} updated.'
        if errors:
            msg += f' {len(errors)} errors.'
        flash(msg, 'success' if not errors else 'warning')
    except Exception as e:
        db.rollback()
        flash(f'Import error: {e}', 'error')
    finally:
        db.close()
    return redirect(url_for('vendors.vendor_detail', vendor_id=vendor_id, tab='pricing'))


# ── API: vendor prices for PO form autofill ───────────────────────────────────

@vendor_bp.route('/vendors/api/prices/<int:vendor_id>')
@login_required
def api_vendor_prices(vendor_id):
    db = get_session()
    try:
        from models.part import Part
        prices = db.query(VendorPrice).filter_by(vendor_id=vendor_id).all()
        return jsonify([{
            'part_id': vp.part_id,
            'part_name': vp.part.name if vp.part else '',
            'part_number': vp.part.part_number if vp.part else '',
            'vendor_part_number': vp.vendor_part_number,
            'unit_price': float(vp.unit_price),
            'lead_time_days': vp.lead_time_days,
        } for vp in prices])
    finally:
        db.close()
