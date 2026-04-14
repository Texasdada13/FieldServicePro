"""FieldServicePro - Data Models."""

from .database import Base, get_session, init_db, engine
from .user import User, Organization, UserRole
from .division import Division
from .client import Client, Property, ClientContact, ClientNote, ClientCommunication, PaymentTerms
from .job import Job, JobStatus, JobNote
from .quote import Quote, QuoteItem, QuoteStatus
from .invoice import Invoice, InvoiceItem, InvoiceStatus, Payment, ApprovalStatus
from .technician import Technician
from .sla import SLA, PriorityLevel
from .contract import (
    Contract, ContractLineItem, ContractActivityLog, ContractAttachment,
    ContractType, ContractStatus, BillingFrequency, ServiceFrequency,
    contract_property, contract_sla,
)
from .purchase_order import PurchaseOrder, POStatus
from .po_attachment import POAttachment
from .app_settings import AppSettings
from .settings import OrganizationSettings
from .job_phase import JobPhase, PhaseStatus, InspectionStatus
from .change_order import (
    ChangeOrder, ChangeOrderLineItem, ChangeOrderStatus,
    ChangeOrderReason, ChangeOrderCostType, ChangeOrderRequestedBy,
)
from .document import Document
from .permit import Permit
from .insurance import InsurancePolicy
from .certification import TechnicianCertification, JobCertificationRequirement
from .checklist import ChecklistTemplate, ChecklistItem, CompletedChecklist, CompletedChecklistItem
from .lien_waiver import LienWaiver
from .portal_user import PortalUser, portal_user_properties
from .portal_message import PortalMessage
from .portal_notification import PortalNotification
from .portal_settings import PortalSettings
from .service_request import ServiceRequest
from .equipment import Equipment
from .project import Project, ProjectNote, ProjectStatus, ProjectPriority
from .time_entry import TimeEntry, ActiveClock
from .part import Part, PART_CATEGORIES, PART_TRADES, UNIT_TYPES
from .inventory import InventoryLocation, InventoryStock, InventoryTransaction, LOCATION_TYPES, TRANSACTION_TYPES
from .job_material import JobMaterial, MATERIAL_STATUSES, MATERIAL_STATUS_COLORS
from .stock_transfer import StockTransfer, StockTransferItem, TRANSFER_STATUSES
from .recurring_schedule import (
    RecurringSchedule, RecurringJobLog,
    FREQUENCY_CHOICES, SCHEDULE_STATUS_CHOICES,
)
from .warranty import (
    Warranty, WarrantyClaim,
    WARRANTY_TYPES, WARRANTY_STATUSES, CLAIM_TYPES, CLAIM_STATUSES,
)
from .callback import (
    Callback,
    CALLBACK_REASONS, CALLBACK_SEVERITIES, CALLBACK_STATUSES,
)
from .communication import (
    CommunicationLog, CommunicationTemplate,
    COMM_TYPES, COMM_DIRECTIONS, COMM_PRIORITIES, COMM_SENTIMENTS,
)
from .expense import (
    Expense, MileageEntry,
    EXPENSE_CATEGORIES, EXPENSE_STATUSES, PAYMENT_METHODS,
)
from .notification import (
    Notification, NotificationPreference, ClientNotificationTemplate, NotificationLog,
    NOTIFICATION_TYPES, NOTIFICATION_CATEGORIES, NOTIFICATION_PRIORITIES,
)
from .vehicle_profile import VehicleProfile, FUEL_TYPES
from .vehicle_mileage_log import VehicleMileageLog, MILEAGE_PURPOSES
from .vehicle_fuel_log import VehicleFuelLog, FUEL_PAYMENT_METHODS
from .payroll_period import PayrollPeriod, PAYROLL_STATUSES, PAY_FREQUENCIES
from .payroll_line_item import PayrollLineItem

__all__ = [
    'Base', 'get_session', 'init_db', 'engine',
    'User', 'Organization', 'UserRole',
    'Division',
    'Client', 'Property', 'ClientContact', 'ClientNote', 'ClientCommunication',
    'PaymentTerms',
    'Job', 'JobStatus', 'JobNote',
    'Quote', 'QuoteItem', 'QuoteStatus',
    'Invoice', 'InvoiceItem', 'InvoiceStatus', 'Payment', 'ApprovalStatus',
    'Technician',
    'SLA', 'PriorityLevel',
    'Contract', 'ContractLineItem', 'ContractActivityLog', 'ContractAttachment',
    'ContractType', 'ContractStatus', 'BillingFrequency', 'ServiceFrequency',
    'contract_property', 'contract_sla',
    'PurchaseOrder', 'POStatus',
    'POAttachment',
    'AppSettings',
    'OrganizationSettings',
    'JobPhase', 'PhaseStatus', 'InspectionStatus',
    'ChangeOrder', 'ChangeOrderLineItem', 'ChangeOrderStatus',
    'ChangeOrderReason', 'ChangeOrderCostType', 'ChangeOrderRequestedBy',
    'Document',
    'Permit',
    'InsurancePolicy',
    'TechnicianCertification', 'JobCertificationRequirement',
    'ChecklistTemplate', 'ChecklistItem', 'CompletedChecklist', 'CompletedChecklistItem',
    'LienWaiver',
    'PortalUser', 'portal_user_properties',
    'PortalMessage',
    'PortalNotification',
    'PortalSettings',
    'ServiceRequest',
    'Equipment',
    'Project', 'ProjectNote', 'ProjectStatus', 'ProjectPriority',
    'TimeEntry', 'ActiveClock',
    'Part', 'PART_CATEGORIES', 'PART_TRADES', 'UNIT_TYPES',
    'InventoryLocation', 'InventoryStock', 'InventoryTransaction',
    'LOCATION_TYPES', 'TRANSACTION_TYPES',
    'JobMaterial', 'MATERIAL_STATUSES',
    'StockTransfer', 'StockTransferItem', 'TRANSFER_STATUSES',
    'RecurringSchedule', 'RecurringJobLog',
    'FREQUENCY_CHOICES', 'SCHEDULE_STATUS_CHOICES',
    'Warranty', 'WarrantyClaim', 'WARRANTY_TYPES', 'WARRANTY_STATUSES',
    'CLAIM_TYPES', 'CLAIM_STATUSES',
    'Callback', 'CALLBACK_REASONS', 'CALLBACK_SEVERITIES', 'CALLBACK_STATUSES',
    'CommunicationLog', 'CommunicationTemplate',
    'COMM_TYPES', 'COMM_DIRECTIONS', 'COMM_PRIORITIES', 'COMM_SENTIMENTS',
    'Expense', 'MileageEntry', 'EXPENSE_CATEGORIES', 'EXPENSE_STATUSES', 'PAYMENT_METHODS',
    'Notification', 'NotificationPreference', 'ClientNotificationTemplate', 'NotificationLog',
    'NOTIFICATION_TYPES', 'NOTIFICATION_CATEGORIES', 'NOTIFICATION_PRIORITIES',
    'VehicleProfile', 'FUEL_TYPES',
    'VehicleMileageLog', 'MILEAGE_PURPOSES',
    'VehicleFuelLog', 'FUEL_PAYMENT_METHODS',
    'PayrollPeriod', 'PAYROLL_STATUSES', 'PAY_FREQUENCIES',
    'PayrollLineItem',
]
