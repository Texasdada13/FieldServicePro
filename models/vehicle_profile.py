"""Vehicle Profile — extends Equipment for vehicles with fleet-specific data."""
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, Float, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


FUEL_TYPES = [
    ('gasoline', 'Gasoline'), ('diesel', 'Diesel'), ('electric', 'Electric'),
    ('hybrid', 'Hybrid'), ('propane', 'Propane'),
]


class VehicleProfile(Base):
    __tablename__ = 'vehicle_profiles'

    id = Column(Integer, primary_key=True)
    equipment_id = Column(Integer, ForeignKey('equipment.id'), unique=True, nullable=False)

    # Identity
    license_plate = Column(String(20), nullable=True)
    vin = Column(String(17), nullable=True)
    make = Column(String(50), nullable=True)
    model = Column(String(50), nullable=True)
    year = Column(Integer, nullable=True)
    color = Column(String(30), nullable=True)

    # Registration & Insurance
    registration_expiry = Column(Date, nullable=True)
    insurance_policy_number = Column(String(100), nullable=True)
    insurance_expiry = Column(Date, nullable=True)

    # Odometer / Fuel
    current_odometer = Column(Integer, default=0)
    fuel_type = Column(String(20), default='gasoline')
    fuel_tank_capacity = Column(Float, nullable=True)
    average_mpg = Column(Float, nullable=True)

    # Assignment
    assigned_technician_id = Column(Integer, ForeignKey('technicians.id'), nullable=True)

    # Logistics
    home_base_address = Column(String(255), nullable=True)
    ez_pass_number = Column(String(50), nullable=True)
    gps_tracker_id = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    equipment = relationship('Equipment', back_populates='vehicle_profile')
    assigned_technician = relationship('Technician', foreign_keys=[assigned_technician_id])

    # ── Computed helpers ─────────────────────────────────────────────────

    @property
    def registration_days_until_expiry(self):
        if self.registration_expiry:
            return (self.registration_expiry - date.today()).days
        return None

    @property
    def insurance_days_until_expiry(self):
        if self.insurance_expiry:
            return (self.insurance_expiry - date.today()).days
        return None

    @property
    def registration_status(self):
        days = self.registration_days_until_expiry
        if days is None:
            return 'unknown'
        if days < 0:
            return 'expired'
        if days <= 30:
            return 'expiring_soon'
        return 'valid'

    @property
    def insurance_status(self):
        days = self.insurance_days_until_expiry
        if days is None:
            return 'unknown'
        if days < 0:
            return 'expired'
        if days <= 30:
            return 'expiring_soon'
        return 'valid'

    @property
    def display_name(self):
        parts = []
        if self.year:
            parts.append(str(self.year))
        if self.make:
            parts.append(self.make)
        if self.model:
            parts.append(self.model)
        if self.license_plate:
            parts.append(f'({self.license_plate})')
        if parts:
            return ' '.join(parts)
        return self.equipment.name if self.equipment else f'Vehicle #{self.id}'

    def to_dict(self):
        return {
            'id': self.id, 'equipment_id': self.equipment_id,
            'license_plate': self.license_plate, 'vin': self.vin,
            'make': self.make, 'model': self.model, 'year': self.year,
            'color': self.color, 'current_odometer': self.current_odometer,
            'fuel_type': self.fuel_type, 'average_mpg': self.average_mpg,
            'registration_status': self.registration_status,
            'insurance_status': self.insurance_status,
            'display_name': self.display_name,
            'assigned_technician_id': self.assigned_technician_id,
        }
