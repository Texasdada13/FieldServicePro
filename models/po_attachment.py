"""Purchase Order Attachment model."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class POAttachment(Base):
    __tablename__ = 'po_attachments'

    id                = Column(Integer, primary_key=True)
    purchase_order_id = Column(Integer, ForeignKey('purchase_orders.id'), nullable=False)
    filename          = Column(String(255), nullable=False)
    original_filename = Column(String(255), nullable=False)
    file_size         = Column(Integer, nullable=True)
    content_type      = Column(String(100), nullable=True)
    uploaded_by       = Column(Integer, ForeignKey('users.id'), nullable=True)
    uploaded_at       = Column(DateTime, default=datetime.utcnow)
    notes             = Column(String(500), nullable=True)

    purchase_order = relationship('PurchaseOrder', back_populates='attachments')
    uploader       = relationship('User', foreign_keys=[uploaded_by])

    def to_dict(self):
        return {
            'id': self.id,
            'purchase_order_id': self.purchase_order_id,
            'filename': self.filename,
            'original_filename': self.original_filename,
            'file_size': self.file_size,
            'content_type': self.content_type,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None,
            'notes': self.notes,
        }

    def __repr__(self):
        return f'<POAttachment {self.original_filename}>'
