"""Service Request model — intake for new work before it becomes a job."""
import builtins
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class ServiceRequest(Base):
    __tablename__ = 'service_requests'

    id                = Column(Integer, primary_key=True)
    request_number    = Column(String(50), unique=True, nullable=False, index=True)
    organization_id   = Column(Integer, ForeignKey('organizations.id'), nullable=False)

    # Contact (may or may not be an existing client)
    client_id         = Column(Integer, ForeignKey('clients.id'), nullable=True)
    property_id       = Column(Integer, ForeignKey('properties.id'), nullable=True)
    contact_name      = Column(String(200), nullable=False)
    contact_phone     = Column(String(50), nullable=True)
    contact_email     = Column(String(255), nullable=True)

    # Details
    source            = Column(String(30), nullable=False, default='phone')
    request_type      = Column(String(50), nullable=True)
    priority          = Column(String(20), nullable=False, default='medium')
    description       = Column(Text, nullable=False)
    preferred_date    = Column(Date, nullable=True)
    preferred_time    = Column(String(30), nullable=True)

    # Workflow
    status            = Column(String(20), nullable=False, default='new', index=True)
    assigned_to       = Column(Integer, ForeignKey('users.id'), nullable=True)
    notes             = Column(Text, nullable=True)
    converted_job_id  = Column(Integer, ForeignKey('jobs.id'), nullable=True)

    # Online booking additions
    preferred_dates       = Column(Text, nullable=True)       # JSON: ["2026-07-15", "2026-07-16"]
    preferred_time_slot   = Column(String(20), nullable=True)  # morning | afternoon | anytime
    referral_source       = Column(String(50), nullable=True)
    access_instructions   = Column(Text, nullable=True)
    customer_address      = Column(Text, nullable=True)
    street_address        = Column(String(200), nullable=True)
    unit_apt              = Column(String(50), nullable=True)
    city                  = Column(String(100), nullable=True)
    state_province        = Column(String(100), nullable=True)
    postal_code           = Column(String(20), nullable=True)
    is_existing_customer  = Column(Boolean, default=False)
    existing_customer_ref = Column(String(200), nullable=True)
    confirmation_sent     = Column(Boolean, default=False)
    confirmation_sent_at  = Column(DateTime, nullable=True)
    booking_token         = Column(String(64), unique=True, nullable=True)
    honeypot_check        = Column(Boolean, default=False)
    submitter_ip          = Column(String(45), nullable=True)

    # Tracking
    created_by        = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at        = Column(DateTime, default=datetime.utcnow)
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    client       = relationship('Client', backref='service_requests')
    property     = relationship('Property', backref='service_requests')
    assigned_user = relationship('User', foreign_keys=[assigned_to])
    creator      = relationship('User', foreign_keys=[created_by])
    converted_job = relationship('Job', foreign_keys=[converted_job_id])

    SOURCE_CHOICES = [
        ('phone', 'Phone'), ('email', 'Email'), ('walk_in', 'Walk-In'),
        ('portal', 'Portal'), ('online_booking', 'Online Booking'),
        ('referral', 'Referral'), ('other', 'Other'),
    ]

    TYPE_CHOICES = [
        ('plumbing', 'Plumbing'), ('hvac', 'HVAC'), ('electrical', 'Electrical'),
        ('general', 'General'), ('service_call', 'Service Call'),
        ('maintenance', 'Maintenance'), ('installation', 'Installation'),
        ('repair', 'Repair'), ('inspection', 'Inspection'), ('emergency', 'Emergency'),
    ]

    PRIORITY_CHOICES = [
        ('emergency', 'Emergency'), ('high', 'High'),
        ('medium', 'Medium'), ('low', 'Low'),
    ]

    STATUS_CHOICES = [
        ('new', 'New'), ('reviewed', 'Reviewed'),
        ('converted', 'Converted'), ('declined', 'Declined'),
        ('cancelled', 'Cancelled'),
    ]

    STATUS_COLORS = {
        'new': 'accent', 'reviewed': 'info',
        'converted': 'success', 'declined': 'secondary',
        'cancelled': 'danger',
    }

    PRIORITY_COLORS = {
        'emergency': 'danger', 'high': 'warning',
        'medium': 'secondary', 'low': 'secondary',
    }

    @builtins.property
    def source_display(self):
        return dict(self.SOURCE_CHOICES).get(self.source, self.source)

    @builtins.property
    def type_display(self):
        return dict(self.TYPE_CHOICES).get(self.request_type, self.request_type or 'General')

    @builtins.property
    def priority_display(self):
        return dict(self.PRIORITY_CHOICES).get(self.priority, self.priority)

    @builtins.property
    def status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

    @builtins.property
    def status_color(self):
        return self.STATUS_COLORS.get(self.status, 'secondary')

    @builtins.property
    def priority_color(self):
        return self.PRIORITY_COLORS.get(self.priority, 'secondary')

    @staticmethod
    def generate_number(db, org_id):
        """Generate next request number: REQ-YYYY-XXXX."""
        year = date.today().year
        last = db.query(ServiceRequest).filter(
            ServiceRequest.organization_id == org_id,
            ServiceRequest.request_number.like(f'REQ-{year}-%')
        ).order_by(ServiceRequest.id.desc()).first()

        seq = 1
        if last and last.request_number:
            parts = last.request_number.split('-')
            if len(parts) == 3:
                try:
                    seq = int(parts[2]) + 1
                except ValueError:
                    pass
        return f"REQ-{year}-{seq:04d}"

    def to_dict(self):
        return {
            'id': self.id,
            'request_number': self.request_number,
            'contact_name': self.contact_name,
            'contact_phone': self.contact_phone,
            'contact_email': self.contact_email,
            'client_id': self.client_id,
            'property_id': self.property_id,
            'source': self.source,
            'request_type': self.request_type,
            'priority': self.priority,
            'description': self.description,
            'status': self.status,
            'converted_job_id': self.converted_job_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
