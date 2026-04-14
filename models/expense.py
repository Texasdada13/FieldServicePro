"""Expense Tracking models."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean,
    Date, DateTime, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from .database import Base


EXPENSE_CATEGORIES = [
    ('equipment_rental', 'Equipment Rental'), ('subcontractor', 'Subcontractor'),
    ('permit_fee', 'Permit Fee'), ('disposal', 'Disposal'),
    ('fuel_mileage', 'Fuel / Mileage'), ('tools', 'Tools'),
    ('supplies', 'Supplies'), ('meals', 'Meals'), ('travel', 'Travel'),
    ('parking', 'Parking'), ('shipping', 'Shipping'), ('insurance', 'Insurance'),
    ('inspection_fee', 'Inspection Fee'), ('utility_connection', 'Utility Connection'),
    ('temporary_services', 'Temporary Services'), ('office_supplies', 'Office Supplies'),
    ('other', 'Other'),
]

EXPENSE_STATUSES = [
    ('draft', 'Draft'), ('submitted', 'Submitted'), ('approved', 'Approved'),
    ('rejected', 'Rejected'), ('reimbursed', 'Reimbursed'), ('voided', 'Voided'),
]

PAYMENT_METHODS = [
    ('company_card', 'Company Card'), ('cash', 'Cash'),
    ('personal_card_reimbursement', 'Personal Card (Reimburse)'),
    ('check', 'Check'), ('account', 'Account / Net Terms'), ('other', 'Other'),
]

EXPENSE_STATUS_COLORS = {
    'draft': 'secondary', 'submitted': 'accent', 'approved': 'success',
    'rejected': 'danger', 'reimbursed': 'info', 'voided': 'secondary',
}

CATEGORY_COLORS = {
    'equipment_rental': 'accent', 'subcontractor': 'info', 'permit_fee': 'success',
    'disposal': 'warning', 'fuel_mileage': 'warning', 'tools': 'secondary',
    'supplies': 'info', 'meals': 'success', 'travel': 'accent',
    'other': 'secondary',
}


class Expense(Base):
    __tablename__ = 'expenses'

    id = Column(Integer, primary_key=True)
    expense_number = Column(String(20), unique=True, nullable=False, index=True)

    # Core
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    expense_category = Column(String(30), nullable=False, default='other')

    # Amounts
    amount = Column(Float, nullable=False, default=0)
    tax_amount = Column(Float, nullable=False, default=0)
    total_amount = Column(Float, nullable=False, default=0)

    # Links
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=True, index=True)
    phase_id = Column(Integer, ForeignKey('job_phases.id'), nullable=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True, index=True)
    division_id = Column(Integer, ForeignKey('divisions.id'), nullable=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=True, index=True)

    # Billing
    is_billable = Column(Boolean, default=False, nullable=False)
    is_reimbursable = Column(Boolean, default=False, nullable=False)
    markup_percentage = Column(Float, default=0, nullable=False)
    billable_amount = Column(Float, nullable=True)
    invoice_id = Column(Integer, ForeignKey('invoices.id'), nullable=True)
    invoiced = Column(Boolean, default=False, nullable=False)
    po_id = Column(Integer, ForeignKey('purchase_orders.id'), nullable=True)

    # Vendor
    vendor_name = Column(String(255), nullable=True)
    receipt_number = Column(String(100), nullable=True)
    payment_method = Column(String(30), nullable=True, default='company_card')
    paid_by = Column(Integer, ForeignKey('users.id'), nullable=True)

    # Dates
    expense_date = Column(Date, nullable=False)
    submitted_date = Column(Date, nullable=True)
    approved_date = Column(Date, nullable=True)

    # Workflow
    status = Column(String(20), nullable=False, default='draft')
    approved_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    rejection_reason = Column(Text, nullable=True)
    reimbursed_date = Column(Date, nullable=True)
    reimbursed_amount = Column(Float, nullable=True)

    # Receipt
    receipt_document_id = Column(Integer, ForeignKey('documents.id'), nullable=True)

    # Metadata
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    job = relationship('Job', back_populates='expenses', foreign_keys=[job_id])
    phase = relationship('JobPhase', foreign_keys=[phase_id])
    project = relationship('Project', back_populates='expenses', foreign_keys=[project_id])
    division = relationship('Division', foreign_keys=[division_id])
    client = relationship('Client', foreign_keys=[client_id])
    invoice = relationship('Invoice', foreign_keys=[invoice_id])
    po = relationship('PurchaseOrder', foreign_keys=[po_id])
    paid_by_user = relationship('User', foreign_keys=[paid_by])
    approved_by_user = relationship('User', foreign_keys=[approved_by])
    created_by_user = relationship('User', foreign_keys=[created_by])
    receipt_document = relationship('Document', foreign_keys=[receipt_document_id])
    mileage_entry = relationship('MileageEntry', back_populates='expense', uselist=False, cascade='all, delete-orphan')

    __table_args__ = (
        Index('ix_expenses_status', 'status'),
        Index('ix_expenses_date', 'expense_date'),
    )

    def compute_totals(self):
        amt = float(self.amount or 0)
        tax = float(self.tax_amount or 0)
        self.total_amount = round(amt + tax, 2)
        if self.is_billable:
            markup = float(self.markup_percentage or 0)
            self.billable_amount = round((amt + tax) * (1 + markup / 100), 2)
        else:
            self.billable_amount = None

    @property
    def category_display(self):
        return dict(EXPENSE_CATEGORIES).get(self.expense_category, self.expense_category)

    @property
    def category_color(self):
        return CATEGORY_COLORS.get(self.expense_category, 'secondary')

    @property
    def status_display(self):
        return dict(EXPENSE_STATUSES).get(self.status, self.status)

    @property
    def status_color(self):
        return EXPENSE_STATUS_COLORS.get(self.status, 'secondary')

    @property
    def payment_method_display(self):
        return dict(PAYMENT_METHODS).get(self.payment_method, self.payment_method or '')

    def to_dict(self):
        return {
            'id': self.id, 'expense_number': self.expense_number,
            'title': self.title, 'expense_category': self.expense_category,
            'amount': self.amount, 'total_amount': self.total_amount,
            'status': self.status, 'expense_date': self.expense_date.isoformat() if self.expense_date else None,
            'is_billable': self.is_billable, 'job_id': self.job_id,
        }


class MileageEntry(Base):
    __tablename__ = 'mileage_entries'

    id = Column(Integer, primary_key=True)
    expense_id = Column(Integer, ForeignKey('expenses.id', ondelete='CASCADE'), nullable=False, unique=True)

    start_location = Column(String(255), nullable=False)
    end_location = Column(String(255), nullable=False)
    distance_miles = Column(Float, nullable=False, default=0)
    mileage_rate = Column(Float, nullable=False, default=0.67)
    calculated_amount = Column(Float, nullable=False, default=0)
    vehicle_id = Column(Integer, ForeignKey('equipment.id'), nullable=True)
    is_round_trip = Column(Boolean, default=False, nullable=False)
    purpose = Column(String(255), nullable=True)

    expense = relationship('Expense', back_populates='mileage_entry')
    vehicle = relationship('Equipment', foreign_keys=[vehicle_id])

    def compute_amount(self):
        miles = float(self.distance_miles or 0)
        rate = float(self.mileage_rate or 0)
        if self.is_round_trip:
            miles *= 2
        self.calculated_amount = round(miles * rate, 2)
        return self.calculated_amount
