"""
Purchase Order balance tracking, linking, and exhaustion utilities.
Called from invoice save/update logic and PO API endpoints.
Uses raw SQLAlchemy sessions (not Flask-SQLAlchemy).
"""
from datetime import date
from sqlalchemy import func
from models.purchase_order import PurchaseOrder
from models.invoice import Invoice


def recalculate_po_balance(db, po):
    """
    Recompute amount_used from all non-cancelled linked invoices.
    Auto-transitions status. Caller must commit.
    """
    linked_total = db.query(
        func.coalesce(func.sum(Invoice.total), 0)
    ).filter(
        Invoice.po_id == po.id,
        Invoice.status.notin_(['void', 'cancelled']),
    ).scalar()

    po.amount_used = float(linked_total or 0)

    if po.status == 'cancelled':
        return

    today = date.today()
    if po.expiry_date and po.expiry_date < today:
        po.status = 'expired'
    elif po.amount_used >= float(po.amount_authorized or 0):
        po.status = 'exhausted'
    elif po.status in ('exhausted', 'expired') and po.amount_used < float(po.amount_authorized or 0):
        if not po.expiry_date or po.expiry_date >= today:
            po.status = 'active'


def check_po_capacity(db, po, invoice_amount, exclude_invoice_id=None):
    """
    Non-blocking capacity check. Returns dict with warnings/errors.
    """
    result = {
        'can_cover': False,
        'remaining': 0.0,
        'overage': 0.0,
        'warnings': [],
        'errors': [],
    }

    if po.status == 'cancelled':
        result['errors'].append(f"PO {po.po_number} has been cancelled.")
        return result

    today = date.today()
    if po.expiry_date and po.expiry_date < today:
        result['errors'].append(f"PO {po.po_number} expired on {po.expiry_date.strftime('%b %d, %Y')}.")
        return result

    # Compute used excluding the invoice being edited
    q = db.query(func.coalesce(func.sum(Invoice.total), 0)).filter(
        Invoice.po_id == po.id,
        Invoice.status.notin_(['void', 'cancelled']),
    )
    if exclude_invoice_id:
        q = q.filter(Invoice.id != exclude_invoice_id)
    used = float(q.scalar() or 0)

    authorized = float(po.amount_authorized or 0)
    remaining = authorized - used
    result['remaining'] = remaining
    invoice_amt = float(invoice_amount or 0)

    if invoice_amt <= remaining:
        result['can_cover'] = True
        pct_after = ((used + invoice_amt) / authorized * 100) if authorized else 0
        if pct_after >= 90:
            result['warnings'].append(
                f"This invoice will use {pct_after:.1f}% of PO {po.po_number}. "
                f"Only ${remaining - invoice_amt:,.2f} will remain."
            )
    else:
        overage = invoice_amt - remaining
        result['overage'] = overage
        result['warnings'].append(
            f"Invoice amount (${invoice_amt:,.2f}) exceeds PO {po.po_number} "
            f"remaining balance (${remaining:,.2f}) by ${overage:,.2f}. "
            "You may still save — the PO will show as over-authorized."
        )

    return result


def link_invoice_to_po(db, invoice, po):
    """
    Attach invoice to PO, update balance. Returns capacity dict.
    Does NOT commit.
    """
    capacity = check_po_capacity(db, po, float(invoice.total or 0),
                                  exclude_invoice_id=invoice.id)

    invoice.po_id = po.id
    invoice.po_number_display = po.po_number

    if po.cost_code and not invoice.cost_code:
        invoice.cost_code = po.cost_code
    if po.department and not invoice.department:
        invoice.department = po.department

    recalculate_po_balance(db, po)
    return capacity


def unlink_invoice_from_po(db, invoice):
    """
    Remove PO link from invoice and refresh PO balance.
    Does NOT commit.
    """
    if not invoice.po_id:
        return
    po = db.query(PurchaseOrder).filter_by(id=invoice.po_id).first()
    invoice.po_id = None
    if po:
        recalculate_po_balance(db, po)


def get_active_pos_for_client(db, client_id):
    """Return active, non-expired POs for a client."""
    today = date.today()
    pos = db.query(PurchaseOrder).filter(
        PurchaseOrder.client_id == client_id,
        PurchaseOrder.status == 'active',
    ).order_by(PurchaseOrder.expiry_date.asc().nullslast()).all()

    result = []
    for po in pos:
        if po.expiry_date and po.expiry_date < today:
            po.status = 'expired'
        else:
            result.append(po)
    return result


def handle_po_linking(db, invoice, new_po_id_raw):
    """
    Reconcile PO link on invoice save. Returns list of warning strings.
    Raises ValueError for hard blocking errors.
    """
    warnings = []
    old_po_id = invoice.po_id
    new_po_id = int(new_po_id_raw) if new_po_id_raw else None

    if old_po_id == new_po_id:
        if new_po_id:
            po = db.query(PurchaseOrder).filter_by(id=new_po_id).first()
            if po:
                recalculate_po_balance(db, po)
        return warnings

    if old_po_id:
        unlink_invoice_from_po(db, invoice)

    if new_po_id:
        po = db.query(PurchaseOrder).filter_by(id=new_po_id).first()
        if not po:
            raise ValueError(f"Purchase Order ID {new_po_id} not found.")
        capacity = link_invoice_to_po(db, invoice, po)
        if capacity['errors']:
            raise ValueError(capacity['errors'][0])
        warnings.extend(capacity['warnings'])

    return warnings
