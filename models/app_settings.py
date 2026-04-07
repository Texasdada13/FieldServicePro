"""
Application-wide settings stored as key-value pairs.
Supports typed retrieval (decimal, int, bool, string, json).
"""

from datetime import datetime
import json
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from .database import Base, get_session


class AppSettings(Base):
    __tablename__ = 'app_settings'

    id          = Column(Integer, primary_key=True)
    key         = Column(String(100), unique=True, nullable=False, index=True)
    value       = Column(Text, nullable=True)
    value_type  = Column(String(20), nullable=False, default='string')
    description = Column(String(500), nullable=True)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by  = Column(Integer, ForeignKey('users.id'), nullable=True)

    @classmethod
    def get(cls, key, default=None):
        """Get a setting value by key. Opens its own session."""
        db = get_session()
        try:
            record = db.query(cls).filter_by(key=key).first()
            if record is None:
                return default
            return cls._cast(record.value, record.value_type, default)
        finally:
            db.close()

    @classmethod
    def get_with_session(cls, db, key, default=None):
        """Get a setting value using an existing session."""
        record = db.query(cls).filter_by(key=key).first()
        if record is None:
            return default
        return cls._cast(record.value, record.value_type, default)

    @classmethod
    def set(cls, key, value, value_type='string', description=None, user_id=None):
        """Set a setting value. Opens its own session and commits."""
        db = get_session()
        try:
            record = db.query(cls).filter_by(key=key).first()
            if record is None:
                record = cls(key=key, value_type=value_type, description=description)
                db.add(record)
            if value_type == 'json':
                record.value = json.dumps(value)
            elif value_type == 'bool':
                record.value = 'true' if value else 'false'
            else:
                record.value = str(value) if value is not None else None
            record.value_type = value_type
            record.updated_by = user_id
            db.commit()
        finally:
            db.close()

    @staticmethod
    def _cast(raw, value_type, default):
        if raw is None:
            return default
        try:
            if value_type == 'int':
                return int(raw)
            elif value_type == 'decimal':
                return float(raw)
            elif value_type == 'bool':
                return raw.lower() in ('true', '1', 'yes')
            elif value_type == 'json':
                return json.loads(raw)
            else:
                return raw
        except (ValueError, TypeError):
            return default

    # Convenience accessors for commercial invoicing settings
    @classmethod
    def invoice_approval_threshold(cls):
        """Returns float or None. None = no approval required."""
        val = cls.get('invoice_approval_threshold', default=None)
        if val is None:
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None

    @classmethod
    def invoice_approval_roles(cls):
        """Returns list of role strings that can approve invoices."""
        return cls.get(
            'invoice_approval_roles',
            default=['owner', 'admin'],
        ) or ['owner', 'admin']

    @classmethod
    def late_fee_rate_default(cls):
        return cls.get('late_fee_rate_default', default=1.5)

    @classmethod
    def statement_footer_text(cls):
        return cls.get(
            'statement_footer_text',
            default='Thank you for your business. Please remit payment by the due date.',
        )

    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value,
            'value_type': self.value_type,
            'description': self.description,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }

    def __repr__(self):
        return f'<AppSettings {self.key}={self.value}>'
