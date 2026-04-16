"""Vendor model — supplier and subcontractor management."""
import json
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


VENDOR_TYPES = [
    ('parts_supplier', 'Parts Supplier'), ('equipment_rental', 'Equipment Rental'),
    ('subcontractor', 'Subcontractor'), ('professional_services', 'Professional Services'),
    ('waste_disposal', 'Waste Disposal'), ('fuel', 'Fuel'),
    ('office_supplies', 'Office Supplies'), ('utilities', 'Utilities'),
    ('insurance', 'Insurance'), ('other', 'Other'),
]

VENDOR_STATUSES = [
    ('active', 'Active'), ('preferred', 'Preferred'), ('on_hold', 'On Hold'),
    ('inactive', 'Inactive'), ('blacklisted', 'Blacklisted'),
]

PAYMENT_TERMS = [
    ('due_on_receipt', 'Due on Receipt'), ('net_15', 'Net 15'), ('net_30', 'Net 30'),
    ('net_45', 'Net 45'), ('net_60', 'Net 60'), ('net_90', 'Net 90'), ('custom', 'Custom'),
]

STATUS_COLORS = {
    'active': 'success', 'preferred': 'accent', 'on_hold': 'warning',
    'inactive': 'secondary', 'blacklisted': 'danger',
}


class Vendor(Base):
    __tablename__ = 'vendors'

    id = Column(Integer, primary_key=True)
    vendor_number = Column(String(20), unique=True, nullable=False, index=True)
    company_name = Column(String(200), nullable=False)
    doing_business_as = Column(String(200), nullable=True)
    vendor_type = Column(String(50), nullable=False, default='parts_supplier')
    _trade_categories = Column('trade_categories', Text, nullable=True)
    status = Column(String(20), nullable=False, default='active')

    # Primary Contact
    contact_name = Column(String(100), nullable=True)
    contact_title = Column(String(100), nullable=True)
    contact_email = Column(String(200), nullable=True)
    contact_phone = Column(String(30), nullable=True)

    # Company Info
    phone = Column(String(30), nullable=True)
    email = Column(String(200), nullable=True)
    website = Column(String(300), nullable=True)
    address_line1 = Column(String(200), nullable=True)
    address_line2 = Column(String(200), nullable=True)
    city = Column(String(100), nullable=True)
    state_province = Column(String(100), nullable=True)
    postal_code = Column(String(20), nullable=True)
    country = Column(String(100), nullable=False, default='Canada')

    # Financial
    payment_terms = Column(String(30), nullable=False, default='net_30')
    custom_payment_days = Column(Integer, nullable=True)
    tax_id = Column(String(50), nullable=True)
    currency = Column(String(10), nullable=False, default='CAD')
    credit_limit = Column(Float, nullable=True)
    current_balance = Column(Float, nullable=False, default=0)
    default_markup = Column(Float, nullable=True)
    account_number = Column(String(100), nullable=True)

    # Sales Rep
    sales_rep_name = Column(String(100), nullable=True)
    sales_rep_phone = Column(String(30), nullable=True)
    sales_rep_email = Column(String(200), nullable=True)

    # Ratings (1-5)
    quality_rating = Column(Integer, nullable=True)
    delivery_rating = Column(Integer, nullable=True)
    price_rating = Column(Integer, nullable=True)
    rating_notes = Column(Text, nullable=True)

    # Compliance
    insurance_verified = Column(Boolean, nullable=False, default=False)
    insurance_expiry = Column(Date, nullable=True)
    wsib_verified = Column(Boolean, nullable=False, default=False)
    wsib_number = Column(String(50), nullable=True)
    liability_coverage = Column(Float, nullable=True)
    certifications = Column(Text, nullable=True)

    # Metadata
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    division_id = Column(Integer, ForeignKey('divisions.id'), nullable=True)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    division = relationship('Division', backref='vendors')
    creator = relationship('User', foreign_keys=[created_by])

    @property
    def trade_categories(self):
        if self._trade_categories:
            try:
                return json.loads(self._trade_categories)
            except (ValueError, TypeError):
                return []
        return []

    @trade_categories.setter
    def trade_categories(self, value):
        self._trade_categories = json.dumps(value) if isinstance(value, list) else value

    @property
    def overall_rating(self):
        ratings = [r for r in [self.quality_rating, self.delivery_rating, self.price_rating] if r]
        return round(sum(ratings) / len(ratings), 1) if ratings else None

    @property
    def payment_days(self):
        return {'due_on_receipt': 0, 'net_15': 15, 'net_30': 30, 'net_45': 45,
                'net_60': 60, 'net_90': 90, 'custom': self.custom_payment_days or 30
                }.get(self.payment_terms, 30)

    @property
    def display_name(self):
        return f"{self.company_name} ({self.doing_business_as})" if self.doing_business_as else self.company_name

    @property
    def status_color(self):
        return STATUS_COLORS.get(self.status, 'secondary')

    @staticmethod
    def generate_vendor_number(db):
        from sqlalchemy import func
        year = date.today().year
        last = db.query(Vendor).filter(
            Vendor.vendor_number.like(f'VND-{year}-%')
        ).order_by(Vendor.vendor_number.desc()).first()
        seq = int(last.vendor_number.split('-')[-1]) + 1 if last else 1
        return f"VND-{year}-{seq:04d}"

    def to_dict(self):
        return {
            'id': self.id, 'vendor_number': self.vendor_number,
            'company_name': self.company_name, 'display_name': self.display_name,
            'vendor_type': self.vendor_type, 'status': self.status,
            'payment_terms': self.payment_terms, 'overall_rating': self.overall_rating,
            'current_balance': float(self.current_balance or 0),
        }
