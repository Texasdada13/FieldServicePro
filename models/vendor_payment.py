"""Vendor Payment tracking."""
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, Float, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


PAYMENT_METHODS = [
    ('check', 'Check'), ('bank_transfer', 'Bank Transfer'),
    ('credit_card', 'Credit Card'), ('company_card', 'Company Card'),
    ('cash', 'Cash'), ('other', 'Other'),
]


class VendorPayment(Base):
    __tablename__ = 'vendor_payments'

    id = Column(Integer, primary_key=True)
    payment_number = Column(String(20), unique=True, nullable=False, index=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id'), nullable=False, index=True)
    po_id = Column(Integer, ForeignKey('supplier_purchase_orders.id'), nullable=True)
    amount = Column(Float, nullable=False)
    payment_date = Column(Date, nullable=False, default=date.today)
    payment_method = Column(String(30), nullable=False, default='bank_transfer')
    reference_number = Column(String(100), nullable=True)
    memo = Column(Text, nullable=True)
    status = Column(String(20), nullable=False, default='completed')
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    vendor = relationship('Vendor', backref='payments')
    po = relationship('SupplierPurchaseOrder', backref='vendor_payments')
    creator = relationship('User', foreign_keys=[created_by])

    @staticmethod
    def generate_payment_number(db):
        year = date.today().year
        last = db.query(VendorPayment).filter(
            VendorPayment.payment_number.like(f'VP-{year}-%')
        ).order_by(VendorPayment.payment_number.desc()).first()
        seq = int(last.payment_number.split('-')[-1]) + 1 if last else 1
        return f"VP-{year}-{seq:04d}"
