"""Job Material model — tracks parts/materials used on jobs."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from .database import Base


MATERIAL_STATUSES = [
    ('logged', 'Logged'), ('verified', 'Verified'), ('invoiced', 'Invoiced'),
]

MATERIAL_STATUS_COLORS = {
    'logged': 'secondary', 'verified': 'info', 'invoiced': 'success',
}


class JobMaterial(Base):
    __tablename__ = 'job_materials'

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)

    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=False, index=True)
    part_id = Column(Integer, ForeignKey('parts.id'), nullable=True, index=True)
    phase_id = Column(Integer, ForeignKey('job_phases.id'), nullable=True)
    project_id = Column(Integer, ForeignKey('projects.id'), nullable=True)

    # For non-catalog items
    custom_description = Column(String(500), nullable=True)

    # Quantities & units
    quantity = Column(Float, nullable=False, default=1)
    unit_of_measure = Column(String(20), nullable=True, default='each')

    # Pricing
    unit_cost = Column(Float, nullable=False, default=0)
    markup_percentage = Column(Float, nullable=True, default=0)
    sell_price_per_unit = Column(Float, nullable=False, default=0)
    total_cost = Column(Float, nullable=False, default=0)
    total_sell = Column(Float, nullable=False, default=0)

    # Source & billing
    source_location_id = Column(Integer, ForeignKey('inventory_locations.id'), nullable=True)
    is_billable = Column(Boolean, nullable=False, default=True)
    is_warranty_replacement = Column(Boolean, nullable=False, default=False)

    # Status
    status = Column(String(20), nullable=False, default='logged')

    # Tracking
    added_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    added_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    job = relationship('Job', back_populates='materials')
    part = relationship('Part', back_populates='job_materials')
    phase = relationship('JobPhase')
    source_location = relationship('InventoryLocation')
    added_by_user = relationship('User', foreign_keys=[added_by])

    __table_args__ = (
        Index('ix_job_mat_job', 'job_id'),
        Index('ix_job_mat_org', 'organization_id'),
    )

    @property
    def display_name(self):
        if self.part:
            return self.part.name
        return self.custom_description or 'Custom Item'

    @property
    def status_display(self):
        return dict(MATERIAL_STATUSES).get(self.status, self.status)

    @property
    def status_color(self):
        return MATERIAL_STATUS_COLORS.get(self.status, 'secondary')

    @property
    def margin(self):
        return round(float(self.total_sell or 0) - float(self.total_cost or 0), 2)

    def to_dict(self):
        return {
            'id': self.id,
            'job_id': self.job_id,
            'part_id': self.part_id,
            'display_name': self.display_name,
            'part_number': self.part.part_number if self.part else None,
            'quantity': self.quantity,
            'unit_of_measure': self.unit_of_measure,
            'unit_cost': self.unit_cost,
            'sell_price_per_unit': self.sell_price_per_unit,
            'total_cost': self.total_cost,
            'total_sell': self.total_sell,
            'is_billable': self.is_billable,
            'is_warranty_replacement': self.is_warranty_replacement,
            'status': self.status,
            'added_at': self.added_at.isoformat() if self.added_at else None,
        }
