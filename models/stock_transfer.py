"""Stock Transfer models — move inventory between locations."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from .database import Base


TRANSFER_STATUSES = [
    ('requested', 'Requested'), ('approved', 'Approved'),
    ('in_transit', 'In Transit'), ('completed', 'Completed'),
    ('cancelled', 'Cancelled'),
]

TRANSFER_STATUS_COLORS = {
    'requested': 'secondary', 'approved': 'info',
    'in_transit': 'warning', 'completed': 'success', 'cancelled': 'danger',
}


class StockTransfer(Base):
    __tablename__ = 'stock_transfers'

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)

    transfer_number = Column(String(50), unique=True, nullable=False, index=True)
    status = Column(String(20), nullable=False, default='requested')

    from_location_id = Column(Integer, ForeignKey('inventory_locations.id'), nullable=False)
    to_location_id = Column(Integer, ForeignKey('inventory_locations.id'), nullable=False)

    reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    requested_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    approved_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    completed_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    completed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    from_location = relationship('InventoryLocation', foreign_keys=[from_location_id])
    to_location = relationship('InventoryLocation', foreign_keys=[to_location_id])
    items = relationship('StockTransferItem', back_populates='transfer', cascade='all, delete-orphan')
    requester = relationship('User', foreign_keys=[requested_by])
    approver = relationship('User', foreign_keys=[approved_by])

    __table_args__ = (
        Index('ix_transfer_org', 'organization_id'),
    )

    @property
    def status_display(self):
        return dict(TRANSFER_STATUSES).get(self.status, self.status)

    @property
    def status_color(self):
        return TRANSFER_STATUS_COLORS.get(self.status, 'secondary')

    @property
    def total_items_requested(self):
        return sum(i.quantity_requested or 0 for i in self.items)

    @property
    def total_value(self):
        return sum((i.quantity_requested or 0) * float(i.unit_cost or 0) for i in self.items)

    @property
    def has_discrepancies(self):
        if self.status != 'completed':
            return False
        return any(i.has_discrepancy for i in self.items)

    def to_dict(self):
        return {
            'id': self.id,
            'transfer_number': self.transfer_number,
            'status': self.status,
            'status_display': self.status_display,
            'from_location_id': self.from_location_id,
            'to_location_id': self.to_location_id,
            'total_items_requested': self.total_items_requested,
            'total_value': self.total_value,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


class StockTransferItem(Base):
    __tablename__ = 'stock_transfer_items'

    id = Column(Integer, primary_key=True)
    transfer_id = Column(Integer, ForeignKey('stock_transfers.id'), nullable=False, index=True)
    part_id = Column(Integer, ForeignKey('parts.id'), nullable=False)

    quantity_requested = Column(Integer, nullable=False, default=0)
    quantity_sent = Column(Integer, nullable=True)
    quantity_received = Column(Integer, nullable=True)

    unit_cost = Column(Float, nullable=True)
    notes = Column(Text, nullable=True)

    # Relationships
    transfer = relationship('StockTransfer', back_populates='items')
    part = relationship('Part')

    @property
    def has_discrepancy(self):
        if self.quantity_sent is not None and self.quantity_received is not None:
            return self.quantity_sent != self.quantity_received
        return False

    @property
    def discrepancy_amount(self):
        sent = self.quantity_sent or 0
        received = self.quantity_received or 0
        diff = received - sent
        return f"{'+' if diff > 0 else ''}{diff}"

    def to_dict(self):
        return {
            'id': self.id,
            'transfer_id': self.transfer_id,
            'part_id': self.part_id,
            'part_number': self.part.part_number if self.part else None,
            'part_name': self.part.name if self.part else None,
            'quantity_requested': self.quantity_requested,
            'quantity_sent': self.quantity_sent,
            'quantity_received': self.quantity_received,
            'unit_cost': self.unit_cost,
            'has_discrepancy': self.has_discrepancy,
        }
