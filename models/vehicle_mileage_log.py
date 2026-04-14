"""Vehicle Mileage Log — tracks odometer-based trip records."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


MILEAGE_PURPOSES = [
    ('job_travel', 'Job Travel'), ('parts_pickup', 'Parts Pickup'),
    ('between_jobs', 'Between Jobs'), ('commute', 'Commute'),
    ('personal', 'Personal'), ('maintenance', 'Maintenance'), ('other', 'Other'),
]

PURPOSE_LABELS = dict(MILEAGE_PURPOSES)


class VehicleMileageLog(Base):
    __tablename__ = 'vehicle_mileage_logs'

    id = Column(Integer, primary_key=True)
    vehicle_id = Column(Integer, ForeignKey('equipment.id'), nullable=False, index=True)
    date = Column(Date, nullable=False)

    # Odometer
    start_odometer = Column(Integer, nullable=False)
    end_odometer = Column(Integer, nullable=False)

    # Purpose
    purpose = Column(String(20), default='job_travel')

    # Links
    job_id = Column(Integer, ForeignKey('jobs.id'), nullable=True)
    technician_id = Column(Integer, ForeignKey('technicians.id'), nullable=False)
    expense_id = Column(Integer, ForeignKey('expenses.id'), nullable=True)

    # Locations
    start_location = Column(String(255), nullable=True)
    end_location = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)

    # Audit
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Relationships
    vehicle = relationship('Equipment', foreign_keys=[vehicle_id])
    job = relationship('Job', foreign_keys=[job_id])
    technician = relationship('Technician', foreign_keys=[technician_id])
    expense = relationship('Expense', foreign_keys=[expense_id])
    created_by_user = relationship('User', foreign_keys=[created_by])

    @property
    def miles_driven(self):
        if self.start_odometer is not None and self.end_odometer is not None:
            return max(0, self.end_odometer - self.start_odometer)
        return 0

    @property
    def purpose_label(self):
        return PURPOSE_LABELS.get(self.purpose, self.purpose)

    def to_dict(self):
        return {
            'id': self.id, 'vehicle_id': self.vehicle_id,
            'date': self.date.isoformat() if self.date else None,
            'start_odometer': self.start_odometer, 'end_odometer': self.end_odometer,
            'miles_driven': self.miles_driven, 'purpose': self.purpose,
            'purpose_label': self.purpose_label,
            'job_id': self.job_id, 'technician_id': self.technician_id,
            'start_location': self.start_location, 'end_location': self.end_location,
        }
