"""Warranty and Warranty Claim models."""
from datetime import date, datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Date, DateTime,
    Float, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from .database import Base


WARRANTY_TYPES = [
    ('labor_only', 'Labor Only'), ('parts_only', 'Parts Only'),
    ('parts_and_labor', 'Parts & Labor'), ('manufacturer', 'Manufacturer'),
    ('extended', 'Extended'), ('custom', 'Custom'),
]

WARRANTY_STATUSES = [
    ('active', 'Active'), ('expiring_soon', 'Expiring Soon'),
    ('expired', 'Expired'), ('voided', 'Voided'), ('claimed', 'Claimed'),
]

WARRANTY_STATUS_COLORS = {
    'active': 'success', 'expiring_soon': 'warning',
    'expired': 'danger', 'voided': 'secondary', 'claimed': 'info',
}

CLAIM_TYPES = [
    ('labor', 'Labor'), ('parts', 'Parts'), ('parts_and_labor', 'Parts & Labor'),
]

CLAIM_STATUSES = [
    ('open', 'Open'), ('approved', 'Approved'),
    ('denied', 'Denied'), ('completed', 'Completed'),
]

CLAIM_STATUS_COLORS = {
    'open': 'accent', 'approved': 'success', 'denied': 'danger', 'completed': 'secondary',
}


class Warranty(Base):
    __tablename__ = 'warranties'

    id = Column(Integer, primary_key=True)
    warranty_number = Column(String(20), unique=True, nullable=False, index=True)

    # Core relationships
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=False)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    property_id = Column(Integer, ForeignKey('properties.id'), nullable=True)

    # Details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    warranty_type = Column(String(20), nullable=False, default='parts_and_labor')
    coverage_scope = Column(Text, nullable=True)

    # Coverage period
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    duration_months = Column(Integer, nullable=False, default=12)
    status = Column(String(20), nullable=False, default='active')

    # Financial
    max_claim_value = Column(Float, nullable=True)
    total_claimed = Column(Float, nullable=False, default=0)

    # Parts coverage
    covers_parts = Column(Boolean, default=True, nullable=False)
    covered_parts = Column(Text, nullable=True)
    manufacturer_warranty_info = Column(Text, nullable=True)
    manufacturer_warranty_end_date = Column(Date, nullable=True)

    # Equipment
    equipment_serial_number = Column(String(100), nullable=True)
    model_number = Column(String(100), nullable=True)

    # Admin
    notes = Column(Text, nullable=True)
    terms_and_conditions = Column(Text, nullable=True)
    voided_reason = Column(Text, nullable=True)
    voided_date = Column(Date, nullable=True)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    job = relationship('Job', foreign_keys=[job_id], back_populates='warranties')
    client = relationship('Client', back_populates='warranties')
    property_rel = relationship('Property', foreign_keys=[property_id])
    claims = relationship('WarrantyClaim', back_populates='warranty',
                          cascade='all, delete-orphan', order_by='WarrantyClaim.claimed_date.desc()')
    creator = relationship('User', foreign_keys=[created_by])

    __table_args__ = (
        Index('ix_warranty_client', 'client_id'),
        Index('ix_warranty_status', 'status'),
    )

    @property
    def type_display(self):
        return dict(WARRANTY_TYPES).get(self.warranty_type, self.warranty_type)

    @property
    def status_display(self):
        return dict(WARRANTY_STATUSES).get(self.status, self.status)

    @property
    def status_color(self):
        return WARRANTY_STATUS_COLORS.get(self.status, 'secondary')

    @property
    def remaining_coverage(self):
        if self.max_claim_value is None:
            return None
        return float(self.max_claim_value) - float(self.total_claimed or 0)

    @property
    def days_remaining(self):
        if self.end_date:
            return (self.end_date - date.today()).days
        return None

    @property
    def is_active_warranty(self):
        return self.status in ('active', 'expiring_soon')

    def refresh_status(self):
        """Update status based on current date. Caller must commit."""
        if self.status == 'voided':
            return
        today = date.today()
        if self.end_date < today:
            self.status = 'expired'
        elif (self.end_date - today).days <= 30:
            self.status = 'expiring_soon'
        elif self.status in ('expired', 'expiring_soon'):
            self.status = 'active'

    def to_dict(self):
        return {
            'id': self.id,
            'warranty_number': self.warranty_number,
            'title': self.title,
            'warranty_type': self.warranty_type,
            'status': self.status,
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'days_remaining': self.days_remaining,
            'max_claim_value': self.max_claim_value,
            'total_claimed': self.total_claimed,
            'remaining_coverage': self.remaining_coverage,
        }


class WarrantyClaim(Base):
    __tablename__ = 'warranty_claims'

    id = Column(Integer, primary_key=True)
    claim_number = Column(String(20), unique=True, nullable=False, index=True)

    warranty_id = Column(Integer, ForeignKey('warranties.id'), nullable=False)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=False)

    description = Column(Text, nullable=False)
    claim_type = Column(String(20), nullable=False, default='parts_and_labor')

    labor_cost = Column(Float, nullable=False, default=0)
    parts_cost = Column(Float, nullable=False, default=0)

    status = Column(String(20), nullable=False, default='open')
    denied_reason = Column(Text, nullable=True)
    resolution = Column(Text, nullable=True)

    claimed_date = Column(Date, nullable=False)
    resolved_date = Column(Date, nullable=True)

    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    warranty = relationship('Warranty', back_populates='claims')
    job = relationship('Job', foreign_keys=[job_id], overlaps='warranty_claims')
    creator = relationship('User', foreign_keys=[created_by])

    @property
    def total_cost(self):
        return float(self.labor_cost or 0) + float(self.parts_cost or 0)

    @property
    def status_display(self):
        return dict(CLAIM_STATUSES).get(self.status, self.status)

    @property
    def status_color(self):
        return CLAIM_STATUS_COLORS.get(self.status, 'secondary')

    @property
    def type_display(self):
        return dict(CLAIM_TYPES).get(self.claim_type, self.claim_type)
