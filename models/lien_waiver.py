"""Lien waiver models."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class LienWaiver(Base):
    __tablename__ = 'lien_waivers'

    id             = Column(Integer, primary_key=True)
    job_id         = Column(Integer, ForeignKey('jobs.id'), nullable=False)
    waiver_type    = Column(String(50), nullable=False, default='conditional_progress')
    party_type     = Column(String(50), nullable=False, default='subcontractor')
    party_name     = Column(String(200), nullable=False)
    amount         = Column(Float, nullable=True)
    invoice_id     = Column(Integer, ForeignKey('invoices.id'), nullable=True)
    status         = Column(String(50), nullable=False, default='requested')
    through_date   = Column(Date, nullable=True)
    requested_date = Column(Date, nullable=True)
    received_date  = Column(Date, nullable=True)
    notes          = Column(Text, nullable=True)
    created_by     = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at     = Column(DateTime, default=datetime.utcnow)
    updated_at     = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    job     = relationship('Job', backref='lien_waivers')
    invoice = relationship('Invoice', backref='lien_waivers')
    creator = relationship('User', foreign_keys=[created_by])

    WAIVER_TYPES = [
        ('conditional_progress', 'Conditional Progress'),
        ('unconditional_progress', 'Unconditional Progress'),
        ('conditional_final', 'Conditional Final'),
        ('unconditional_final', 'Unconditional Final'),
    ]

    PARTY_TYPES = [
        ('subcontractor', 'Subcontractor'),
        ('supplier', 'Supplier / Material Provider'),
        ('general_contractor', 'General Contractor'),
        ('owner', 'Property Owner'),
        ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('requested', 'Requested'),
        ('sent', 'Sent'),
        ('received', 'Received'),
        ('accepted', 'Accepted'),
        ('rejected', 'Rejected'),
        ('expired', 'Expired'),
    ]

    STATUS_COLORS = {
        'requested': 'warning',
        'sent': 'info',
        'received': 'accent',
        'accepted': 'success',
        'rejected': 'danger',
        'expired': 'secondary',
    }

    @property
    def type_display(self):
        return dict(self.WAIVER_TYPES).get(self.waiver_type, self.waiver_type)

    @property
    def party_type_display(self):
        return dict(self.PARTY_TYPES).get(self.party_type, self.party_type)

    @property
    def status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

    @property
    def status_color(self):
        return self.STATUS_COLORS.get(self.status, 'secondary')

    def to_dict(self):
        return {
            'id': self.id, 'job_id': self.job_id,
            'waiver_type': self.waiver_type, 'party_type': self.party_type,
            'party_name': self.party_name, 'amount': self.amount,
            'status': self.status,
        }
