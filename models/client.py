"""Client, Property, and Contact models."""

from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from .database import Base


class Client(Base):
    __tablename__ = 'clients'

    id = Column(Integer, primary_key=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)

    # Client type
    client_type = Column(String(20), default='commercial')  # commercial, residential

    # Company info (for commercial clients)
    company_name = Column(String(255))
    # Person info (for residential, or primary contact for commercial)
    first_name = Column(String(100))
    last_name = Column(String(100))

    email = Column(String(255))
    phone = Column(String(50))
    mobile = Column(String(50))

    # Billing address
    billing_address = Column(String(500))
    billing_city = Column(String(100))
    billing_province = Column(String(100))
    billing_postal_code = Column(String(20))

    notes = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    properties = relationship("Property", back_populates="client", cascade="all, delete-orphan")
    contacts = relationship("ClientContact", back_populates="client", cascade="all, delete-orphan")
    client_notes = relationship("ClientNote", back_populates="client", cascade="all, delete-orphan")
    communications = relationship("ClientCommunication", back_populates="client", cascade="all, delete-orphan")
    jobs = relationship("Job", back_populates="client")
    quotes = relationship("Quote", back_populates="client")
    invoices = relationship("Invoice", back_populates="client")

    @property
    def display_name(self):
        if self.client_type == 'commercial' and self.company_name:
            return self.company_name
        parts = [self.first_name or '', self.last_name or '']
        return ' '.join(p for p in parts if p) or self.email or f'Client #{self.id}'

    def to_dict(self):
        return {
            'id': self.id,
            'client_type': self.client_type,
            'company_name': self.company_name,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'display_name': self.display_name,
            'email': self.email,
            'phone': self.phone,
            'billing_city': self.billing_city,
            'is_active': self.is_active,
            'property_count': len(self.properties) if self.properties else 0,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Property(Base):
    __tablename__ = 'properties'

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    name = Column(String(255))  # e.g. "123 Main St" or "Kingsley Tower A"
    address = Column(String(500), nullable=False)
    city = Column(String(100))
    province = Column(String(100))
    postal_code = Column(String(20))
    unit_number = Column(String(50))
    property_type = Column(String(50))  # residential, commercial, condo, industrial
    notes = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="properties")
    jobs = relationship("Job", back_populates="property")
    quotes = relationship("Quote", back_populates="property")

    @property
    def display_address(self):
        parts = []
        if self.unit_number:
            parts.append(f"Unit {self.unit_number},")
        parts.append(self.address or '')
        if self.city:
            parts.append(f", {self.city}")
        return ' '.join(parts)

    def to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'name': self.name,
            'address': self.address,
            'city': self.city,
            'province': self.province,
            'postal_code': self.postal_code,
            'unit_number': self.unit_number,
            'property_type': self.property_type,
            'display_address': self.display_address,
            'notes': self.notes
        }


class ClientContact(Base):
    __tablename__ = 'client_contacts'

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100))
    title = Column(String(100))  # e.g. "Property Manager", "Building Super"
    email = Column(String(255))
    phone = Column(String(50))
    mobile = Column(String(50))
    is_primary = Column(Boolean, default=False)
    notes = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="contacts")

    def to_dict(self):
        return {
            'id': self.id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'title': self.title,
            'email': self.email,
            'phone': self.phone,
            'is_primary': self.is_primary
        }


class ClientNote(Base):
    __tablename__ = 'client_notes'

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'))
    content = Column(Text, nullable=False)
    is_starred = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    client = relationship("Client", back_populates="client_notes")

    def to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'user_id': self.user_id,
            'content': self.content,
            'is_starred': self.is_starred,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }


class ClientCommunication(Base):
    __tablename__ = 'client_communications'

    id = Column(Integer, primary_key=True, autoincrement=True)
    client_id = Column(Integer, ForeignKey('clients.id'), nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'))
    comm_type = Column(String(20), default='email')  # email, phone, text, in_person
    direction = Column(String(10), default='outbound')  # outbound, inbound
    subject = Column(String(500))
    body = Column(Text)
    recipient_email = Column(String(255))
    status = Column(String(20), default='sent')  # draft, sent, delivered, opened, failed
    related_job_id = Column(Integer, ForeignKey('jobs.id'))
    related_invoice_id = Column(Integer, ForeignKey('invoices.id'))
    sent_at = Column(DateTime)
    opened_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)

    client = relationship("Client", back_populates="communications")

    def to_dict(self):
        return {
            'id': self.id,
            'client_id': self.client_id,
            'user_id': self.user_id,
            'comm_type': self.comm_type,
            'direction': self.direction,
            'subject': self.subject,
            'body': self.body,
            'recipient_email': self.recipient_email,
            'status': self.status,
            'related_job_id': self.related_job_id,
            'related_invoice_id': self.related_invoice_id,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'opened_at': self.opened_at.isoformat() if self.opened_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
