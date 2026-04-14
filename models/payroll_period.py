"""Payroll Period — groups time entries and expenses into pay periods."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


PAYROLL_STATUSES = [
    ('open', 'Open'), ('processing', 'Processing'),
    ('finalized', 'Finalized'), ('exported', 'Exported'),
]

PAY_FREQUENCIES = [
    ('weekly', 'Weekly'), ('biweekly', 'Biweekly'),
    ('semi_monthly', 'Semi-Monthly'), ('monthly', 'Monthly'),
]

STATUS_COLORS = {
    'open': 'success', 'processing': 'warning',
    'finalized': 'accent', 'exported': 'secondary',
}


class PayrollPeriod(Base):
    __tablename__ = 'payroll_periods'

    id = Column(Integer, primary_key=True)
    period_name = Column(String(100), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)

    status = Column(String(20), default='open', nullable=False)
    pay_frequency = Column(String(20), default='biweekly', nullable=False)

    # Computed totals (stored at finalize time)
    total_regular_hours = Column(Float, default=0)
    total_overtime_hours = Column(Float, default=0)
    total_double_time_hours = Column(Float, default=0)
    total_gross_pay = Column(Float, default=0)
    total_reimbursements = Column(Float, default=0)

    # Finalization
    finalized_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    finalized_at = Column(DateTime, nullable=True)
    exported_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    line_items = relationship('PayrollLineItem', back_populates='period',
                              cascade='all, delete-orphan')
    finalized_by_user = relationship('User', foreign_keys=[finalized_by])

    @property
    def total_hours(self):
        return (float(self.total_regular_hours or 0) +
                float(self.total_overtime_hours or 0) +
                float(self.total_double_time_hours or 0))

    @property
    def total_compensation(self):
        return float(self.total_gross_pay or 0) + float(self.total_reimbursements or 0)

    @property
    def is_editable(self):
        return self.status in ('open', 'processing')

    @property
    def status_color(self):
        return STATUS_COLORS.get(self.status, 'secondary')

    def refresh_totals(self):
        """Recompute aggregate columns from child line items."""
        self.total_regular_hours = sum(float(li.regular_hours or 0) for li in self.line_items)
        self.total_overtime_hours = sum(float(li.overtime_hours or 0) for li in self.line_items)
        self.total_double_time_hours = sum(float(li.double_time_hours or 0) for li in self.line_items)
        self.total_gross_pay = sum(float(li.gross_pay or 0) for li in self.line_items)
        self.total_reimbursements = sum(float(li.reimbursable_expenses or 0) for li in self.line_items)

    def to_dict(self):
        return {
            'id': self.id, 'period_name': self.period_name,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'status': self.status, 'pay_frequency': self.pay_frequency,
            'total_hours': self.total_hours,
            'total_gross_pay': float(self.total_gross_pay or 0),
            'total_reimbursements': float(self.total_reimbursements or 0),
            'total_compensation': self.total_compensation,
            'line_item_count': len(self.line_items) if self.line_items else 0,
        }
