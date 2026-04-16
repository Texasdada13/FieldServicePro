"""Restock Request model — technicians request parts from warehouse."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


RESTOCK_STATUSES = [
    ('pending', 'Pending'), ('approved', 'Approved'),
    ('fulfilled', 'Fulfilled'), ('denied', 'Denied'),
]


class RestockRequest(Base):
    __tablename__ = 'restock_requests'

    id = Column(Integer, primary_key=True)
    technician_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    part_id = Column(Integer, ForeignKey('parts.id'), nullable=False)
    quantity_requested = Column(Float, nullable=False, default=1)
    notes = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default='pending')
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    technician = relationship('User', foreign_keys=[technician_id])
    part = relationship('Part')

    def to_dict(self):
        return {
            'id': self.id,
            'technician_id': self.technician_id,
            'part_id': self.part_id,
            'part_name': self.part.name if self.part else '',
            'quantity_requested': self.quantity_requested,
            'status': self.status,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
