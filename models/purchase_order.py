"""Purchase Order model."""

from datetime import datetime, date
import enum
from sqlalchemy import (
    Column, Integer, String, Text, Float, Boolean, Date, DateTime,
    ForeignKey
)
from sqlalchemy.orm import relationship
from .database import Base


class POStatus(str, enum.Enum):
    active    = "active"
    exhausted = "exhausted"
    expired   = "expired"
    cancelled = "cancelled"


class PurchaseOrder(Base):
    __tablename__ = 'purchase_orders'

    id                = Column(Integer, primary_key=True)
    organization_id   = Column(Integer, ForeignKey('organizations.id'), nullable=False)
    po_number         = Column(String(100), nullable=False, index=True)
    client_id         = Column(Integer, ForeignKey('clients.id'), nullable=False)
    contract_id       = Column(Integer, ForeignKey('contracts.id'), nullable=True)
    project_id        = Column(Integer, ForeignKey('projects.id'), nullable=True, index=True)

    description       = Column(Text, nullable=True)
    status            = Column(String(20), nullable=False, default=POStatus.active.value, index=True)

    amount_authorized = Column(Float, nullable=False, default=0)
    amount_used       = Column(Float, nullable=False, default=0)

    issue_date        = Column(Date, nullable=False, default=date.today)
    expiry_date       = Column(Date, nullable=True)

    department        = Column(String(100), nullable=True)
    cost_code         = Column(String(100), nullable=True)
    notes             = Column(Text, nullable=True)

    created_by        = Column(Integer, ForeignKey('users.id'), nullable=True)
    updated_by        = Column(Integer, ForeignKey('users.id'), nullable=True)
    created_at        = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at        = Column(DateTime, default=datetime.utcnow,
                               onupdate=datetime.utcnow, nullable=False)

    # Relationships
    client    = relationship('Client', back_populates='purchase_orders')
    contract  = relationship('Contract', backref='purchase_orders')
    invoices  = relationship('Invoice', back_populates='purchase_order')
    creator   = relationship('User', foreign_keys=[created_by])
    project   = relationship('Project', backref='purchase_orders', foreign_keys=[project_id])
    updater   = relationship('User', foreign_keys=[updated_by])
    attachments = relationship('POAttachment', back_populates='purchase_order',
                                cascade='all, delete-orphan', lazy='select')

    @property
    def amount_remaining(self):
        return float(self.amount_authorized or 0) - float(self.amount_used or 0)

    @property
    def utilization_percentage(self):
        auth = float(self.amount_authorized or 0)
        if auth == 0:
            return 0
        return min(100, (float(self.amount_used or 0) / auth) * 100)

    @property
    def is_expired(self):
        if self.expiry_date and date.today() > self.expiry_date:
            return True
        return False

    @property
    def is_available(self):
        """Returns True if PO can accept new invoice charges."""
        if self.status != POStatus.active.value:
            return False
        if self.is_expired:
            return False
        return True

    @property
    def status_badge_class(self):
        return {
            'active': 'success',
            'exhausted': 'warning',
            'expired': 'danger',
            'cancelled': 'secondary',
        }.get(self.status, 'secondary')

    def check_and_update_status(self):
        """Auto-update status based on balance and expiry."""
        if self.status == POStatus.cancelled.value:
            return
        if self.is_expired and self.status == POStatus.active.value:
            self.status = POStatus.expired.value
        elif self.amount_remaining <= 0 and self.status == POStatus.active.value:
            self.status = POStatus.exhausted.value
        elif self.amount_remaining > 0 and not self.is_expired:
            if self.status in (POStatus.exhausted.value, POStatus.expired.value):
                self.status = POStatus.active.value

    def recalculate_amount_used(self):
        """Recalculate amount_used from linked invoices (non-void)."""
        total = sum(
            float(inv.total or 0)
            for inv in self.invoices
            if inv.status not in ('void', 'cancelled')
        )
        self.amount_used = total
        self.check_and_update_status()

    def can_accommodate(self, amount):
        """Check if PO can accommodate an additional amount."""
        if not self.is_available:
            return False, f"PO {self.po_number} is {self.status} and cannot accept new charges."
        if float(amount) > self.amount_remaining:
            return False, (
                f"Invoice amount ${float(amount):,.2f} exceeds PO remaining balance "
                f"${self.amount_remaining:,.2f}."
            )
        return True, None

    def to_dict(self):
        return {
            'id': self.id,
            'po_number': self.po_number,
            'client_id': self.client_id,
            'contract_id': self.contract_id,
            'description': self.description,
            'status': self.status,
            'amount_authorized': float(self.amount_authorized or 0),
            'amount_used': float(self.amount_used or 0),
            'amount_remaining': self.amount_remaining,
            'utilization_percentage': self.utilization_percentage,
            'issue_date': self.issue_date.isoformat() if self.issue_date else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'department': self.department,
            'cost_code': self.cost_code,
            'notes': self.notes,
            'is_available': self.is_available,
            'status_badge_class': self.status_badge_class,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }

    def to_selector_dict(self):
        """Serializable dict for the invoice form PO selector JS."""
        return {
            'id': self.id,
            'po_number': self.po_number,
            'description': self.description or '',
            'amount_authorized': float(self.amount_authorized or 0),
            'amount_used': float(self.amount_used or 0),
            'amount_remaining': self.amount_remaining,
            'utilization_pct': self.utilization_percentage,
            'status': self.status,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'department': self.department or '',
            'cost_code': self.cost_code or '',
            'is_available': self.is_available,
        }

    def __repr__(self):
        return f'<PurchaseOrder {self.po_number} client={self.client_id} status={self.status}>'
