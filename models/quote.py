"""Quote / Estimate model."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Float
from sqlalchemy.orm import relationship
import enum
from .database import Base


class QuoteStatus(enum.Enum):
    DRAFT = "draft"
    SENT = "sent"
    APPROVED = "approved"
    DECLINED = "declined"
    EXPIRED = "expired"
    CONVERTED = "converted"  # converted to a job


class Quote(Base):
    __tablename__ = 'quotes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    division_id = Column(Integer, ForeignKey('divisions.id'), nullable=False)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    property_id = Column(Integer, ForeignKey('properties.id'))

    quote_number = Column(String(50), unique=True, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(20), default=QuoteStatus.DRAFT.value, index=True)

    # Financial
    subtotal = Column(Float, default=0)
    tax_rate = Column(Float, default=13.0)  # Ontario HST
    tax_amount = Column(Float, default=0)
    total = Column(Float, default=0)
    discount = Column(Float, default=0)

    # Dates
    issued_date = Column(DateTime)
    valid_until = Column(DateTime)
    approved_date = Column(DateTime)

    # Template info
    template_name = Column(String(100))  # e.g. "BFP", "Curb Stop Assessment", "Water Softener"

    notes = Column(Text)

    # Portal approval
    portal_approved_by = Column(Integer, ForeignKey('portal_users.id'), nullable=True)
    portal_approved_at = Column(DateTime, nullable=True)
    portal_approval_note = Column(Text, nullable=True)

    created_by_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    division = relationship("Division", back_populates="quotes")
    client = relationship("Client", back_populates="quotes")
    property = relationship("Property", back_populates="quotes")
    items = relationship("QuoteItem", back_populates="quote", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'quote_number': self.quote_number,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'division_id': self.division_id,
            'client_id': self.client_id,
            'property_id': self.property_id,
            'subtotal': self.subtotal,
            'tax_rate': self.tax_rate,
            'tax_amount': self.tax_amount,
            'total': self.total,
            'discount': self.discount,
            'issued_date': self.issued_date.isoformat() if self.issued_date else None,
            'valid_until': self.valid_until.isoformat() if self.valid_until else None,
            'template_name': self.template_name,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class QuoteItem(Base):
    __tablename__ = 'quote_items'

    id = Column(Integer, primary_key=True, autoincrement=True)
    quote_id = Column(Integer, ForeignKey('quotes.id'), nullable=False)
    description = Column(String(500), nullable=False)
    quantity = Column(Float, default=1)
    unit_price = Column(Float, default=0)
    total = Column(Float, default=0)
    sort_order = Column(Integer, default=0)

    quote = relationship("Quote", back_populates="items")

    def to_dict(self):
        return {
            'id': self.id,
            'description': self.description,
            'quantity': self.quantity,
            'unit_price': self.unit_price,
            'total': self.total,
            'sort_order': self.sort_order
        }
