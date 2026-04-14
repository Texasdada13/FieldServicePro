"""Customer Communication Log models."""
from datetime import date, datetime
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, Date,
    ForeignKey, Index, JSON
)
from sqlalchemy.orm import relationship
from .database import Base


COMM_TYPES = [
    ('phone_inbound', 'Phone (Inbound)'), ('phone_outbound', 'Phone (Outbound)'),
    ('email_inbound', 'Email (Inbound)'), ('email_outbound', 'Email (Outbound)'),
    ('text_inbound', 'Text (Inbound)'), ('text_outbound', 'Text (Outbound)'),
    ('in_person', 'In-Person Meeting'), ('site_visit', 'Site Visit'),
    ('video_call', 'Video Call'), ('voicemail', 'Voicemail'),
    ('letter', 'Letter'), ('other', 'Other'),
]

COMM_DIRECTIONS = [('inbound', 'Inbound'), ('outbound', 'Outbound')]

COMM_PRIORITIES = [
    ('low', 'Low'), ('normal', 'Normal'), ('high', 'High'), ('urgent', 'Urgent'),
]

COMM_SENTIMENTS = [
    ('positive', 'Positive'), ('neutral', 'Neutral'),
    ('negative', 'Negative'), ('escalation', 'Escalation'),
]

PRIORITY_COLORS = {
    'low': 'secondary', 'normal': 'info', 'high': 'warning', 'urgent': 'danger',
}

SENTIMENT_COLORS = {
    'positive': 'success', 'neutral': 'secondary', 'negative': 'warning', 'escalation': 'danger',
}

TYPE_ICONS = {
    'phone_inbound': 'bi-telephone-inbound', 'phone_outbound': 'bi-telephone-outbound',
    'email_inbound': 'bi-envelope-arrow-down', 'email_outbound': 'bi-envelope-arrow-up',
    'text_inbound': 'bi-chat-left-text', 'text_outbound': 'bi-chat-right-text',
    'in_person': 'bi-people', 'site_visit': 'bi-geo-alt',
    'video_call': 'bi-camera-video', 'voicemail': 'bi-voicemail',
    'letter': 'bi-mailbox', 'other': 'bi-three-dots',
}

DIRECTION_MAP = {
    'phone_inbound': 'inbound', 'phone_outbound': 'outbound',
    'email_inbound': 'inbound', 'email_outbound': 'outbound',
    'text_inbound': 'inbound', 'text_outbound': 'outbound',
    'voicemail': 'inbound',
}


class CommunicationLog(Base):
    __tablename__ = 'communication_logs'

    id = Column(Integer, primary_key=True)
    log_number = Column(String(20), unique=True, nullable=False, index=True)

    # Core
    communication_type = Column(String(20), nullable=False)
    direction = Column(String(10), nullable=True)
    subject = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    outcome = Column(Text, nullable=True)

    # Follow-up
    follow_up_required = Column(Boolean, default=False, nullable=False)
    follow_up_date = Column(Date, nullable=True)
    follow_up_notes = Column(Text, nullable=True)
    follow_up_completed = Column(Boolean, default=False, nullable=False)
    follow_up_completed_date = Column(Date, nullable=True)
    follow_up_completed_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)

    # Client (required)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False, index=True)

    # Contact info
    contact_name = Column(String(150), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    contact_email = Column(String(150), nullable=True)

    # Optional entity links
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=True, index=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)
    quote_id = Column(Integer, ForeignKey('quotes.id'), nullable=True)
    invoice_id = Column(Integer, ForeignKey('invoices.id'), nullable=True)
    warranty_id = Column(Integer, ForeignKey('warranties.id'), nullable=True)
    service_request_id = Column(Integer, ForeignKey('service_requests.id'), nullable=True)

    # Metadata
    duration_minutes = Column(Integer, nullable=True)
    priority = Column(String(10), nullable=False, default='normal')
    sentiment = Column(String(12), nullable=True)
    is_escalation = Column(Boolean, default=False, nullable=False)
    escalated_to_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    tags = Column(JSON, nullable=True)

    # Who + when
    logged_by_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    communication_date = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    client = relationship('Client', foreign_keys=[client_id])
    job = relationship('Job', foreign_keys=[job_id])
    project = relationship('Project', foreign_keys=[project_id])
    quote = relationship('Quote', foreign_keys=[quote_id])
    invoice = relationship('Invoice', foreign_keys=[invoice_id])
    warranty = relationship('Warranty', foreign_keys=[warranty_id])
    service_request = relationship('ServiceRequest', foreign_keys=[service_request_id])
    logged_by = relationship('User', foreign_keys=[logged_by_id])
    escalated_to = relationship('User', foreign_keys=[escalated_to_id])
    follow_up_completed_by = relationship('User', foreign_keys=[follow_up_completed_by_id])

    __table_args__ = (
        Index('ix_comm_log_date', 'communication_date'),
        Index('ix_comm_log_followup', 'follow_up_required', 'follow_up_completed', 'follow_up_date'),
    )

    @property
    def type_display(self):
        return dict(COMM_TYPES).get(self.communication_type, self.communication_type)

    @property
    def type_icon(self):
        return TYPE_ICONS.get(self.communication_type, 'bi-chat')

    @property
    def direction_display(self):
        return (self.direction or '').capitalize() if self.direction else 'N/A'

    @property
    def priority_color(self):
        return PRIORITY_COLORS.get(self.priority, 'secondary')

    @property
    def sentiment_color(self):
        return SENTIMENT_COLORS.get(self.sentiment, '')

    @property
    def is_follow_up_overdue(self):
        if self.follow_up_required and not self.follow_up_completed and self.follow_up_date:
            return self.follow_up_date < date.today()
        return False

    @property
    def related_entity_label(self):
        if self.job:
            return f'Job {self.job.job_number}'
        if self.quote:
            return f'Quote {self.quote.quote_number}'
        if self.invoice:
            return f'Invoice {self.invoice.invoice_number}'
        if self.project:
            return f'Project {self.project.project_number}'
        if self.warranty:
            return f'Warranty {self.warranty.warranty_number}'
        if self.service_request:
            return f'Request {self.service_request.request_number}'
        return ''

    @property
    def tags_list(self):
        if not self.tags:
            return []
        if isinstance(self.tags, list):
            return self.tags
        return [t.strip() for t in str(self.tags).split(',') if t.strip()]

    def to_dict(self):
        return {
            'id': self.id, 'log_number': self.log_number,
            'communication_type': self.communication_type,
            'direction': self.direction, 'subject': self.subject,
            'client_id': self.client_id, 'priority': self.priority,
            'follow_up_required': self.follow_up_required,
            'communication_date': self.communication_date.isoformat() if self.communication_date else None,
        }


class CommunicationTemplate(Base):
    __tablename__ = 'communication_templates'

    id = Column(Integer, primary_key=True)
    name = Column(String(150), nullable=False)
    communication_type = Column(String(20), nullable=False)
    subject_template = Column(String(255), nullable=False)
    description_template = Column(Text, nullable=True)
    follow_up_required = Column(Boolean, default=False, nullable=False)
    follow_up_days = Column(Integer, nullable=True)
    default_priority = Column(String(10), nullable=False, default='normal')
    is_active = Column(Boolean, default=True, nullable=False)
    created_by_id = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by = relationship('User', foreign_keys=[created_by_id])
