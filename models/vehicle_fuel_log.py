"""Vehicle Fuel Log — tracks fill-ups with MPG calculation."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


FUEL_PAYMENT_METHODS = [
    ('company_card', 'Company Card'), ('personal_card', 'Personal Card'),
    ('fuel_card', 'Fuel Card'), ('cash', 'Cash'),
]

PAYMENT_LABELS = dict(FUEL_PAYMENT_METHODS)


class VehicleFuelLog(Base):
    __tablename__ = 'vehicle_fuel_logs'

    id = Column(Integer, primary_key=True)
    vehicle_id = Column(Integer, ForeignKey('equipment.id'), nullable=False, index=True)
    date = Column(Date, nullable=False)

    # Fuel data
    odometer_reading = Column(Integer, nullable=False)
    gallons = Column(Float, nullable=False)
    price_per_gallon = Column(Float, nullable=False)
    fuel_type = Column(String(20), nullable=True)
    station = Column(String(100), nullable=True)
    is_full_tank = Column(Boolean, default=True)

    # Payment
    payment_method = Column(String(20), default='company_card')

    # Computed / stored
    mpg_calculated = Column(Float, nullable=True)

    # Links
    receipt_document_id = Column(Integer, ForeignKey('documents.id'), nullable=True)
    expense_id = Column(Integer, ForeignKey('expenses.id'), nullable=True)
    technician_id = Column(Integer, ForeignKey('technicians.id'), nullable=False)
    notes = Column(Text, nullable=True)

    # Audit
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    vehicle = relationship('Equipment', foreign_keys=[vehicle_id])
    technician = relationship('Technician', foreign_keys=[technician_id])
    expense = relationship('Expense', foreign_keys=[expense_id])
    receipt_document = relationship('Document', foreign_keys=[receipt_document_id])
    created_by_user = relationship('User', foreign_keys=[created_by])

    @property
    def total_cost(self):
        if self.gallons is not None and self.price_per_gallon is not None:
            return round(float(self.gallons) * float(self.price_per_gallon), 2)
        return 0.0

    @property
    def payment_method_label(self):
        return PAYMENT_LABELS.get(self.payment_method, self.payment_method)

    def to_dict(self):
        return {
            'id': self.id, 'vehicle_id': self.vehicle_id,
            'date': self.date.isoformat() if self.date else None,
            'odometer_reading': self.odometer_reading,
            'gallons': self.gallons, 'price_per_gallon': self.price_per_gallon,
            'total_cost': self.total_cost, 'fuel_type': self.fuel_type,
            'station': self.station, 'is_full_tank': self.is_full_tank,
            'payment_method': self.payment_method,
            'mpg_calculated': self.mpg_calculated,
            'technician_id': self.technician_id,
        }
