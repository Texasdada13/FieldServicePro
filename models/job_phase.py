"""Job Phase model — multi-phase job management."""

from datetime import datetime
import enum
import json
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, Date, DateTime,
    ForeignKey, UniqueConstraint
)
from sqlalchemy.orm import relationship
from .database import Base


class PhaseStatus(str, enum.Enum):
    not_started = "not_started"
    scheduled   = "scheduled"
    in_progress = "in_progress"
    on_hold     = "on_hold"
    completed   = "completed"
    skipped     = "skipped"


class InspectionStatus(str, enum.Enum):
    not_required = "not_required"
    pending      = "pending"
    passed       = "passed"
    failed       = "failed"


class JobPhase(Base):
    __tablename__ = 'job_phases'
    __table_args__ = (
        UniqueConstraint('job_id', 'phase_number', name='uq_job_phase_number'),
    )

    id                     = Column(Integer, primary_key=True)
    job_id                 = Column(Integer, ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, index=True)
    phase_number           = Column(Integer, nullable=False)
    title                  = Column(String(200), nullable=False)
    description            = Column(Text, nullable=True)
    status                 = Column(String(20), default=PhaseStatus.not_started.value, nullable=False)

    # Scheduling
    scheduled_start_date   = Column(Date, nullable=True)
    scheduled_end_date     = Column(Date, nullable=True)
    actual_start_date      = Column(Date, nullable=True)
    actual_end_date        = Column(Date, nullable=True)

    # Assignment
    assigned_technician_id = Column(Integer, ForeignKey('technicians.id', ondelete='SET NULL'), nullable=True)

    # Effort & Cost
    estimated_hours        = Column(Float, default=0)
    actual_hours           = Column(Float, default=0)
    estimated_cost         = Column(Float, default=0)
    actual_cost            = Column(Float, default=0)

    # Details
    materials              = Column(Text, nullable=True)
    dependencies           = Column(Text, nullable=True)  # JSON: [phase_id, ...]
    notes                  = Column(Text, nullable=True)
    completion_notes       = Column(Text, nullable=True)

    # Inspection
    requires_inspection    = Column(Boolean, default=False)
    inspection_status      = Column(String(20), default=InspectionStatus.not_required.value, nullable=True)
    inspection_date        = Column(DateTime, nullable=True)
    inspection_notes       = Column(Text, nullable=True)

    # Ordering
    sort_order             = Column(Integer, default=0)

    created_at             = Column(DateTime, default=datetime.utcnow)
    updated_at             = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    job                    = relationship('Job', back_populates='phases')
    assigned_technician    = relationship('Technician', foreign_keys=[assigned_technician_id])
    change_orders          = relationship('ChangeOrder', back_populates='phase', lazy='select')

    @property
    def status_label(self):
        labels = {
            'not_started': 'Not Started', 'scheduled': 'Scheduled',
            'in_progress': 'In Progress', 'on_hold': 'On Hold',
            'completed': 'Completed', 'skipped': 'Skipped',
        }
        return labels.get(self.status, self.status)

    @property
    def status_badge_class(self):
        classes = {
            'not_started': 'secondary', 'scheduled': 'active',
            'in_progress': 'primary', 'on_hold': 'warning',
            'completed': 'success', 'skipped': 'draft',
        }
        return classes.get(self.status, 'secondary')

    @property
    def is_active(self):
        return self.status in ('scheduled', 'in_progress')

    @property
    def is_complete(self):
        return self.status in ('completed', 'skipped')

    @property
    def inspection_required_and_pending(self):
        return self.requires_inspection and self.inspection_status == 'pending'

    @property
    def dependency_list(self):
        """Parse dependencies JSON into list of phase IDs."""
        if not self.dependencies:
            return []
        try:
            return json.loads(self.dependencies)
        except (json.JSONDecodeError, TypeError):
            return []

    def to_dict(self):
        return {
            'id': self.id,
            'job_id': self.job_id,
            'phase_number': self.phase_number,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'status_label': self.status_label,
            'status_badge_class': self.status_badge_class,
            'scheduled_start_date': self.scheduled_start_date.isoformat() if self.scheduled_start_date else None,
            'scheduled_end_date': self.scheduled_end_date.isoformat() if self.scheduled_end_date else None,
            'actual_start_date': self.actual_start_date.isoformat() if self.actual_start_date else None,
            'actual_end_date': self.actual_end_date.isoformat() if self.actual_end_date else None,
            'assigned_technician_id': self.assigned_technician_id,
            'estimated_hours': float(self.estimated_hours or 0),
            'actual_hours': float(self.actual_hours or 0),
            'estimated_cost': float(self.estimated_cost or 0),
            'actual_cost': float(self.actual_cost or 0),
            'materials': self.materials,
            'dependencies': self.dependency_list,
            'notes': self.notes,
            'completion_notes': self.completion_notes,
            'sort_order': self.sort_order,
            'requires_inspection': self.requires_inspection,
            'inspection_status': self.inspection_status,
            'is_active': self.is_active,
            'is_complete': self.is_complete,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<JobPhase {self.phase_number}: {self.title} [{self.status}]>'
