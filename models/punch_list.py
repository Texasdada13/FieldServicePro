"""Punch List and Punch List Item models."""
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


PUNCH_LIST_STATUSES = [
    ('draft', 'Draft'), ('active', 'Active'), ('in_progress', 'In Progress'),
    ('completed', 'Completed'), ('accepted', 'Accepted'),
]

ITEM_CATEGORIES = [
    ('cosmetic', 'Cosmetic'), ('functional', 'Functional'), ('safety', 'Safety'),
    ('incomplete', 'Incomplete'), ('damage', 'Damage'),
    ('code_violation', 'Code Violation'), ('other', 'Other'),
]

ITEM_SEVERITIES = [
    ('minor', 'Minor'), ('moderate', 'Moderate'), ('major', 'Major'), ('critical', 'Critical'),
]

ITEM_TRADES = [
    ('plumbing', 'Plumbing'), ('hvac', 'HVAC'), ('electrical', 'Electrical'),
    ('general', 'General'), ('painting', 'Painting'), ('flooring', 'Flooring'), ('other', 'Other'),
]

ITEM_STATUSES = [
    ('open', 'Open'), ('assigned', 'Assigned'), ('in_progress', 'In Progress'),
    ('completed', 'Completed'), ('verified', 'Verified'),
    ('rejected', 'Rejected'), ('deferred', 'Deferred'),
]

SEVERITY_COLORS = {
    'minor': 'secondary', 'moderate': 'warning', 'major': 'danger', 'critical': 'danger',
}

ITEM_STATUS_COLORS = {
    'open': 'secondary', 'assigned': 'info', 'in_progress': 'accent',
    'completed': 'success', 'verified': 'success',
    'rejected': 'danger', 'deferred': 'warning',
}


class PunchList(Base):
    __tablename__ = 'punch_lists'

    id = Column(Integer, primary_key=True)
    punch_list_number = Column(String(20), nullable=False)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False, index=True)

    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    inspection_date = Column(Date, nullable=False, default=date.today)
    inspected_by = Column(String(255), nullable=True)
    status = Column(String(20), nullable=False, default='draft')
    due_date = Column(Date, nullable=True)
    accepted_by = Column(String(255), nullable=True)
    accepted_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)

    created_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship('Project', backref='punch_lists')
    created_by = relationship('User', foreign_keys=[created_by_id])
    items = relationship('PunchListItem', back_populates='punch_list',
                         cascade='all, delete-orphan', order_by='PunchListItem.sort_order')

    @property
    def total_items(self):
        return len(self.items) if self.items else 0

    @property
    def completed_items(self):
        return len([i for i in (self.items or []) if i.status == 'verified'])

    @property
    def percent_complete(self):
        total = self.total_items
        if total == 0:
            return 0
        return round((self.completed_items / total) * 100)

    @property
    def has_critical_open(self):
        return any(i.severity == 'critical' and i.status not in ('verified', 'deferred')
                   for i in (self.items or []))

    @property
    def status_color(self):
        return {'draft': 'secondary', 'active': 'accent', 'in_progress': 'info',
                'completed': 'success', 'accepted': 'success'}.get(self.status, 'secondary')

    @staticmethod
    def next_number(db):
        from sqlalchemy import func
        year = date.today().year
        count = db.query(func.count(PunchList.id)).filter(
            PunchList.punch_list_number.like(f'PL-{year}-%')
        ).scalar() or 0
        return f"PL-{year}-{count + 1:04d}"

    def to_dict(self):
        return {
            'id': self.id, 'punch_list_number': self.punch_list_number,
            'project_id': self.project_id, 'title': self.title,
            'status': self.status, 'total_items': self.total_items,
            'completed_items': self.completed_items,
            'percent_complete': self.percent_complete,
        }


class PunchListItem(Base):
    __tablename__ = 'punch_list_items'

    id = Column(Integer, primary_key=True)
    punch_list_id = Column(Integer, ForeignKey('punch_lists.id', ondelete='CASCADE'), nullable=False)
    item_number = Column(Integer, nullable=False)
    location = Column(String(255), nullable=True)
    description = Column(String(500), nullable=False)
    category = Column(String(20), nullable=False, default='other')
    severity = Column(String(10), nullable=False, default='minor')
    trade = Column(String(20), nullable=False, default='general')
    status = Column(String(20), nullable=False, default='open')

    assigned_to_id = Column(Integer, ForeignKey('technicians.id'), nullable=True)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=True)
    photo_before_id = Column(Integer, ForeignKey('documents.id'), nullable=True)
    photo_after_id = Column(Integer, ForeignKey('documents.id'), nullable=True)
    notes = Column(Text, nullable=True)
    completed_date = Column(Date, nullable=True)
    verified_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    verified_date = Column(Date, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    punch_list = relationship('PunchList', back_populates='items')
    assigned_to = relationship('Technician', foreign_keys=[assigned_to_id])
    job = relationship('Job', foreign_keys=[job_id])
    photo_before = relationship('Document', foreign_keys=[photo_before_id])
    photo_after = relationship('Document', foreign_keys=[photo_after_id])
    verified_by = relationship('User', foreign_keys=[verified_by_id])

    @property
    def status_color(self):
        return ITEM_STATUS_COLORS.get(self.status, 'secondary')

    @property
    def severity_color(self):
        return SEVERITY_COLORS.get(self.severity, 'secondary')

    def to_dict(self):
        return {
            'id': self.id, 'item_number': self.item_number,
            'description': self.description, 'location': self.location,
            'category': self.category, 'severity': self.severity,
            'trade': self.trade, 'status': self.status,
        }
