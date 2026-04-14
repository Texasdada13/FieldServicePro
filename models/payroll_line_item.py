"""Payroll Line Item — per-technician pay breakdown within a period."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


LINE_ITEM_STATUSES = [
    ('draft', 'Draft'), ('reviewed', 'Reviewed'), ('approved', 'Approved'),
]


class PayrollLineItem(Base):
    __tablename__ = 'payroll_line_items'

    id = Column(Integer, primary_key=True)
    period_id = Column(Integer, ForeignKey('payroll_periods.id', ondelete='CASCADE'), nullable=False)
    technician_id = Column(Integer, ForeignKey('technicians.id'), nullable=False)

    # Hours
    regular_hours = Column(Float, default=0)
    overtime_hours = Column(Float, default=0)
    double_time_hours = Column(Float, default=0)

    # Rates (snapshot at calculation time)
    regular_rate = Column(Float, default=0)
    overtime_rate = Column(Float, default=0)
    double_time_rate = Column(Float, default=0)

    # Pay amounts
    regular_pay = Column(Float, default=0)
    overtime_pay = Column(Float, default=0)
    double_time_pay = Column(Float, default=0)
    reimbursable_expenses = Column(Float, default=0)

    # Counts
    jobs_worked = Column(Integer, default=0)
    days_worked = Column(Integer, default=0)

    # Status
    status = Column(String(20), default='draft')
    notes = Column(Text, nullable=True)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    period = relationship('PayrollPeriod', back_populates='line_items')
    technician = relationship('Technician', foreign_keys=[technician_id])

    @property
    def gross_pay(self):
        return (float(self.regular_pay or 0) +
                float(self.overtime_pay or 0) +
                float(self.double_time_pay or 0))

    @property
    def total_compensation(self):
        return self.gross_pay + float(self.reimbursable_expenses or 0)

    @property
    def total_hours(self):
        return (float(self.regular_hours or 0) +
                float(self.overtime_hours or 0) +
                float(self.double_time_hours or 0))

    @property
    def effective_hourly_rate(self):
        if self.total_hours > 0:
            return round(self.gross_pay / self.total_hours, 2)
        return 0.0

    @property
    def status_color(self):
        return {'draft': 'secondary', 'reviewed': 'warning', 'approved': 'success'}.get(self.status, 'secondary')

    def to_dict(self):
        return {
            'id': self.id, 'period_id': self.period_id,
            'technician_id': self.technician_id,
            'regular_hours': float(self.regular_hours or 0),
            'overtime_hours': float(self.overtime_hours or 0),
            'double_time_hours': float(self.double_time_hours or 0),
            'total_hours': self.total_hours,
            'gross_pay': self.gross_pay,
            'reimbursable_expenses': float(self.reimbursable_expenses or 0),
            'total_compensation': self.total_compensation,
            'jobs_worked': self.jobs_worked, 'days_worked': self.days_worked,
            'status': self.status,
        }
