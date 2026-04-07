"""Portal messaging model for per-job communication between portal and internal users."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class PortalMessage(Base):
    __tablename__ = 'portal_messages'

    id                  = Column(Integer, primary_key=True)
    job_id              = Column(Integer, ForeignKey('jobs.id'), nullable=False, index=True)
    sender_type         = Column(String(20), nullable=False)  # 'portal_user' or 'internal_user'
    sender_id           = Column(Integer, nullable=False)
    message             = Column(Text, nullable=False)
    is_read_by_recipient = Column(Boolean, default=False, nullable=False)
    created_at          = Column(DateTime, default=datetime.utcnow, nullable=False)

    job = relationship('Job', backref='portal_messages')

    @property
    def sender_name(self):
        from .database import get_session
        db = get_session()
        try:
            if self.sender_type == 'portal_user':
                from .portal_user import PortalUser
                user = db.query(PortalUser).filter_by(id=self.sender_id).first()
                return user.full_name if user else 'Unknown'
            else:
                from .user import User
                user = db.query(User).filter_by(id=self.sender_id).first()
                return user.full_name if user else 'Staff'
        finally:
            db.close()

    def to_dict(self):
        return {
            'id': self.id, 'job_id': self.job_id,
            'sender_type': self.sender_type, 'sender_id': self.sender_id,
            'sender_name': self.sender_name,
            'message': self.message,
            'is_read_by_recipient': self.is_read_by_recipient,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<PortalMessage {self.id} job={self.job_id} from={self.sender_type}:{self.sender_id}>'
