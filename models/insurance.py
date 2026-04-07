"""Insurance policy management model."""
from datetime import datetime, date, timedelta
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class InsurancePolicy(Base):
    __tablename__ = 'insurance_policies'

    id                    = Column(Integer, primary_key=True)
    policy_type           = Column(String(50), nullable=False, default='general_liability')
    policy_number         = Column(String(100), nullable=False)
    provider              = Column(String(200), nullable=False)
    coverage_amount       = Column(Float, nullable=False, default=0)
    deductible            = Column(Float, nullable=True)
    premium               = Column(Float, nullable=True)
    start_date            = Column(Date, nullable=False)
    end_date              = Column(Date, nullable=False)

    status                = Column(String(50), nullable=False, default='active')
    auto_renew            = Column(Boolean, default=False)
    renewal_reminder_days = Column(Integer, default=30)
    division_id           = Column(Integer, ForeignKey('divisions.id'), nullable=True)
    notes                 = Column(Text, nullable=True)

    created_by            = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at            = Column(DateTime, default=datetime.utcnow)
    updated_at            = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    division = relationship('Division', backref='insurance_policies')
    creator  = relationship('User', foreign_keys=[created_by])

    POLICY_TYPES = [
        ('general_liability', 'General Liability'),
        ('workers_comp', "Workers' Compensation"),
        ('commercial_auto', 'Commercial Auto'),
        ('professional_liability', 'Professional Liability'),
        ('umbrella', 'Umbrella'),
        ('equipment_floater', 'Equipment Floater'),
        ('pollution', 'Pollution'),
        ('cyber', 'Cyber'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'), ('expiring_soon', 'Expiring Soon'),
        ('expired', 'Expired'), ('cancelled', 'Cancelled'),
        ('pending_renewal', 'Pending Renewal'),
    ]

    STATUS_COLORS = {
        'active': 'success', 'expiring_soon': 'warning',
        'expired': 'danger', 'cancelled': 'draft', 'pending_renewal': 'active',
    }

    @property
    def status_color(self):
        return self.STATUS_COLORS.get(self.status, 'secondary')

    @property
    def status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

    @property
    def type_display(self):
        return dict(self.POLICY_TYPES).get(self.policy_type, self.policy_type)

    @property
    def is_expired(self):
        return self.end_date < date.today()

    @property
    def is_expiring_soon(self):
        threshold = date.today() + timedelta(days=self.renewal_reminder_days or 30)
        return date.today() <= self.end_date <= threshold

    @property
    def days_until_expiry(self):
        return (self.end_date - date.today()).days if self.end_date else None

    @property
    def computed_status(self):
        if self.status == 'cancelled':
            return 'cancelled'
        if self.is_expired:
            return 'expired'
        if self.is_expiring_soon:
            return 'expiring_soon'
        return 'active'

    def update_status(self):
        self.status = self.computed_status

    def to_dict(self):
        return {
            'id': self.id, 'policy_type': self.policy_type,
            'type_display': self.type_display,
            'policy_number': self.policy_number, 'provider': self.provider,
            'coverage_amount': float(self.coverage_amount or 0),
            'premium': float(self.premium or 0),
            'start_date': self.start_date.isoformat() if self.start_date else None,
            'end_date': self.end_date.isoformat() if self.end_date else None,
            'status': self.status, 'status_display': self.status_display,
            'status_color': self.status_color,
            'days_until_expiry': self.days_until_expiry,
            'auto_renew': self.auto_renew,
        }

    def __repr__(self):
        return f'<InsurancePolicy {self.id}: {self.policy_type} - {self.provider}>'
