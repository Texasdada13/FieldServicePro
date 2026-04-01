"""Division model — Plumbing, HVAC, Electrical, General Contracting."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from .database import Base


class Division(Base):
    __tablename__ = 'divisions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    name = Column(String(100), nullable=False)  # e.g. "Plumbing", "HVAC", "Electrical", "General Contracting"
    code = Column(String(10), nullable=False)    # e.g. "PLB", "HVAC", "ELEC", "GC"
    color = Column(String(7), default='#2563eb')  # hex color for UI badges
    icon = Column(String(50), default='bi-wrench')
    is_active = Column(Boolean, default=True)
    description = Column(Text)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)

    organization = relationship("Organization", back_populates="divisions")
    jobs = relationship("Job", back_populates="division", cascade="all, delete-orphan")
    quotes = relationship("Quote", back_populates="division", cascade="all, delete-orphan")
    technicians = relationship("Technician", back_populates="division", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'color': self.color,
            'icon': self.icon,
            'is_active': self.is_active,
            'description': self.description,
            'sort_order': self.sort_order
        }
