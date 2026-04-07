"""Safety checklist models."""
import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class ChecklistTemplate(Base):
    __tablename__ = 'checklist_templates'

    id                     = Column(Integer, primary_key=True)
    name                   = Column(String(200), nullable=False)
    description            = Column(Text, nullable=True)
    checklist_type         = Column(String(50), nullable=False, default='pre_job')
    category               = Column(String(50), nullable=False, default='general_safety')
    is_active              = Column(Boolean, default=True)
    required_for_job_types = Column(Text, nullable=True)  # JSON array
    division_id            = Column(Integer, ForeignKey('divisions.id'), nullable=True)
    created_by             = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at             = Column(DateTime, default=datetime.utcnow)
    updated_at             = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items       = relationship('ChecklistItem', backref='template', order_by='ChecklistItem.sort_order', cascade='all, delete-orphan')
    completions = relationship('CompletedChecklist', backref='template', lazy='select')
    division    = relationship('Division', backref='checklist_templates')
    creator     = relationship('User', foreign_keys=[created_by])

    TYPE_CHOICES = [('pre_job', 'Pre-Job'), ('daily', 'Daily'), ('post_job', 'Post-Job'),
                    ('incident', 'Incident Report'), ('inspection', 'Inspection')]
    CATEGORY_CHOICES = [('general_safety', 'General Safety'), ('confined_space', 'Confined Space'),
                        ('hot_work', 'Hot Work'), ('electrical', 'Electrical Safety'),
                        ('excavation', 'Excavation'), ('working_at_heights', 'Working at Heights'),
                        ('hazmat', 'HAZMAT'), ('ppe', 'PPE'), ('environmental', 'Environmental'),
                        ('other', 'Other')]

    @property
    def type_display(self):
        return dict(self.TYPE_CHOICES).get(self.checklist_type, self.checklist_type)

    @property
    def category_display(self):
        return dict(self.CATEGORY_CHOICES).get(self.category, self.category)

    @property
    def required_job_types_list(self):
        if not self.required_for_job_types:
            return []
        try:
            return json.loads(self.required_for_job_types)
        except (json.JSONDecodeError, TypeError):
            return []

    @required_job_types_list.setter
    def required_job_types_list(self, value):
        self.required_for_job_types = json.dumps(value) if isinstance(value, list) else None

    @property
    def item_count(self):
        return len(self.items)

    @property
    def required_item_count(self):
        return sum(1 for i in self.items if i.is_required)

    def to_dict(self):
        return {'id': self.id, 'name': self.name, 'checklist_type': self.checklist_type,
                'category': self.category, 'is_active': self.is_active, 'item_count': self.item_count}


class ChecklistItem(Base):
    __tablename__ = 'checklist_items'

    id             = Column(Integer, primary_key=True)
    template_id    = Column(Integer, ForeignKey('checklist_templates.id'), nullable=False)
    question       = Column(String(500), nullable=False)
    item_type      = Column(String(50), nullable=False, default='yes_no')
    is_required    = Column(Boolean, default=True)
    failure_action = Column(String(50), nullable=False, default='warning')
    help_text      = Column(String(500), nullable=True)
    sort_order     = Column(Integer, default=0)
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    ITEM_TYPES = [('yes_no', 'Yes / No'), ('pass_fail', 'Pass / Fail'), ('text', 'Text Input'),
                  ('number', 'Number'), ('photo', 'Photo Upload'), ('signature', 'Signature')]
    FAILURE_ACTIONS = [('warning', 'Warning Only'), ('block_work', 'Block Work'),
                       ('notify_supervisor', 'Notify Supervisor')]

    @property
    def type_display(self):
        return dict(self.ITEM_TYPES).get(self.item_type, self.item_type)


class CompletedChecklist(Base):
    __tablename__ = 'completed_checklists'

    id                    = Column(Integer, primary_key=True)
    template_id           = Column(Integer, ForeignKey('checklist_templates.id'), nullable=False)
    job_id                = Column(Integer, ForeignKey('jobs.id'), nullable=False)
    phase_id              = Column(Integer, ForeignKey('job_phases.id'), nullable=True)
    completed_by          = Column(Integer, ForeignKey('users.id'), nullable=True)
    completed_at          = Column(DateTime, default=datetime.utcnow)
    location              = Column(String(200), nullable=True)
    weather_conditions    = Column(String(100), nullable=True)
    overall_status        = Column(String(50), nullable=False, default='passed')
    supervisor_reviewed   = Column(Boolean, default=False)
    supervisor_id         = Column(Integer, ForeignKey('users.id'), nullable=True)
    supervisor_reviewed_at = Column(DateTime, nullable=True)
    notes                 = Column(Text, nullable=True)

    items      = relationship('CompletedChecklistItem', backref='completed_checklist',
                              order_by='CompletedChecklistItem.sort_order', cascade='all, delete-orphan')
    job        = relationship('Job', backref='completed_checklists')
    phase      = relationship('JobPhase', backref='completed_checklists')
    completer  = relationship('User', foreign_keys=[completed_by])
    supervisor = relationship('User', foreign_keys=[supervisor_id])

    STATUS_COLORS = {'passed': 'success', 'failed': 'danger', 'passed_with_exceptions': 'warning'}

    @property
    def status_color(self):
        return self.STATUS_COLORS.get(self.overall_status, 'secondary')

    @property
    def status_display(self):
        return self.overall_status.replace('_', ' ').title()


class CompletedChecklistItem(Base):
    __tablename__ = 'completed_checklist_items'

    id                     = Column(Integer, primary_key=True)
    completed_checklist_id = Column(Integer, ForeignKey('completed_checklists.id'), nullable=False)
    checklist_item_id      = Column(Integer, ForeignKey('checklist_items.id'), nullable=False)
    response               = Column(String(500), nullable=True)
    is_compliant           = Column(Boolean, default=True)
    notes                  = Column(Text, nullable=True)
    photo_url              = Column(String(500), nullable=True)
    sort_order             = Column(Integer, default=0)

    template_item = relationship('ChecklistItem')
