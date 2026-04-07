"""
Payment terms utility -- due date calculation, display labels, validation.
"""
from datetime import date, timedelta


PAYMENT_TERMS_LABELS = {
    "due_on_receipt": "Due on Receipt",
    "net_15": "Net 15",
    "net_30": "Net 30",
    "net_45": "Net 45",
    "net_60": "Net 60",
    "net_90": "Net 90",
    "custom": "Custom",
}

PAYMENT_TERMS_DAYS = {
    "due_on_receipt": 0,
    "net_15": 15,
    "net_30": 30,
    "net_45": 45,
    "net_60": 60,
    "net_90": 90,
}

PAYMENT_TERMS_CHOICES = [
    ("due_on_receipt", "Due on Receipt"),
    ("net_15", "Net 15"),
    ("net_30", "Net 30"),
    ("net_45", "Net 45"),
    ("net_60", "Net 60"),
    ("net_90", "Net 90"),
    ("custom", "Custom"),
]


def calculate_due_date(invoice_date, payment_terms, custom_days=None):
    """
    Calculate due date from invoice date and payment terms string.

    Args:
        invoice_date: date or datetime object
        payment_terms: string matching PAYMENT_TERMS_DAYS keys
        custom_days: integer, used when payment_terms == 'custom'

    Returns:
        date object
    """
    if invoice_date is None:
        invoice_date = date.today()
    if hasattr(invoice_date, 'date'):
        invoice_date = invoice_date.date()

    if payment_terms == 'custom':
        days = int(custom_days or 30)
    else:
        days = PAYMENT_TERMS_DAYS.get(payment_terms, 30)

    return invoice_date + timedelta(days=days)


def get_terms_for_client(client):
    """
    Return the effective payment terms and due date for a new invoice
    based on client defaults.

    Returns:
        dict with keys: terms, terms_label, custom_days, due_date
    """
    terms = getattr(client, 'default_payment_terms', 'net_30') or 'net_30'
    custom_days = getattr(client, 'custom_payment_days', None)
    due = calculate_due_date(date.today(), terms, custom_days)
    return {
        'terms': terms,
        'terms_label': PAYMENT_TERMS_LABELS.get(terms, terms),
        'custom_days': custom_days,
        'due_date': due,
    }


def assess_late_fees(invoice):
    """
    Assess a late fee on a given invoice if it's overdue and no fee has been applied.

    Returns:
        float fee amount (0 if not applicable)
    """
    from models.app_settings import AppSettings

    if invoice.status not in ('sent', 'overdue', 'partial'):
        return 0.0
    if invoice.due_date is None:
        return 0.0
    due = invoice.due_date if isinstance(invoice.due_date, date) else invoice.due_date.date()
    if date.today() <= due:
        return 0.0
    if invoice.late_fee_applied and float(invoice.late_fee_applied) > 0:
        return 0.0  # Already applied

    rate = float(invoice.late_fee_rate or AppSettings.late_fee_rate_default() or 1.5)
    balance = float(invoice.balance_due or invoice.total or 0)
    fee = round(balance * rate / 100, 2)
    return fee


def validate_po_for_invoice(po, invoice_amount, existing_po_id=None):
    """
    Validate that a PO can be linked to an invoice with the given amount.

    Args:
        po: PurchaseOrder instance
        invoice_amount: float
        existing_po_id: if updating an invoice that already has this PO

    Returns:
        (is_valid: bool, is_warning: bool, message: str)
    """
    if po is None:
        return True, False, ""

    if not po.is_available:
        return (
            False,
            False,
            f"PO #{po.po_number} is {po.status} and cannot accept new charges.",
        )

    remaining = po.amount_remaining
    if float(invoice_amount) > remaining:
        return (
            False,
            True,
            (
                f"Invoice amount ${float(invoice_amount):,.2f} exceeds PO "
                f"#{po.po_number} remaining balance ${remaining:,.2f}. "
                f"Proceed with caution."
            ),
        )

    return True, False, ""
