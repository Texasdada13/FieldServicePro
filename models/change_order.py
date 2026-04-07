"""Change Order model — tracks scope/cost/schedule changes to jobs and phases."""

from datetime import datetime
import enum
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, Date, DateTime,
    ForeignKey
)
from sqlalchemy.orm import relationship
from .database import Base


class ChangeOrderReason(str, enum.Enum):
    client_request       = "client_request"
    unforeseen_condition = "unforeseen_condition"
    design_change        = "design_change"
    regulatory           = "regulatory"
    error_correction     = "error_correction"
    other                = "other"


class ChangeOrderStatus(str, enum.Enum):
    draft            = "draft"
    submitted        = "submitted"
    pending_approval = "pending_approval"
    approved         = "approved"
    rejected         = "rejected"
    voided           = "voided"


class ChangeOrderRequestedBy(str, enum.Enum):
    client          = "client"
    field_tech      = "field_tech"
    project_manager = "project_manager"
    inspector       = "inspector"


class ChangeOrderCostType(str, enum.Enum):
    addition  = "addition"
    deduction = "deduction"
    no_change = "no_change"


class ChangeOrder(Base):
    __tablename__ = 'change_orders'

    id                      = Column(Integer, primary_key=True)
    change_order_number     = Column(String(50), unique=True, nullable=False, index=True)
    job_id                  = Column(Integer, ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, index=True)
    phase_id                = Column(Integer, ForeignKey('job_phases.id', ondelete='SET NULL'), nullable=True)
    quote_id                = Column(Integer, ForeignKey('quotes.id', ondelete='SET NULL'), nullable=True)

    title                   = Column(String(200), nullable=False)
    description             = Column(Text, nullable=False)
    reason                  = Column(String(30), nullable=False)
    status                  = Column(String(20), default=ChangeOrderStatus.draft.value, nullable=False, index=True)
    requested_by            = Column(String(20), nullable=False)
    requested_date          = Column(Date, nullable=False, default=datetime.utcnow)

    # Cost Impact
    cost_type               = Column(String(20), default=ChangeOrderCostType.addition.value, nullable=False)
    original_amount         = Column(Float, default=0)
    revised_amount          = Column(Float, default=0)
    labor_hours_impact      = Column(Float, default=0)

    # Client Approval
    requires_client_approval = Column(Boolean, default=True)
    client_approved         = Column(Boolean, nullable=True)
    client_approved_by      = Column(String(200), nullable=True)
    client_approved_date    = Column(DateTime, nullable=True)
    client_approved_by_portal_id = Column(Integer, ForeignKey('portal_users.id'), nullable=True)
    client_rejection_reason = Column(Text, nullable=True)

    # Internal Approval
    internal_approved_by_id = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    internal_approved_date  = Column(DateTime, nullable=True)
    rejection_reason        = Column(Text, nullable=True)

    # Creates new phase?
    creates_new_phase       = Column(Boolean, default=False)
    new_phase_title         = Column(String(200), nullable=True)

    created_by_id           = Column(Integer, ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    created_at              = Column(DateTime, default=datetime.utcnow)
    updated_at              = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    job                     = relationship('Job', back_populates='change_orders')
    phase                   = relationship('JobPhase', back_populates='change_orders')
    quote                   = relationship('Quote', foreign_keys=[quote_id])
    line_items              = relationship('ChangeOrderLineItem', back_populates='change_order',
                                           cascade='all, delete-orphan', order_by='ChangeOrderLineItem.id')
    internal_approved_by    = relationship('User', foreign_keys=[internal_approved_by_id])
    created_by              = relationship('User', foreign_keys=[created_by_id])

    @property
    def cost_difference(self):
        """Computed: revised - original. Negative = deduction."""
        return float(self.revised_amount or 0) - float(self.original_amount or 0)

    @property
    def status_label(self):
        labels = {
            'draft': 'Draft', 'submitted': 'Submitted',
            'pending_approval': 'Pending Approval', 'approved': 'Approved',
            'rejected': 'Rejected', 'voided': 'Voided',
        }
        return labels.get(self.status, self.status)

    @property
    def status_badge_class(self):
        classes = {
            'draft': 'secondary', 'submitted': 'active',
            'pending_approval': 'warning', 'approved': 'success',
            'rejected': 'danger', 'voided': 'draft',
        }
        return classes.get(self.status, 'secondary')

    @property
    def reason_label(self):
        labels = {
            'client_request': 'Client Request', 'unforeseen_condition': 'Unforeseen Condition',
            'design_change': 'Design Change', 'regulatory': 'Regulatory Requirement',
            'error_correction': 'Error Correction', 'other': 'Other',
        }
        return labels.get(self.reason, self.reason)

    @property
    def line_items_total(self):
        return sum(float(li.line_total or 0) * (1 if li.is_addition else -1) for li in self.line_items)

    @property
    def is_editable(self):
        return self.status in ('draft', 'submitted')

    @property
    def awaiting_approval(self):
        return self.status in ('submitted', 'pending_approval')

    @staticmethod
    def generate_number(db, job_id):
        """Generate next CO number: CO-{JOB_ID}-{SEQ}"""
        last = db.query(ChangeOrder).filter_by(job_id=job_id)\
                  .order_by(ChangeOrder.id.desc()).first()
        seq = 1
        if last and last.change_order_number:
            parts = last.change_order_number.split('-')
            if len(parts) >= 3:
                try:
                    seq = int(parts[-1]) + 1
                except ValueError:
                    pass
        return f"CO-{job_id}-{seq:03d}"

    def to_dict(self):
        return {
            'id': self.id,
            'change_order_number': self.change_order_number,
            'job_id': self.job_id,
            'phase_id': self.phase_id,
            'title': self.title,
            'description': self.description,
            'reason': self.reason,
            'reason_label': self.reason_label,
            'status': self.status,
            'status_label': self.status_label,
            'status_badge_class': self.status_badge_class,
            'requested_by': self.requested_by,
            'requested_date': self.requested_date.isoformat() if self.requested_date else None,
            'cost_type': self.cost_type,
            'original_amount': float(self.original_amount or 0),
            'revised_amount': float(self.revised_amount or 0),
            'cost_difference': self.cost_difference,
            'labor_hours_impact': float(self.labor_hours_impact or 0),
            'line_items_total': self.line_items_total,
            'requires_client_approval': self.requires_client_approval,
            'client_approved': self.client_approved,
            'client_approved_by': self.client_approved_by,
            'is_editable': self.is_editable,
            'awaiting_approval': self.awaiting_approval,
            'creates_new_phase': self.creates_new_phase,
            'new_phase_title': self.new_phase_title,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f'<ChangeOrder {self.change_order_number}: {self.title}>'


class ChangeOrderLineItem(Base):
    __tablename__ = 'change_order_line_items'

    id               = Column(Integer, primary_key=True)
    change_order_id  = Column(Integer, ForeignKey('change_orders.id', ondelete='CASCADE'),
                              nullable=False, index=True)
    description      = Column(String(500), nullable=False)
    quantity         = Column(Float, default=1)
    unit_price       = Column(Float, default=0)
    is_addition      = Column(Boolean, default=True)  # True = adding scope/cost
    created_at       = Column(DateTime, default=datetime.utcnow)

    change_order     = relationship('ChangeOrder', back_populates='line_items')

    @property
    def line_total(self):
        return float(self.quantity or 1) * float(self.unit_price or 0)

    @property
    def signed_total(self):
        """Positive for additions, negative for deductions."""
        return self.line_total if self.is_addition else -self.line_total

    def to_dict(self):
        return {
            'id': self.id,
            'description': self.description,
            'quantity': float(self.quantity or 1),
            'unit_price': float(self.unit_price or 0),
            'line_total': self.line_total,
            'signed_total': self.signed_total,
            'is_addition': self.is_addition,
        }
