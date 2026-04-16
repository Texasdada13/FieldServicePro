"""TechPerformanceScore — composite performance scores per technician per period."""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, Date, DateTime,
    ForeignKey, Text, Boolean, UniqueConstraint
)
from sqlalchemy.orm import relationship
from .database import Base


class TechPerformanceScore(Base):
    __tablename__ = 'tech_performance_scores'

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    technician_id = Column(Integer, ForeignKey('technicians.id'), nullable=False)

    # Period: weekly | monthly | quarterly
    period_type = Column(String(20), nullable=False)
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    # Composite score (0-100)
    overall_score = Column(Float, nullable=False, default=0.0)

    # Component scores (each 0-100)
    customer_rating_score = Column(Float, default=0.0)
    completion_rate_score = Column(Float, default=0.0)
    callback_rate_score = Column(Float, default=0.0)
    utilization_score = Column(Float, default=0.0)
    revenue_score = Column(Float, default=0.0)
    efficiency_score = Column(Float, default=0.0)
    profitability_score = Column(Float, default=0.0)

    # Ranking
    rank = Column(Integer, nullable=True)

    # Raw metrics
    jobs_completed = Column(Integer, default=0)
    jobs_total = Column(Integer, default=0)
    total_hours = Column(Float, default=0.0)
    billable_hours = Column(Float, default=0.0)
    total_revenue = Column(Float, default=0.0)
    total_callbacks = Column(Integer, default=0)
    avg_customer_rating = Column(Float, default=0.0)
    avg_job_margin = Column(Float, default=0.0)

    # Metadata
    calculated_at = Column(DateTime, default=datetime.utcnow)
    score_version = Column(Integer, default=1)

    technician = relationship('Technician', back_populates='performance_scores')

    __table_args__ = (
        UniqueConstraint(
            'organization_id', 'technician_id', 'period_type', 'period_start',
            name='uq_tech_score_period'
        ),
    )

    @property
    def completion_rate(self):
        return (self.jobs_completed / self.jobs_total * 100) if self.jobs_total else 0.0

    @property
    def callback_rate(self):
        return (self.total_callbacks / self.jobs_completed * 100) if self.jobs_completed else 0.0

    @property
    def utilization_rate(self):
        return (self.billable_hours / self.total_hours * 100) if self.total_hours else 0.0

    def to_dict(self):
        return {
            'id': self.id,
            'technician_id': self.technician_id,
            'tech_name': self.technician.full_name if self.technician else 'Unknown',
            'period_type': self.period_type,
            'period_start': self.period_start.isoformat(),
            'period_end': self.period_end.isoformat(),
            'overall_score': round(self.overall_score, 1),
            'customer_rating_score': round(self.customer_rating_score or 0, 1),
            'completion_rate_score': round(self.completion_rate_score or 0, 1),
            'callback_rate_score': round(self.callback_rate_score or 0, 1),
            'utilization_score': round(self.utilization_score or 0, 1),
            'revenue_score': round(self.revenue_score or 0, 1),
            'efficiency_score': round(self.efficiency_score or 0, 1),
            'profitability_score': round(self.profitability_score or 0, 1),
            'rank': self.rank,
            'jobs_completed': self.jobs_completed,
            'jobs_total': self.jobs_total,
            'total_hours': round(self.total_hours or 0, 1),
            'billable_hours': round(self.billable_hours or 0, 1),
            'total_revenue': round(self.total_revenue or 0, 2),
            'total_callbacks': self.total_callbacks,
            'avg_customer_rating': round(self.avg_customer_rating or 0, 2),
            'avg_job_margin': round(self.avg_job_margin or 0, 2),
            'completion_rate': round(self.completion_rate, 1),
            'callback_rate': round(self.callback_rate, 2),
            'utilization_rate': round(self.utilization_rate, 1),
        }


class TechAchievement(Base):
    __tablename__ = 'tech_achievements'

    id = Column(Integer, primary_key=True)
    organization_id = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    technician_id = Column(Integer, ForeignKey('technicians.id'), nullable=False)

    achievement_type = Column(String(50), nullable=False)
    achievement_name = Column(String(100), nullable=False)
    description = Column(Text)
    icon = Column(String(50))

    period_type = Column(String(20), nullable=True)
    period_start = Column(Date, nullable=True)
    period_end = Column(Date, nullable=True)

    earned_at = Column(DateTime, default=datetime.utcnow)
    notified = Column(Boolean, default=False)

    technician = relationship('Technician', back_populates='achievements')

    def to_dict(self):
        return {
            'id': self.id,
            'achievement_type': self.achievement_type,
            'achievement_name': self.achievement_name,
            'description': self.description,
            'icon': self.icon,
            'earned_at': self.earned_at.isoformat() if self.earned_at else None,
        }


ACHIEVEMENT_DEFINITIONS = {
    'perfect_stars': {'name': 'Perfect 5 Stars', 'description': 'Received a 5-star review', 'icon': '\u2b50'},
    'zero_callbacks': {'name': 'Zero Callbacks', 'description': 'No callbacks this month', 'icon': '\U0001f3af'},
    'revenue_king': {'name': 'Revenue King', 'description': 'Highest revenue this month', 'icon': '\U0001f451'},
    'iron_horse': {'name': 'Iron Horse', 'description': 'Most hours logged this month', 'icon': '\U0001f3c7'},
    'speed_demon': {'name': 'Speed Demon', 'description': 'Fastest avg job completion', 'icon': '\u26a1'},
    'customer_favorite': {'name': 'Customer Favorite', 'description': 'Highest avg customer rating', 'icon': '\u2764\ufe0f'},
    'most_improved': {'name': 'Most Improved', 'description': 'Largest score increase', 'icon': '\U0001f4c8'},
    'consistency_streak': {'name': 'Consistency Streak', 'description': '3+ months above 80', 'icon': '\U0001f525'},
}
