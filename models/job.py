"""Job / Work Order model."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
import enum
from .database import Base


class JobStatus(enum.Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    COMPLETED = "completed"
    INVOICED = "invoiced"
    CANCELLED = "cancelled"


class Job(Base):
    __tablename__ = 'jobs'

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    division_id = Column(Integer, ForeignKey('divisions.id'), nullable=False)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    property_id = Column(Integer, ForeignKey('properties.id'))
    quote_id = Column(Integer, ForeignKey('quotes.id'))

    # Job details
    job_number = Column(String(50), unique=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(20), default=JobStatus.DRAFT.value, index=True)
    priority = Column(String(20), default='normal')  # low, normal, high, urgent

    # Scheduling
    scheduled_date = Column(DateTime)
    scheduled_end = Column(DateTime)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)

    # Assignment
    assigned_technician_id = Column(Integer, ForeignKey('technicians.id'))

    # Financial
    estimated_amount = Column(Float, default=0)
    actual_amount = Column(Float, default=0)

    # Job type
    job_type = Column(String(50))  # service_call, maintenance, installation, repair, inspection, emergency

    # Tracking
    created_by_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    division = relationship("Division", back_populates="jobs")
    client = relationship("Client", back_populates="jobs")
    property = relationship("Property", back_populates="jobs")
    quote = relationship("Quote", foreign_keys=[quote_id])
    technician = relationship("Technician", back_populates="jobs")
    notes = relationship("JobNote", back_populates="job", cascade="all, delete-orphan")
    invoices = relationship("Invoice", back_populates="job")

    def to_dict(self):
        return {
            'id': self.id,
            'job_number': self.job_number,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'priority': self.priority,
            'division_id': self.division_id,
            'client_id': self.client_id,
            'property_id': self.property_id,
            'job_type': self.job_type,
            'scheduled_date': self.scheduled_date.isoformat() if self.scheduled_date else None,
            'scheduled_end': self.scheduled_end.isoformat() if self.scheduled_end else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'assigned_technician_id': self.assigned_technician_id,
            'estimated_amount': self.estimated_amount,
            'actual_amount': self.actual_amount,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class JobNote(Base):
    __tablename__ = 'job_notes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'))
    content = Column(Text, nullable=False)
    note_type = Column(String(20), default='note')  # note, status_change, photo, internal
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("Job", back_populates="notes")

    def to_dict(self):
        return {
            'id': self.id,
            'job_id': self.job_id,
            'content': self.content,
            'note_type': self.note_type,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
