"""SLA (Service Level Agreement) model."""

from datetime import datetime, timedelta
import enum
from sqlalchemy import (
    Column, Integer, String, Text, Boolean, Float, DateTime,
    ForeignKey, Enum as SAEnum
)
from sqlalchemy.orm import relationship
from .database import Base
from .contract import contract_sla


class PriorityLevel(str, enum.Enum):
    emergency = "emergency"
    high      = "high"
    medium    = "medium"
    low       = "low"


class SLA(Base):
    __tablename__ = 'slas'

    id                    = Column(Integer, primary_key=True)
    organization_id       = Column(Integer, ForeignKey('organizations.id'), nullable=True)
    sla_name              = Column(String(255), nullable=False)
    priority_level        = Column(SAEnum(PriorityLevel), nullable=False)
    response_time_hours   = Column(Float, nullable=False)
    resolution_time_hours = Column(Float, nullable=True)
    business_hours_only   = Column(Boolean, default=True, nullable=False)
    business_hours_start  = Column(String(5), default='08:00', nullable=False)
    business_hours_end    = Column(String(5), default='17:00', nullable=False)
    business_days         = Column(String(50),
                                   default='mon,tue,wed,thu,fri', nullable=False)
    penalties             = Column(Text, nullable=True)
    is_active             = Column(Boolean, default=True, nullable=False)
    created_at            = Column(DateTime, default=datetime.utcnow)
    updated_at            = Column(DateTime, default=datetime.utcnow,
                                   onupdate=datetime.utcnow)

    # -- Relationships --
    contracts = relationship('Contract', secondary=contract_sla,
                              back_populates='slas', lazy='select')

    @property
    def priority_badge_class(self):
        return {
            PriorityLevel.emergency: 'danger',
            PriorityLevel.high:      'warning',
            PriorityLevel.medium:    'primary',
            PriorityLevel.low:       'secondary',
        }.get(self.priority_level, 'secondary')

    @property
    def priority_level_value(self):
        if isinstance(self.priority_level, PriorityLevel):
            return self.priority_level.value
        return self.priority_level

    @property
    def business_days_list(self):
        return [d.strip() for d in self.business_days.split(',')]

    def calculate_deadline(self, start_dt, hours):
        """
        Calculate deadline from start_dt given hours budget.
        Respects business_hours_only flag.
        Returns a datetime.
        """
        if not self.business_hours_only:
            return start_dt + timedelta(hours=hours)

        from datetime import time as dtime
        day_map = {
            'mon': 0, 'tue': 1, 'wed': 2, 'thu': 3,
            'fri': 4, 'sat': 5, 'sun': 6
        }
        biz_days = {day_map[d] for d in self.business_days_list if d in day_map}
        h_start_parts = [int(x) for x in self.business_hours_start.split(':')]
        h_end_parts   = [int(x) for x in self.business_hours_end.split(':')]
        biz_start = dtime(h_start_parts[0], h_start_parts[1])
        biz_end   = dtime(h_end_parts[0],   h_end_parts[1])

        remaining = hours
        current = start_dt

        # Advance to next business moment if needed
        while current.weekday() not in biz_days or \
              current.time() >= biz_end or \
              current.time() < biz_start:
            if current.weekday() not in biz_days or current.time() >= biz_end:
                current = current.replace(hour=h_start_parts[0],
                                          minute=h_start_parts[1],
                                          second=0, microsecond=0)
                current += timedelta(days=1)
            elif current.time() < biz_start:
                current = current.replace(hour=h_start_parts[0],
                                          minute=h_start_parts[1],
                                          second=0, microsecond=0)

        while remaining > 0:
            if current.weekday() not in biz_days:
                current = current.replace(hour=h_start_parts[0],
                                          minute=h_start_parts[1],
                                          second=0, microsecond=0)
                current += timedelta(days=1)
                continue
            end_of_day = current.replace(hour=h_end_parts[0],
                                         minute=h_end_parts[1],
                                         second=0, microsecond=0)
            avail = (end_of_day - current).total_seconds() / 3600.0
            if remaining <= avail:
                current += timedelta(hours=remaining)
                remaining = 0
            else:
                remaining -= avail
                current = current.replace(hour=h_start_parts[0],
                                          minute=h_start_parts[1],
                                          second=0, microsecond=0)
                current += timedelta(days=1)
                while current.weekday() not in biz_days:
                    current += timedelta(days=1)
        return current

    def to_dict(self):
        return {
            'id': self.id,
            'sla_name': self.sla_name,
            'priority_level': self.priority_level_value,
            'response_time_hours': self.response_time_hours,
            'resolution_time_hours': self.resolution_time_hours,
            'business_hours_only': self.business_hours_only,
            'business_hours_start': self.business_hours_start,
            'business_hours_end': self.business_hours_end,
            'business_days': self.business_days,
            'penalties': self.penalties,
            'is_active': self.is_active,
            'priority_badge_class': self.priority_badge_class,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<SLA {self.sla_name} ({self.priority_level})>'
