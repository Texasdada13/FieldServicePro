"""Portal-specific configuration. Single-row table per organization."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from .database import Base, get_session


class PortalSettings(Base):
    __tablename__ = 'portal_settings'

    id                          = Column(Integer, primary_key=True)
    organization_id             = Column(Integer, ForeignKey('organizations.id'), nullable=True)

    portal_enabled              = Column(Boolean, default=False, nullable=False)
    welcome_message             = Column(Text, nullable=True,
        default='Welcome to your service portal. Here you can track jobs, approve quotes, view invoices, and more.')
    payment_instructions        = Column(Text, nullable=True,
        default='Please contact our billing department for payment options.')
    company_contact_info        = Column(Text, nullable=True)

    session_timeout_minutes     = Column(Integer, default=30, nullable=False)

    allow_service_requests      = Column(Boolean, default=True, nullable=False)
    allow_quote_approval        = Column(Boolean, default=True, nullable=False)
    allow_change_order_approval = Column(Boolean, default=True, nullable=False)
    auto_convert_approved_quotes = Column(Boolean, default=False, nullable=False)

    email_on_service_request    = Column(Boolean, default=True, nullable=False)
    email_on_quote_approval     = Column(Boolean, default=True, nullable=False)
    email_on_co_approval        = Column(Boolean, default=True, nullable=False)
    email_on_portal_message     = Column(Boolean, default=True, nullable=False)
    email_on_job_status_change  = Column(Boolean, default=True, nullable=False)
    email_on_invoice_issued     = Column(Boolean, default=True, nullable=False)

    updated_at                  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @classmethod
    def get_settings(cls, db=None):
        """Get or create portal settings. Opens own session if db not provided."""
        own_session = db is None
        if own_session:
            db = get_session()
        try:
            settings = db.query(cls).first()
            if not settings:
                settings = cls()
                db.add(settings)
                db.commit()
            return settings
        finally:
            if own_session:
                db.close()

    def to_dict(self):
        return {
            'portal_enabled': self.portal_enabled,
            'welcome_message': self.welcome_message,
            'payment_instructions': self.payment_instructions,
            'company_contact_info': self.company_contact_info,
            'session_timeout_minutes': self.session_timeout_minutes,
            'allow_service_requests': self.allow_service_requests,
            'allow_quote_approval': self.allow_quote_approval,
            'allow_change_order_approval': self.allow_change_order_approval,
            'auto_convert_approved_quotes': self.auto_convert_approved_quotes,
        }
