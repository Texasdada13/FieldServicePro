"""Equipment and asset tracking model."""
from datetime import datetime, date
from sqlalchemy import Column, Integer, String, Text, Float, Boolean, Date, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from .database import Base


class Equipment(Base):
    __tablename__ = 'equipment'

    id                = Column(Integer, primary_key=True)
    organization_id   = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    name              = Column(String(200), nullable=False)
    equipment_type    = Column(String(50), nullable=False, default='tool')
    # Types: vehicle, heavy_equipment, power_tool, specialty, safety, other
    make              = Column(String(100), nullable=True)
    model             = Column(String(100), nullable=True)
    year              = Column(Integer, nullable=True)
    serial_number     = Column(String(100), nullable=True)
    identifier        = Column(String(100), nullable=True)  # VIN, asset tag, etc.

    status            = Column(String(30), nullable=False, default='available')
    # Statuses: available, assigned, in_maintenance, out_of_service, retired

    division_id       = Column(Integer, ForeignKey('divisions.id'), nullable=True)
    daily_rate        = Column(Float, nullable=True)
    hourly_rate       = Column(Float, nullable=True)

    last_maintenance  = Column(Date, nullable=True)
    next_maintenance  = Column(Date, nullable=True)
    warranty_expiry   = Column(Date, nullable=True)

    notes             = Column(Text, nullable=True)
    is_active         = Column(Boolean, default=True)
    created_at        = Column(DateTime, default=datetime.utcnow)
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    division = relationship('Division', backref='equipment')

    TYPE_CHOICES = [
        ('vehicle', 'Vehicle'), ('heavy_equipment', 'Heavy Equipment'),
        ('power_tool', 'Power Tool'), ('specialty', 'Specialty'),
        ('safety', 'Safety'), ('other', 'Other'),
    ]

    STATUS_CHOICES = [
        ('available', 'Available'), ('assigned', 'Assigned'),
        ('in_maintenance', 'In Maintenance'), ('out_of_service', 'Out of Service'),
        ('retired', 'Retired'),
    ]

    STATUS_COLORS = {
        'available': 'success', 'assigned': 'accent',
        'in_maintenance': 'warning', 'out_of_service': 'danger',
        'retired': 'secondary',
    }

    @property
    def type_display(self):
        return dict(self.TYPE_CHOICES).get(self.equipment_type, self.equipment_type)

    @property
    def status_display(self):
        return dict(self.STATUS_CHOICES).get(self.status, self.status)

    @property
    def status_color(self):
        return self.STATUS_COLORS.get(self.status, 'secondary')

    @property
    def make_model(self):
        parts = [self.make or '', self.model or '']
        return ' '.join(p for p in parts if p) or ''

    @property
    def maintenance_overdue(self):
        if self.next_maintenance and self.next_maintenance < date.today():
            return True
        return False

    def to_dict(self):
        return {
            'id': self.id, 'name': self.name,
            'equipment_type': self.equipment_type, 'status': self.status,
            'make': self.make, 'model': self.model,
            'serial_number': self.serial_number, 'identifier': self.identifier,
        }
