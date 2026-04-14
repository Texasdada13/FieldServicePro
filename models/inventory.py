"""Inventory models: Location, Stock, and Transaction tracking."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from .database import Base


LOCATION_TYPES = [
    ('warehouse', 'Warehouse'), ('truck', 'Truck/Van'), ('job_site', 'Job Site'),
    ('office', 'Office'), ('supplier', 'Supplier'), ('other', 'Other'),
]

TRANSACTION_TYPES = [
    ('received', 'Received'), ('issued', 'Issued to Job'), ('returned', 'Returned'),
    ('adjusted', 'Adjustment'), ('transferred_in', 'Transferred In'),
    ('transferred_out', 'Transferred Out'), ('scrapped', 'Scrapped'),
    ('cycle_count', 'Cycle Count'),
]


class InventoryLocation(Base):
    __tablename__ = 'inventory_locations'

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)

    name = Column(String(200), nullable=False)
    location_type = Column(String(30), nullable=False, default='warehouse')
    address = Column(String(500), nullable=True)
    description = Column(Text, nullable=True)

    # If truck, link to technician
    technician_id = Column(Integer, ForeignKey('technicians.id'), nullable=True)

    is_active = Column(Boolean, nullable=False, default=True)
    is_default = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    stocks = relationship('InventoryStock', back_populates='location', cascade='all, delete-orphan')
    technician = relationship('Technician', backref='inventory_location')

    __table_args__ = (
        Index('ix_inv_loc_org', 'organization_id'),
    )

    @property
    def type_display(self):
        return dict(LOCATION_TYPES).get(self.location_type, self.location_type)

    @property
    def total_items(self):
        return sum(s.quantity_on_hand for s in self.stocks if s.quantity_on_hand > 0)

    @property
    def total_value(self):
        return sum(s.quantity_on_hand * float(s.part.cost_price or 0) for s in self.stocks if s.quantity_on_hand > 0)

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'location_type': self.location_type,
            'type_display': self.type_display,
            'technician_id': self.technician_id,
            'is_active': self.is_active,
            'is_default': self.is_default,
            'total_items': self.total_items,
        }


class InventoryStock(Base):
    """Current stock level for a part at a specific location."""
    __tablename__ = 'inventory_stock'

    id = Column(Integer, primary_key=True)
    part_id = Column(Integer, ForeignKey('parts.id'), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey('inventory_locations.id'), nullable=False, index=True)

    quantity_on_hand = Column(Integer, nullable=False, default=0)
    quantity_reserved = Column(Integer, nullable=False, default=0)
    quantity_on_order = Column(Integer, nullable=False, default=0)

    last_counted_at = Column(DateTime, nullable=True)
    last_received_at = Column(DateTime, nullable=True)

    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    part = relationship('Part', back_populates='inventory_stocks')
    location = relationship('InventoryLocation', back_populates='stocks')

    __table_args__ = (
        Index('ix_inv_stock_part_loc', 'part_id', 'location_id', unique=True),
    )

    @property
    def available_quantity(self):
        return max(0, self.quantity_on_hand - self.quantity_reserved)

    @property
    def is_low_stock(self):
        """True if this stock record's part is below min at this location."""
        if self.part and self.part.minimum_stock_level > 0:
            return self.quantity_on_hand <= self.part.minimum_stock_level
        return False

    @property
    def stock_value(self):
        return (self.quantity_on_hand or 0) * float(self.part.cost_price or 0)

    def to_dict(self):
        return {
            'id': self.id,
            'part_id': self.part_id,
            'location_id': self.location_id,
            'quantity_on_hand': self.quantity_on_hand,
            'quantity_reserved': self.quantity_reserved,
            'quantity_on_order': self.quantity_on_order,
            'available_quantity': self.available_quantity,
        }


class InventoryTransaction(Base):
    """Audit trail for every inventory movement."""
    __tablename__ = 'inventory_transactions'

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)

    part_id = Column(Integer, ForeignKey('parts.id'), nullable=False, index=True)
    location_id = Column(Integer, ForeignKey('inventory_locations.id'), nullable=False)

    transaction_type = Column(String(30), nullable=False)
    quantity = Column(Integer, nullable=False)  # positive for in, negative for out
    unit_cost = Column(Float, nullable=True)

    # Reference links
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=True)
    job_material_id = Column(Integer, ForeignKey('job_materials.id'), nullable=True)
    transfer_id = Column(Integer, ForeignKey('stock_transfers.id'), nullable=True)
    po_id = Column(Integer, ForeignKey('purchase_orders.id'), nullable=True)

    reference_number = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    part = relationship('Part', back_populates='transactions')
    location = relationship('InventoryLocation')
    job = relationship('Job')
    creator = relationship('User', foreign_keys=[created_by])

    __table_args__ = (
        Index('ix_inv_txn_part_date', 'part_id', 'created_at'),
        Index('ix_inv_txn_org', 'organization_id'),
    )

    @property
    def type_display(self):
        return dict(TRANSACTION_TYPES).get(self.transaction_type, self.transaction_type)

    @property
    def total_cost(self):
        return abs(self.quantity or 0) * float(self.unit_cost or 0)

    def to_dict(self):
        return {
            'id': self.id,
            'part_id': self.part_id,
            'location_id': self.location_id,
            'transaction_type': self.transaction_type,
            'type_display': self.type_display,
            'quantity': self.quantity,
            'unit_cost': self.unit_cost,
            'job_id': self.job_id,
            'reference_number': self.reference_number,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
