"""Vendor Price — per-vendor pricing for parts."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, Date, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import relationship
from .database import Base


class VendorPrice(Base):
    __tablename__ = 'vendor_prices'
    __table_args__ = (UniqueConstraint('vendor_id', 'part_id', name='uq_vendor_part'),)

    id = Column(Integer, primary_key=True)
    vendor_id = Column(Integer, ForeignKey('vendors.id', ondelete='CASCADE'), nullable=False, index=True)
    part_id = Column(Integer, ForeignKey('parts.id', ondelete='CASCADE'), nullable=False, index=True)
    vendor_part_number = Column(String(100), nullable=True)
    unit_price = Column(Float, nullable=False)
    minimum_order_quantity = Column(Integer, nullable=False, default=1)
    bulk_price = Column(Float, nullable=True)
    bulk_threshold = Column(Integer, nullable=True)
    lead_time_days = Column(Integer, nullable=True)
    is_preferred = Column(Boolean, nullable=False, default=False)
    last_quoted_date = Column(Date, nullable=True)
    price_valid_until = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    vendor = relationship('Vendor', backref='prices')
    part = relationship('Part', backref='vendor_prices')

    def effective_price(self, quantity=1):
        if self.bulk_price and self.bulk_threshold and quantity >= self.bulk_threshold:
            return float(self.bulk_price)
        return float(self.unit_price)
