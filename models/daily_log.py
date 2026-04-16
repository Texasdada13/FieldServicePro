"""Daily Log model — daily field reports for projects."""
import json
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, Float, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from .database import Base


WEATHER_IMPACTS = [
    ('none', 'None'), ('minor_delay', 'Minor Delay'),
    ('major_delay', 'Major Delay'), ('work_stopped', 'Work Stopped'),
]

DAILY_LOG_STATUSES = [
    ('draft', 'Draft'), ('submitted', 'Submitted'), ('reviewed', 'Reviewed'),
]

STATUS_COLORS = {
    'draft': 'secondary', 'submitted': 'accent', 'reviewed': 'success',
}


class DailyLog(Base):
    __tablename__ = 'daily_logs'
    __table_args__ = (
        UniqueConstraint('project_id', 'log_date', name='uq_daily_log_project_date'),
    )

    id = Column(Integer, primary_key=True)
    log_number = Column(String(20), nullable=False)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=False, index=True)
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=True)
    log_date = Column(Date, nullable=False, default=date.today)
    reported_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)

    # Conditions
    weather = Column(String(255), nullable=True)
    temperature_high = Column(Integer, nullable=True)
    temperature_low = Column(Integer, nullable=True)
    weather_impact = Column(String(20), nullable=False, default='none')
    site_conditions = Column(Text, nullable=True)

    # Workforce (JSON)
    crew_on_site = Column(Text, nullable=True)
    subcontractors_on_site = Column(Text, nullable=True)
    total_workers = Column(Integer, default=0)
    hours_worked = Column(Float, default=0)

    # Work
    work_description = Column(Text, nullable=False, default='')
    areas_worked = Column(Text, nullable=True)
    milestones_reached = Column(Text, nullable=True)

    # Materials & Equipment
    materials_received = Column(Text, nullable=True)
    equipment_on_site = Column(Text, nullable=True)

    # Issues
    delays = Column(Text, nullable=True)
    safety_incidents = Column(Text, nullable=True)
    visitor_log = Column(Text, nullable=True)
    issues_or_concerns = Column(Text, nullable=True)

    # Status
    status = Column(String(20), nullable=False, default='draft')
    reviewed_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    project = relationship('Project', backref='daily_logs')
    job = relationship('Job', backref='daily_logs')
    reported_by = relationship('User', foreign_keys=[reported_by_id])
    reviewed_by = relationship('User', foreign_keys=[reviewed_by_id])

    @property
    def crew_list(self):
        if self.crew_on_site:
            try:
                return json.loads(self.crew_on_site)
            except (json.JSONDecodeError, TypeError):
                return []
        return []

    @crew_list.setter
    def crew_list(self, value):
        self.crew_on_site = json.dumps(value) if value else None

    @property
    def is_late_entry(self):
        return (date.today() - self.log_date).days > 2

    @property
    def status_color(self):
        return STATUS_COLORS.get(self.status, 'secondary')

    @staticmethod
    def next_number(db, project_id):
        count = db.query(DailyLog).filter_by(project_id=project_id).count()
        return f"DL-{count + 1:03d}"

    def to_dict(self):
        return {
            'id': self.id, 'log_number': self.log_number,
            'project_id': self.project_id,
            'log_date': self.log_date.isoformat() if self.log_date else None,
            'status': self.status, 'weather': self.weather,
            'total_workers': self.total_workers,
            'work_description': (self.work_description or '')[:200],
        }
