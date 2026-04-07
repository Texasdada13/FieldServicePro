"""Notifications triggered by portal activity."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class PortalNotification(Base):
    __tablename__ = 'portal_notifications'

    id                = Column(Integer, primary_key=True)
    notification_type = Column(String(50), nullable=False)
    # Types: service_request, quote_approved, quote_change_requested,
    #        co_approved, co_rejected, portal_message, portal_user_created

    title             = Column(String(255), nullable=False)
    message           = Column(Text, nullable=True)
    link              = Column(String(500), nullable=True)

    # Who triggered it
    triggered_by_portal_user_id   = Column(Integer, ForeignKey('portal_users.id'), nullable=True)
    triggered_by_internal_user_id = Column(Integer, ForeignKey('users.id'), nullable=True)

    # Target audience
    target_type    = Column(String(20), nullable=False)  # 'internal' or 'portal'
    target_user_id = Column(Integer, nullable=True)  # Specific user, or null for broadcast
    target_role    = Column(String(30), nullable=True)  # e.g., 'dispatcher' for internal broadcasts

    # Related entities
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=True)
    job_id    = Column(Integer, ForeignKey('jobs.id'), nullable=True)

    is_read    = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    triggered_by_portal_user = relationship('PortalUser', backref='triggered_notifications')
    triggered_by_internal_user = relationship('User', foreign_keys=[triggered_by_internal_user_id])

    def to_dict(self):
        return {
            'id': self.id, 'notification_type': self.notification_type,
            'title': self.title, 'message': self.message,
            'link': self.link, 'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<PortalNotification {self.id} type={self.notification_type}>'
