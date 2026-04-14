"""Callback tracking model."""
from datetime import date, datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Date, DateTime,
    ForeignKey, Index
)
from sqlalchemy.orm import relationship
from .database import Base


CALLBACK_REASONS = [
    ('incomplete_repair', 'Incomplete Repair'), ('recurring_issue', 'Recurring Issue'),
    ('customer_complaint', 'Customer Complaint'), ('quality_issue', 'Quality Issue'),
    ('missed_scope', 'Missed Scope'), ('equipment_failure', 'Equipment Failure'),
    ('installation_defect', 'Installation Defect'), ('other', 'Other'),
]

CALLBACK_SEVERITIES = [
    ('minor', 'Minor'), ('moderate', 'Moderate'),
    ('major', 'Major'), ('critical', 'Critical'),
]

CALLBACK_STATUSES = [
    ('reported', 'Reported'), ('investigating', 'Investigating'),
    ('in_progress', 'In Progress'), ('resolved', 'Resolved'), ('closed', 'Closed'),
]

CALLBACK_STATUS_COLORS = {
    'reported': 'warning', 'investigating': 'info',
    'in_progress': 'accent', 'resolved': 'success', 'closed': 'secondary',
}

SEVERITY_COLORS = {
    'minor': 'secondary', 'moderate': 'warning', 'major': 'danger', 'critical': 'danger',
}


class Callback(Base):
    __tablename__ = 'callbacks'

    id = Column(Integer, primary_key=True)
    callback_number = Column(String(20), unique=True, nullable=False, index=True)

    # Job links
    original_job_id = Column(Integer, ForeignKey('jobs.id'), nullable=False)
    callback_job_id = Column(Integer, ForeignKey('jobs.id'), nullable=False)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)

    # Classification
    reason = Column(String(30), nullable=False, default='other')
    description = Column(Text, nullable=False)
    severity = Column(String(10), nullable=False, default='minor')

    # Warranty linkage
    is_warranty = Column(Boolean, default=False, nullable=False)
    warranty_id = Column(Integer, ForeignKey('warranties.id'), nullable=True)
    warranty_claim_id = Column(Integer, ForeignKey('warranty_claims.id'), nullable=True)

    # Billing
    is_billable = Column(Boolean, default=False, nullable=False)

    # Root cause / corrective action
    root_cause = Column(Text, nullable=True)
    corrective_action = Column(Text, nullable=True)

    # Responsibility
    responsible_technician_id = Column(Integer, ForeignKey('technicians.id'), nullable=True)

    # Status
    status = Column(String(20), nullable=False, default='reported')
    reported_date = Column(Date, nullable=False, default=date.today)
    resolved_date = Column(Date, nullable=True)

    # Notes
    customer_impact = Column(Text, nullable=True)
    internal_notes = Column(Text, nullable=True)

    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    original_job = relationship('Job', foreign_keys=[original_job_id], back_populates='originated_callbacks')
    callback_job = relationship('Job', foreign_keys=[callback_job_id], back_populates='callback_record')
    client = relationship('Client', back_populates='callbacks')
    warranty = relationship('Warranty')
    warranty_claim = relationship('WarrantyClaim')
    responsible_technician = relationship('Technician', foreign_keys=[responsible_technician_id])
    creator = relationship('User', foreign_keys=[created_by])

    __table_args__ = (
        Index('ix_callback_client', 'client_id'),
        Index('ix_callback_status', 'status'),
    )

    @property
    def reason_display(self):
        return dict(CALLBACK_REASONS).get(self.reason, self.reason)

    @property
    def severity_display(self):
        return dict(CALLBACK_SEVERITIES).get(self.severity, self.severity)

    @property
    def severity_color(self):
        return SEVERITY_COLORS.get(self.severity, 'secondary')

    @property
    def status_display(self):
        return dict(CALLBACK_STATUSES).get(self.status, self.status)

    @property
    def status_color(self):
        return CALLBACK_STATUS_COLORS.get(self.status, 'secondary')

    @property
    def is_open(self):
        return self.status not in ('resolved', 'closed')

    def to_dict(self):
        return {
            'id': self.id,
            'callback_number': self.callback_number,
            'reason': self.reason,
            'severity': self.severity,
            'status': self.status,
            'is_warranty': self.is_warranty,
            'reported_date': self.reported_date.isoformat() if self.reported_date else None,
        }
