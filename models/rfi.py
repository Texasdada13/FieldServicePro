"""RFI (Request for Information) model."""
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, Float, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


RFI_STATUSES = [
    ('draft', 'Draft'), ('open', 'Open'), ('pending_response', 'Pending Response'),
    ('answered', 'Answered'), ('closed', 'Closed'), ('void', 'Void'),
]

RFI_PRIORITIES = [
    ('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('critical', 'Critical'),
]

RFI_IMPACT_TYPES = [
    ('none', 'None'), ('potential', 'Potential'), ('confirmed', 'Confirmed'),
]

STATUS_COLORS = {
    'draft': 'secondary', 'open': 'accent', 'pending_response': 'info',
    'answered': 'success', 'closed': 'secondary', 'void': 'secondary',
}

PRIORITY_COLORS = {
    'low': 'secondary', 'normal': 'accent', 'high': 'warning', 'critical': 'danger',
}


class RFI(Base):
    __tablename__ = 'rfis'

    id = Column(Integer, primary_key=True)
    rfi_number = Column(String(20), nullable=False)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=True)
    phase_id = Column(Integer, ForeignKey('job_phases.id'), nullable=True)

    subject = Column(String(255), nullable=False)
    question = Column(Text, nullable=False)
    context = Column(Text, nullable=True)
    reference = Column(String(255), nullable=True)

    # Routing
    submitted_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    assigned_to_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    directed_to = Column(String(255), nullable=True)
    directed_to_email = Column(String(255), nullable=True)

    # Response
    response = Column(Text, nullable=True)
    responded_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    responded_by_external = Column(String(255), nullable=True)
    response_date = Column(DateTime, nullable=True)

    # Status & Dates
    status = Column(String(20), nullable=False, default='draft')
    priority = Column(String(10), nullable=False, default='normal')
    date_submitted = Column(Date, nullable=False, default=date.today)
    date_required = Column(Date, nullable=True)

    # Impact
    cost_impact = Column(String(20), nullable=False, default='none')
    cost_impact_amount = Column(Float, nullable=True)
    schedule_impact = Column(String(20), nullable=False, default='none')
    schedule_impact_days = Column(Integer, nullable=True)
    related_change_order_id = Column(Integer, ForeignKey('change_orders.id'), nullable=True)

    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship('Project', backref='rfis')
    job = relationship('Job', backref='rfis')
    phase = relationship('JobPhase', foreign_keys=[phase_id])
    submitted_by = relationship('User', foreign_keys=[submitted_by_id])
    assigned_to = relationship('User', foreign_keys=[assigned_to_id])
    responded_by = relationship('User', foreign_keys=[responded_by_id])
    related_change_order = relationship('ChangeOrder', foreign_keys=[related_change_order_id])

    @property
    def days_open(self):
        if self.status in ('answered', 'closed') and self.response_date:
            rd = self.response_date.date() if hasattr(self.response_date, 'date') else self.response_date
            return (rd - self.date_submitted).days
        return (date.today() - self.date_submitted).days

    @property
    def is_overdue(self):
        if self.status in ('answered', 'closed', 'void'):
            return False
        if self.date_required:
            return date.today() > self.date_required
        return False

    @property
    def status_color(self):
        return STATUS_COLORS.get(self.status, 'secondary')

    @property
    def priority_color(self):
        return PRIORITY_COLORS.get(self.priority, 'secondary')

    @staticmethod
    def next_number(db, project_id):
        count = db.query(RFI).filter_by(project_id=project_id).count()
        return f"RFI-{count + 1:03d}"

    def to_dict(self):
        return {
            'id': self.id, 'rfi_number': self.rfi_number,
            'project_id': self.project_id, 'subject': self.subject,
            'status': self.status, 'priority': self.priority,
            'days_open': self.days_open, 'is_overdue': self.is_overdue,
            'date_submitted': self.date_submitted.isoformat() if self.date_submitted else None,
        }
