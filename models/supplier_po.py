"""Supplier Purchase Order and Line Items."""
from datetime import datetime, date, timedelta
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


SPO_STATUSES = [
    ('draft', 'Draft'), ('submitted', 'Submitted'), ('acknowledged', 'Acknowledged'),
    ('partially_received', 'Partially Received'), ('received', 'Received'),
    ('cancelled', 'Cancelled'), ('disputed', 'Disputed'),
]

PAYMENT_STATUSES = [('unpaid', 'Unpaid'), ('partially_paid', 'Partially Paid'), ('paid', 'Paid')]


class SupplierPurchaseOrder(Base):
    __tablename__ = 'supplier_purchase_orders'

    id = Column(Integer, primary_key=True)
    po_number = Column(String(20), unique=True, nullable=False, index=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False, index=True)
    status = Column(String(30), nullable=False, default='draft')

    order_date = Column(Date, nullable=False, default=date.today)
    expected_delivery_date = Column(Date, nullable=True)
    actual_delivery_date = Column(Date, nullable=True)

    subtotal = Column(Float, nullable=False, default=0)
    tax_rate = Column(Float, nullable=False, default=13)
    tax_amount = Column(Float, nullable=False, default=0)
    shipping_cost = Column(Float, nullable=False, default=0)
    total = Column(Float, nullable=False, default=0)

    payment_terms = Column(String(30), nullable=False, default='net_30')
    payment_due_date = Column(Date, nullable=True)
    payment_status = Column(String(20), nullable=False, default='unpaid')
    amount_paid = Column(Float, nullable=False, default=0)

    delivery_address = Column(String(400), nullable=True)
    shipping_method = Column(String(100), nullable=True)
    tracking_number = Column(String(200), nullable=True)

    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)
    requested_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    approved_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    notes = Column(Text, nullable=True)
    internal_notes = Column(Text, nullable=True)

    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    vendor = relationship('Vendor', backref='purchase_orders')
    line_items = relationship('SupplierPOLineItem', back_populates='po', cascade='all, delete-orphan')
    job = relationship('Job', foreign_keys=[job_id])
    project = relationship('Project', foreign_keys=[project_id])
    requester = relationship('User', foreign_keys=[requested_by])
    approver = relationship('User', foreign_keys=[approved_by])
    creator = relationship('User', foreign_keys=[created_by])

    def recalculate_totals(self):
        subtotal = sum(float(item.quantity_ordered or 0) * float(item.unit_price or 0) for item in self.line_items)
        self.subtotal = round(subtotal, 2)
        self.tax_amount = round(subtotal * (self.tax_rate or 0) / 100, 2)
        self.total = round(subtotal + self.tax_amount + float(self.shipping_cost or 0), 2)

    @property
    def balance_due(self):
        return max(float(self.total or 0) - float(self.amount_paid or 0), 0)

    @property
    def receipt_progress(self):
        ordered = sum(i.quantity_ordered for i in self.line_items)
        received = sum(i.quantity_received for i in self.line_items)
        return int((received / ordered) * 100) if ordered else 0

    @property
    def status_color(self):
        return {'draft': 'secondary', 'submitted': 'accent', 'acknowledged': 'info',
                'partially_received': 'warning', 'received': 'success',
                'cancelled': 'secondary', 'disputed': 'danger'}.get(self.status, 'secondary')

    @staticmethod
    def generate_po_number(db):
        from sqlalchemy import func
        year = date.today().year
        last = db.query(SupplierPurchaseOrder).filter(
            SupplierPurchaseOrder.po_number.like(f'SPO-{year}-%')
        ).order_by(SupplierPurchaseOrder.po_number.desc()).first()
        seq = int(last.po_number.split('-')[-1]) + 1 if last else 1
        return f"SPO-{year}-{seq:04d}"

    def to_dict(self):
        return {
            'id': self.id, 'po_number': self.po_number,
            'vendor_name': self.vendor.display_name if self.vendor else '--',
            'status': self.status, 'total': float(self.total or 0),
            'balance_due': self.balance_due, 'receipt_progress': self.receipt_progress,
        }


class SupplierPOLineItem(Base):
    __tablename__ = 'supplier_po_line_items'

    id = Column(Integer, primary_key=True)
    po_id = Column(Integer, ForeignKey('supplier_purchase_orders.id', ondelete='CASCADE'), nullable=False)
    part_id = Column(Integer, ForeignKey('parts.id'), nullable=True)
    description = Column(String(300), nullable=False)
    vendor_part_number = Column(String(100), nullable=True)
    quantity_ordered = Column(Integer, nullable=False, default=1)
    quantity_received = Column(Integer, nullable=False, default=0)
    unit_price = Column(Float, nullable=False, default=0)
    received_date = Column(Date, nullable=True)
    is_back_ordered = Column(Boolean, nullable=False, default=False)
    notes = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)

    po = relationship('SupplierPurchaseOrder', back_populates='line_items')
    part = relationship('Part', foreign_keys=[part_id])

    @property
    def line_total(self):
        return round(float(self.quantity_ordered or 0) * float(self.unit_price or 0), 2)

    @property
    def quantity_outstanding(self):
        return max(self.quantity_ordered - self.quantity_received, 0)
