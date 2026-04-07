"""Technician certification management model."""
from datetime import datetime, date, timedelta
from sqlalchemy import Column, Integer, String, Text, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class TechnicianCertification(Base):
    __tablename__ = 'technician_certifications'

    id                    = Column(Integer, primary_key=True)
    technician_id         = Column(Integer, ForeignKey('technicians.id'), nullable=False, index=True)
    certification_type    = Column(String(50), nullable=False, default='other')
    certification_name    = Column(String(200), nullable=False)
    issuing_body          = Column(String(200), nullable=True)
    certificate_number    = Column(String(100), nullable=True)
    issue_date            = Column(Date, nullable=False)
    expiry_date           = Column(Date, nullable=True)
    status                = Column(String(50), nullable=False, default='active')
    is_required           = Column(Boolean, default=False)
    renewal_reminder_days = Column(Integer, default=30)
    notes                 = Column(Text, nullable=True)
    created_by            = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at            = Column(DateTime, default=datetime.utcnow)
    updated_at            = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    technician = relationship('Technician', backref='certifications')
    creator    = relationship('User', foreign_keys=[created_by])

    CERT_TYPES = [
        ('trade_license', 'Trade License'), ('safety_training', 'Safety Training'),
        ('equipment_operator', 'Equipment Operator'), ('first_aid', 'First Aid / CPR'),
        ('confined_space', 'Confined Space Entry'), ('fall_protection', 'Fall Protection'),
        ('hazmat', 'HAZMAT'), ('backflow', 'Backflow Prevention'),
        ('gas_fitter', 'Gas Fitter'), ('refrigerant_handling', 'Refrigerant Handling'),
        ('other', 'Other'),
    ]

    STATUS_COLORS = {
        'active': 'success', 'expiring_soon': 'warning', 'expired': 'danger',
        'suspended': 'draft', 'revoked': 'danger',
    }

    @property
    def status_color(self):
        return self.STATUS_COLORS.get(self.status, 'secondary')

    @property
    def status_display(self):
        return {'active': 'Active', 'expiring_soon': 'Expiring Soon', 'expired': 'Expired',
                'suspended': 'Suspended', 'revoked': 'Revoked'}.get(self.status, self.status)

    @property
    def type_display(self):
        return dict(self.CERT_TYPES).get(self.certification_type, self.certification_type)

    @property
    def is_expired(self):
        return self.expiry_date and self.expiry_date < date.today()

    @property
    def is_expiring_soon(self):
        if not self.expiry_date:
            return False
        return date.today() <= self.expiry_date <= date.today() + timedelta(days=self.renewal_reminder_days or 30)

    @property
    def is_valid(self):
        return self.status not in ('suspended', 'revoked') and not self.is_expired

    @property
    def computed_status(self):
        if self.status in ('suspended', 'revoked'):
            return self.status
        if self.is_expired:
            return 'expired'
        if self.is_expiring_soon:
            return 'expiring_soon'
        return 'active'

    def update_status(self):
        self.status = self.computed_status

    @property
    def days_until_expiry(self):
        return (self.expiry_date - date.today()).days if self.expiry_date else None

    def to_dict(self):
        return {
            'id': self.id, 'technician_id': self.technician_id,
            'certification_type': self.certification_type, 'type_display': self.type_display,
            'certification_name': self.certification_name,
            'status': self.status, 'status_display': self.status_display,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'days_until_expiry': self.days_until_expiry,
            'is_valid': self.is_valid,
        }

    def __repr__(self):
        return f'<TechnicianCertification {self.id}: {self.certification_name}>'


class JobCertificationRequirement(Base):
    __tablename__ = 'job_certification_requirements'

    id                 = Column(Integer, primary_key=True)
    job_type           = Column(String(100), nullable=False)
    certification_type = Column(String(50), nullable=False)
    is_mandatory       = Column(Boolean, default=True)
    notes              = Column(Text, nullable=True)
    created_at         = Column(DateTime, default=datetime.utcnow)
