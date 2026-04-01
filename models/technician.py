"""Technician model."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from .database import Base


class Technician(Base):
    __tablename__ = 'technicians'

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    division_id = Column(Integer, ForeignKey('divisions.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'))  # optional link to user account

    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100))
    email = Column(String(255))
    phone = Column(String(50))
    mobile = Column(String(50))

    color = Column(String(7), default='#2563eb')  # for calendar display
    is_active = Column(Boolean, default=True)
    hourly_rate = Column(Integer)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    division = relationship("Division", back_populates="technicians")
    jobs = relationship("Job", back_populates="technician")

    @property
    def full_name(self):
        if self.first_name and self.last_name:
            return f"{self.first_name} {self.last_name}"
        return self.first_name or self.last_name or self.email or f'Tech #{self.id}'

    def to_dict(self):
        return {
            'id': self.id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'full_name': self.full_name,
            'email': self.email,
            'phone': self.phone,
            'mobile': self.mobile,
            'division_id': self.division_id,
            'color': self.color,
            'is_active': self.is_active,
            'hourly_rate': self.hourly_rate
        }
