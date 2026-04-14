"""
Organization-wide settings. Singleton row per organization.
Accessed via OrganizationSettings.get(db) or OrganizationSettings.get_or_create(db, org_id).
"""
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, DateTime, ForeignKey
from .database import Base


class OrganizationSettings(Base):
    __tablename__ = 'organization_settings'

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)

    # -- Invoice Approval --
    invoice_approval_enabled   = Column(Boolean, default=False, nullable=False)
    invoice_approval_threshold = Column(Float, nullable=True)  # None = all commercial
    invoice_approval_roles     = Column(String(200), default='owner,admin', nullable=False)

    # -- Late Fees --
    default_late_fee_rate  = Column(Float, default=1.5)
    late_fee_grace_days    = Column(Integer, default=0)

    # -- Invoice Numbering --
    invoice_number_prefix    = Column(String(10), default='INV')
    invoice_sequence_year    = Column(Integer, nullable=True)
    invoice_sequence_counter = Column(Integer, default=1)

    # -- Statement Footer --
    statement_footer_text = Column(Text, nullable=True)

    # -- Notifications --
    notifications_enabled = Column(Boolean, default=True, nullable=False)
    client_notifications_enabled = Column(Boolean, default=True, nullable=False)
    email_from_name = Column(String(100), nullable=True)
    email_from_address = Column(String(255), nullable=True)
    email_reply_to = Column(String(255), nullable=True)
    sms_enabled = Column(Boolean, default=False, nullable=False)
    sms_provider = Column(String(20), nullable=True)
    sms_api_key = Column(String(500), nullable=True)
    sms_from_number = Column(String(20), nullable=True)
    notification_polling_interval = Column(Integer, default=30)
    appointment_reminder_hours = Column(Integer, default=24)
    invoice_reminder_days = Column(String(50), default='[7, 14, 30]')

    # -- Audit --
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by = Column(Integer, ForeignKey('users.id'), nullable=True)

    @classmethod
    def get_or_create(cls, db, org_id):
        """Fetch or lazily create the settings row for an organization."""
        obj = db.query(cls).filter_by(organization_id=org_id).first()
        if not obj:
            obj = cls(organization_id=org_id)
            db.add(obj)
            db.flush()
        return obj

    @property
    def approval_role_list(self):
        return [r.strip() for r in (self.invoice_approval_roles or '').split(',') if r.strip()]

    def requires_approval(self, amount, client_type='commercial'):
        """Returns True if an invoice of this amount should enter pending approval."""
        if not self.invoice_approval_enabled:
            return False
        if client_type != 'commercial':
            return False
        if self.invoice_approval_threshold is None:
            return True
        return float(amount or 0) > float(self.invoice_approval_threshold)

    def next_invoice_number(self, db):
        """Sequential invoice number: {PREFIX}-{YYYY}-{NNNN}. Resets each year."""
        year = date.today().year
        if self.invoice_sequence_year != year:
            self.invoice_sequence_year = year
            self.invoice_sequence_counter = 1

        number = f"{self.invoice_number_prefix}-{year}-{self.invoice_sequence_counter:04d}"
        self.invoice_sequence_counter += 1
        db.flush()
        return number

    def to_dict(self):
        return {
            'id': self.id,
            'invoice_approval_enabled': self.invoice_approval_enabled,
            'invoice_approval_threshold': self.invoice_approval_threshold,
            'invoice_approval_roles': self.invoice_approval_roles,
            'default_late_fee_rate': self.default_late_fee_rate,
            'late_fee_grace_days': self.late_fee_grace_days,
            'invoice_number_prefix': self.invoice_number_prefix,
            'statement_footer_text': self.statement_footer_text,
        }
