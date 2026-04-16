"""Submittal model — product data, shop drawings, samples for approval."""
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, Float, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


SUBMITTAL_TYPES = [
    ('product_data', 'Product Data'), ('shop_drawing', 'Shop Drawing'),
    ('sample', 'Sample'), ('mock_up', 'Mock-Up'), ('test_report', 'Test Report'),
    ('certification', 'Certification'), ('warranty_info', 'Warranty Info'),
    ('operation_manual', 'O&M Manual'), ('other', 'Other'),
]

SUBMITTAL_STATUSES = [
    ('draft', 'Draft'), ('submitted', 'Submitted'), ('under_review', 'Under Review'),
    ('approved', 'Approved'), ('approved_as_noted', 'Approved as Noted'),
    ('revise_and_resubmit', 'Revise & Resubmit'), ('rejected', 'Rejected'), ('void', 'Void'),
]

STATUS_COLORS = {
    'draft': 'secondary', 'submitted': 'accent', 'under_review': 'info',
    'approved': 'success', 'approved_as_noted': 'success',
    'revise_and_resubmit': 'warning', 'rejected': 'danger', 'void': 'secondary',
}


class Submittal(Base):
    __tablename__ = 'submittals'

    id = Column(Integer, primary_key=True)
    submittal_number = Column(String(20), nullable=False)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=True)
    phase_id = Column(Integer, ForeignKey('job_phases.id'), nullable=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    spec_section = Column(String(100), nullable=True)
    submittal_type = Column(String(30), nullable=False, default='product_data')

    # Product Info
    manufacturer = Column(String(255), nullable=True)
    model_number = Column(String(255), nullable=True)
    product_description = Column(Text, nullable=True)
    quantity = Column(Integer, nullable=True)
    unit_cost = Column(Float, nullable=True)
    total_cost = Column(Float, nullable=True)
    alternatives_considered = Column(Text, nullable=True)

    # Routing
    submitted_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    submitted_to = Column(String(255), nullable=True)
    submitted_to_email = Column(String(255), nullable=True)
    reviewer_name = Column(String(255), nullable=True)

    # Status
    status = Column(String(30), nullable=False, default='draft')
    review_comments = Column(Text, nullable=True)
    revision_number = Column(Integer, nullable=False, default=1)
    previous_submittal_id = Column(Integer, ForeignKey('submittals.id'), nullable=True)

    # Dates
    date_submitted = Column(Date, nullable=False, default=date.today)
    date_required = Column(Date, nullable=True)
    date_reviewed = Column(Date, nullable=True)

    # Logistics
    lead_time_days = Column(Integer, nullable=True)
    delivery_date = Column(Date, nullable=True)

    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship('Project', backref='submittals')
    job = relationship('Job', backref='submittals')
    phase = relationship('JobPhase', foreign_keys=[phase_id])
    submitted_by = relationship('User', foreign_keys=[submitted_by_id])
    previous_submittal = relationship('Submittal', remote_side=[id], backref='revisions')

    @property
    def days_in_review(self):
        if self.date_reviewed:
            return (self.date_reviewed - self.date_submitted).days
        return (date.today() - self.date_submitted).days

    @property
    def is_overdue(self):
        if self.status in ('approved', 'approved_as_noted', 'rejected', 'void', 'draft'):
            return False
        if self.date_required:
            return date.today() > self.date_required
        return False

    @property
    def status_color(self):
        return STATUS_COLORS.get(self.status, 'secondary')

    @staticmethod
    def next_number(db, project_id):
        count = db.query(Submittal).filter_by(project_id=project_id).count()
        return f"SUB-{count + 1:03d}"

    def to_dict(self):
        return {
            'id': self.id, 'submittal_number': self.submittal_number,
            'project_id': self.project_id, 'title': self.title,
            'status': self.status, 'submittal_type': self.submittal_type,
            'revision_number': self.revision_number,
            'days_in_review': self.days_in_review, 'is_overdue': self.is_overdue,
        }
