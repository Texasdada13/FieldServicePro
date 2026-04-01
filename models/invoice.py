"""Invoice and Payment models."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
import enum
from .database import Base


class InvoiceStatus(enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    VIEWED = "viewed"
    PARTIAL = "partial"
    PAID = "paid"
    OVERDUE = "overdue"
    VOID = "void"


class Invoice(Base):
    __tablename__ = 'invoices'

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    job_id = Column(Integer, ForeignKey('jobs.id'))

    invoice_number = Column(String(50), unique=True, index=True)
    status = Column(String(20), default=InvoiceStatus.DRAFT.value, index=True)

    # Financial
    subtotal = Column(Float, default=0)
    tax_rate = Column(Float, default=13.0)
    tax_amount = Column(Float, default=0)
    total = Column(Float, default=0)
    amount_paid = Column(Float, default=0)
    balance_due = Column(Float, default=0)

    # Dates
    issued_date = Column(DateTime)
    due_date = Column(DateTime)
    paid_date = Column(DateTime)

    notes = Column(Text)
    created_by_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    client = relationship("Client", back_populates="invoices")
    job = relationship("Job", back_populates="invoices")
    items = relationship("InvoiceItem", back_populates="invoice", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="invoice", cascade="all, delete-orphan")

    @property
    def is_overdue(self):
        if self.status in ('paid', 'void'):
            return False
        if self.due_date and self.due_date < datetime.utcnow():
            return True
        return False

    def to_dict(self):
        return {
            'id': self.id,
            'invoice_number': self.invoice_number,
            'status': self.status,
            'client_id': self.client_id,
            'job_id': self.job_id,
            'subtotal': self.subtotal,
            'tax_rate': self.tax_rate,
            'tax_amount': self.tax_amount,
            'total': self.total,
            'amount_paid': self.amount_paid,
            'balance_due': self.balance_due,
            'issued_date': self.issued_date.isoformat() if self.issued_date else None,
            'due_date': self.due_date.isoformat() if self.due_date else None,
            'is_overdue': self.is_overdue,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class InvoiceItem(Base):
    __tablename__ = 'invoice_items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey('invoices.id'), nullable=False)
    description = Column(String(500), nullable=False)
    quantity = Column(Float, default=1)
    unit_price = Column(Float, default=0)
    total = Column(Float, default=0)
    sort_order = Column(Integer, default=0)

    invoice = relationship("Invoice", back_populates="items")

    def to_dict(self):
        return {
            'id': self.id,
            'description': self.description,
            'quantity': self.quantity,
            'unit_price': self.unit_price,
            'total': self.total
        }


class Payment(Base):
    __tablename__ = 'payments'

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(Integer, ForeignKey('invoices.id'), nullable=False)
    amount = Column(Float, nullable=False)
    payment_method = Column(String(50))  # cash, cheque, e-transfer, credit_card
    reference_number = Column(String(100))
    notes = Column(Text)
    payment_date = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    invoice = relationship("Invoice", back_populates="payments")

    def to_dict(self):
        return {
            'id': self.id,
            'amount': self.amount,
            'payment_method': self.payment_method,
            'reference_number': self.reference_number,
            'payment_date': self.payment_date.isoformat() if self.payment_date else None
        }
