"""Recurring Schedule & Preventive Maintenance models."""
import json
from datetime import date, datetime, timedelta
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Date, DateTime,
    Float, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from .database import Base


FREQUENCY_CHOICES = [
    ('weekly', 'Weekly'), ('biweekly', 'Every 2 Weeks'),
    ('monthly', 'Monthly'), ('quarterly', 'Quarterly'),
    ('semi_annual', 'Semi-Annual'), ('annual', 'Annual'),
    ('custom', 'Custom Interval'),
]

DAY_OF_WEEK_CHOICES = [
    ('monday', 'Monday'), ('tuesday', 'Tuesday'), ('wednesday', 'Wednesday'),
    ('thursday', 'Thursday'), ('friday', 'Friday'),
    ('saturday', 'Saturday'), ('sunday', 'Sunday'),
]

SCHEDULE_STATUS_CHOICES = [
    ('active', 'Active'), ('paused', 'Paused'),
    ('completed', 'Completed'), ('cancelled', 'Cancelled'),
]

SCHEDULE_STATUS_COLORS = {
    'active': 'success', 'paused': 'warning',
    'completed': 'secondary', 'cancelled': 'danger',
}


class RecurringSchedule(Base):
    __tablename__ = 'recurring_schedules'

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    schedule_number = Column(String(20), unique=True, nullable=False, index=True)

    # Identity
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)

    # Relationships
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    property_id = Column(Integer, ForeignKey('properties.id'), nullable=True)
    contract_id = Column(Integer, ForeignKey('contracts.id'), nullable=True)
    contract_line_item_id = Column(Integer, ForeignKey('contract_line_items.id'), nullable=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)

    # Job template fields
    job_type = Column(String(50), nullable=False, default='maintenance')
    division_id = Column(Integer, ForeignKey('divisions.id'), nullable=True)
    trade = Column(String(20), nullable=True)
    default_description = Column(Text, nullable=True)
    default_priority = Column(String(20), nullable=False, default='normal')
    estimated_duration_hours = Column(Float, nullable=True)
    estimated_amount = Column(Float, nullable=True)
    default_technician_id = Column(Integer, ForeignKey('technicians.id'), nullable=True)
    requires_parts = Column(Text, nullable=True)  # JSON string
    checklist_template_id = Column(Integer, ForeignKey('checklist_templates.id'), nullable=True)

    # Schedule fields
    frequency = Column(String(20), nullable=False, default='annual')
    custom_interval_days = Column(Integer, nullable=True)
    preferred_day_of_week = Column(String(10), nullable=True)
    preferred_time = Column(String(20), nullable=True)  # morning, afternoon, 09:00
    seasonal_months = Column(Text, nullable=True)  # JSON: [3,4,5,9,10,11]
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=True)
    next_due_date = Column(Date, nullable=False)
    last_generated_date = Column(Date, nullable=True)
    last_generated_job_id = Column(Integer, ForeignKey('jobs.id'), nullable=True)

    # Control fields
    is_active = Column(Boolean, default=True, nullable=False)
    auto_generate = Column(Boolean, default=True, nullable=False)
    auto_assign = Column(Boolean, default=True, nullable=False)
    auto_schedule = Column(Boolean, default=False, nullable=False)
    advance_generation_days = Column(Integer, default=14, nullable=False)
    status = Column(String(20), nullable=False, default='active')
    pause_reason = Column(Text, nullable=True)
    pause_until = Column(Date, nullable=True)

    # Tracking
    total_jobs_generated = Column(Integer, default=0, nullable=False)
    total_value_generated = Column(Float, default=0, nullable=False)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ORM relationships
    client = relationship('Client', back_populates='recurring_schedules')
    property_rel = relationship('Property', foreign_keys=[property_id])
    contract = relationship('Contract', foreign_keys=[contract_id])
    contract_line_item = relationship('ContractLineItem', foreign_keys=[contract_line_item_id])
    project = relationship('Project', foreign_keys=[project_id])
    division = relationship('Division', foreign_keys=[division_id])
    default_technician = relationship('Technician', foreign_keys=[default_technician_id])
    checklist_template = relationship('ChecklistTemplate', foreign_keys=[checklist_template_id])
    last_generated_job = relationship('Job', foreign_keys=[last_generated_job_id])
    creator = relationship('User', foreign_keys=[created_by])

    __table_args__ = (
        Index('ix_recurring_org', 'organization_id'),
        Index('ix_recurring_client', 'client_id'),
        Index('ix_recurring_next_due', 'next_due_date'),
        Index('ix_recurring_status', 'status'),
    )

    @property
    def frequency_display(self):
        if self.frequency == 'custom':
            return f'Every {self.custom_interval_days or 30} Days'
        return dict(FREQUENCY_CHOICES).get(self.frequency, self.frequency)

    @property
    def seasonal_months_list(self):
        """Parse seasonal_months JSON into a list of ints."""
        if self.seasonal_months:
            try:
                return json.loads(self.seasonal_months)
            except (json.JSONDecodeError, TypeError):
                pass
        return []

    @property
    def requires_parts_list(self):
        """Parse requires_parts JSON into a list."""
        if self.requires_parts:
            try:
                return json.loads(self.requires_parts)
            except (json.JSONDecodeError, TypeError):
                return [self.requires_parts]
        return []

    @property
    def status_display(self):
        return dict(SCHEDULE_STATUS_CHOICES).get(self.status, self.status)

    @property
    def status_color(self):
        return SCHEDULE_STATUS_COLORS.get(self.status, 'secondary')

    @property
    def days_until_due(self):
        return (self.next_due_date - date.today()).days

    @property
    def is_overdue(self):
        return self.next_due_date < date.today()

    @property
    def is_due_for_generation(self):
        if not self.is_active or self.status != 'active':
            return False
        if self.end_date and date.today() > self.end_date:
            return False
        if self.pause_until and date.today() <= self.pause_until:
            return False
        return self.days_until_due <= self.advance_generation_days

    def calculate_next_due_date(self, from_date=None):
        """Calculate the next due date after a job is generated."""
        from dateutil.relativedelta import relativedelta

        base = from_date or self.next_due_date or date.today()

        interval_map = {
            'weekly': relativedelta(weeks=1),
            'biweekly': relativedelta(weeks=2),
            'monthly': relativedelta(months=1),
            'quarterly': relativedelta(months=3),
            'semi_annual': relativedelta(months=6),
            'annual': relativedelta(years=1),
        }

        if self.frequency == 'custom':
            next_date = base + timedelta(days=self.custom_interval_days or 30)
        else:
            next_date = base + interval_map.get(self.frequency, relativedelta(years=1))

        # Honour seasonal_months
        if self.seasonal_months:
            try:
                valid_months = json.loads(self.seasonal_months)
                if valid_months:
                    attempts = 0
                    while next_date.month not in valid_months and attempts < 24:
                        next_date = next_date + relativedelta(months=1)
                        attempts += 1
            except (json.JSONDecodeError, TypeError):
                pass

        # Snap to preferred_day_of_week
        if self.preferred_day_of_week:
            target_day = {
                'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3,
                'friday': 4, 'saturday': 5, 'sunday': 6,
            }.get(self.preferred_day_of_week)
            if target_day is not None:
                days_ahead = (target_day - next_date.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                next_date = next_date + timedelta(days=days_ahead)

        return next_date

    def to_dict(self):
        return {
            'id': self.id,
            'schedule_number': self.schedule_number,
            'title': self.title,
            'client_id': self.client_id,
            'frequency': self.frequency,
            'frequency_display': self.frequency_display,
            'status': self.status,
            'next_due_date': self.next_due_date.isoformat() if self.next_due_date else None,
            'days_until_due': self.days_until_due,
            'is_overdue': self.is_overdue,
            'total_jobs_generated': self.total_jobs_generated,
            'is_active': self.is_active,
        }


class RecurringJobLog(Base):
    """Audit trail — one row per generated job."""
    __tablename__ = 'recurring_job_logs'

    id = Column(Integer, primary_key=True)
    schedule_id = Column(Integer, ForeignKey('recurring_schedules.id'), nullable=False)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    due_date = Column(Date, nullable=False)
    generation_method = Column(String(30), nullable=False, default='auto')  # auto | manual | cli
    generated_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    notes = Column(Text, nullable=True)
    success = Column(Boolean, default=True, nullable=False)
    error_message = Column(Text, nullable=True)

    schedule = relationship('RecurringSchedule', foreign_keys=[schedule_id], backref='job_logs')
    job = relationship('Job', foreign_keys=[job_id])
    user = relationship('User', foreign_keys=[generated_by])
