"""Vendor management utility functions."""
from models.vendor import Vendor
from models.supplier_po import SupplierPurchaseOrder


def get_vendor_stats(db):
    total = db.query(Vendor).count()
    active = db.query(Vendor).filter_by(status='active').count()
    preferred = db.query(Vendor).filter_by(status='preferred').count()
    pending_delivery = db.query(SupplierPurchaseOrder).filter(
        SupplierPurchaseOrder.status.in_(['submitted', 'acknowledged', 'partially_received'])
    ).count()
    return {'total': total, 'active': active, 'preferred': preferred, 'pending_delivery': pending_delivery}
