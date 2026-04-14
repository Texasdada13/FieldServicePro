"""Part / Material catalog model."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, Index
)
from sqlalchemy.orm import relationship
from .database import Base


# String constants for categories
PART_CATEGORIES = [
    ('pipe_fittings', 'Pipe & Fittings'), ('valves', 'Valves'),
    ('electrical', 'Electrical'), ('hvac_components', 'HVAC Components'),
    ('fixtures', 'Fixtures'), ('fasteners', 'Fasteners'),
    ('adhesives_sealants', 'Adhesives & Sealants'), ('wire_cable', 'Wire & Cable'),
    ('ductwork', 'Ductwork'), ('controls_thermostats', 'Controls & Thermostats'),
    ('safety', 'Safety'), ('tools_consumables', 'Tools & Consumables'),
    ('other', 'Other'),
]

PART_TRADES = [
    ('plumbing', 'Plumbing'), ('hvac', 'HVAC'), ('electrical', 'Electrical'),
    ('general', 'General'), ('multi', 'Multi-Trade'),
]

UNIT_TYPES = [
    ('each', 'Each'), ('foot', 'Foot'), ('meter', 'Meter'), ('roll', 'Roll'),
    ('box', 'Box'), ('bag', 'Bag'), ('gallon', 'Gallon'), ('pair', 'Pair'),
    ('set', 'Set'), ('kit', 'Kit'), ('pound', 'Pound'), ('sheet', 'Sheet'),
]


class Part(Base):
    __tablename__ = 'parts'

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)

    # Identification
    part_number = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(30), nullable=False, default='other')
    subcategory = Column(String(50), nullable=True)
    trade = Column(String(20), nullable=False, default='general')

    # Supplier / manufacturer
    manufacturer = Column(String(200), nullable=True)
    manufacturer_part_number = Column(String(100), nullable=True)
    preferred_vendor_name = Column(String(200), nullable=True)
    supplier_part_number = Column(String(100), nullable=True)

    # Units & pricing
    unit_of_measure = Column(String(20), nullable=False, default='each')
    cost_price = Column(Float, nullable=False, default=0)
    markup_percentage = Column(Float, nullable=False, default=0)
    sell_price = Column(Float, nullable=False, default=0)

    # Inventory
    minimum_stock_level = Column(Integer, nullable=False, default=0)
    reorder_quantity = Column(Integer, nullable=False, default=0)
    max_stock_level = Column(Integer, nullable=True)

    # Status
    is_active = Column(Boolean, nullable=False, default=True)
    is_serialized = Column(Boolean, nullable=False, default=False)
    taxable = Column(Boolean, nullable=False, default=True)

    # Metadata
    barcode = Column(String(100), nullable=True, index=True)
    notes = Column(Text, nullable=True)
    image_url = Column(String(500), nullable=True)
    weight = Column(Float, nullable=True)
    weight_unit = Column(String(10), nullable=True)  # lb, kg

    created_by = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    inventory_stocks = relationship('InventoryStock', back_populates='part', cascade='all, delete-orphan')
    job_materials = relationship('JobMaterial', back_populates='part')
    transactions = relationship('InventoryTransaction', back_populates='part')

    __table_args__ = (
        Index('ix_parts_org_category', 'organization_id', 'category'),
        Index('ix_parts_org_active', 'organization_id', 'is_active'),
    )

    @property
    def category_display(self):
        return dict(PART_CATEGORIES).get(self.category, self.category.replace('_', ' ').title())

    @property
    def trade_display(self):
        return dict(PART_TRADES).get(self.trade, self.trade.title())

    @property
    def unit_display(self):
        return dict(UNIT_TYPES).get(self.unit_of_measure, self.unit_of_measure)

    @property
    def total_stock(self):
        """Sum of all location stocks."""
        return sum(s.quantity_on_hand for s in self.inventory_stocks)

    @property
    def is_low_stock(self):
        return self.minimum_stock_level > 0 and self.total_stock <= self.minimum_stock_level

    @property
    def is_out_of_stock(self):
        return self.total_stock <= 0

    @property
    def effective_sell_price(self):
        """Sell price, or computed from cost + markup."""
        if self.sell_price and self.sell_price > 0:
            return self.sell_price
        if self.cost_price and self.markup_percentage:
            return round(self.cost_price * (1 + self.markup_percentage / 100), 2)
        return self.cost_price or 0

    def to_dict(self):
        return {
            'id': self.id,
            'part_number': self.part_number,
            'name': self.name,
            'description': self.description,
            'category': self.category,
            'category_display': self.category_display,
            'trade': self.trade,
            'trade_display': self.trade_display,
            'manufacturer': self.manufacturer,
            'unit_of_measure': self.unit_of_measure,
            'unit_display': self.unit_display,
            'cost_price': self.cost_price,
            'sell_price': self.sell_price,
            'markup_percentage': self.markup_percentage,
            'minimum_stock_level': self.minimum_stock_level,
            'total_stock': self.total_stock,
            'is_active': self.is_active,
            'is_low_stock': self.is_low_stock,
            'barcode': self.barcode,
        }
