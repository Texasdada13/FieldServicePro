"""
Role-based access control decorators and helpers for FieldServicePro.

Role hierarchy (highest to lowest):
  owner > admin > dispatcher > technician > viewer
"""
from functools import wraps
from flask import abort, flash, redirect, url_for, request
from flask_login import current_user


# -- Role sets --

FINANCIAL_ROLES   = {'owner', 'admin'}
OPERATIONAL_ROLES = {'owner', 'admin', 'dispatcher'}
READ_ONLY_ROLES   = {'owner', 'admin', 'dispatcher', 'technician', 'viewer'}
APPROVAL_ROLES    = {'owner', 'admin'}


def roles_required(*allowed_roles, redirect_url=None, message=None):
    """
    Decorator: abort(403) if current_user.role not in allowed_roles.
    """
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for('auth.login', next=request.url))
            if current_user.role not in allowed_roles:
                if redirect_url:
                    flash(message or 'You do not have permission for that action.', 'danger')
                    return redirect(redirect_url)
                abort(403)
            return fn(*args, **kwargs)
        return wrapper
    return decorator


def can_approve_invoices():
    """Check if current user can approve invoices (respects org settings)."""
    from models.settings import OrganizationSettings
    from models.database import get_session
    try:
        db = get_session()
        settings = OrganizationSettings.get_or_create(db, current_user.organization_id)
        result = current_user.role in settings.approval_role_list
        db.close()
        return result
    except Exception:
        return current_user.role in APPROVAL_ROLES


def can_edit_financial():
    return current_user.role in FINANCIAL_ROLES


def can_create_invoices():
    return current_user.role in OPERATIONAL_ROLES


def can_view_financial():
    return current_user.is_authenticated


def check_invoice_access(invoice, action='view'):
    """
    Returns True if current_user can perform action on invoice.
    action: 'view' | 'edit' | 'approve' | 'delete'
    """
    role = current_user.role

    if action == 'view':
        if role == 'technician':
            return invoice.job and getattr(invoice.job, 'assigned_technician_id', None) == getattr(current_user, 'technician_id', None)
        return True

    if action == 'edit':
        return role in OPERATIONAL_ROLES

    if action == 'approve':
        return can_approve_invoices()

    if action == 'delete':
        return role in FINANCIAL_ROLES

    return False


# -- Phase/Change Order permissions --

def can_manage_phase(user, phase):
    """Can this user create/edit/delete this phase?"""
    if user.role in ('owner', 'admin', 'dispatcher'):
        return True
    if user.role == 'technician':
        from models.technician import Technician
        from models.database import get_session
        db = get_session()
        try:
            tech = db.query(Technician).filter_by(user_id=user.id).first()
            return tech and phase.assigned_technician_id == tech.id
        finally:
            db.close()
    return False


def can_update_phase_status(user, phase):
    return can_manage_phase(user, phase)


def can_create_change_order_fn(user):
    return user.role != 'viewer'


def can_approve_change_order(user, co):
    """Admin/Owner yes. Dispatcher yes but not own COs."""
    if user.role in ('owner', 'admin'):
        return True
    if user.role == 'dispatcher':
        return co.created_by_id != user.id
    return False


def can_edit_change_order(user, co):
    if not co.is_editable:
        return False
    if user.role in ('owner', 'admin'):
        return True
    if user.role in ('dispatcher', 'technician'):
        return co.created_by_id == user.id
    return False


# ── Materials & Inventory Permissions ─────────────────────────────────────────

MATERIALS_PERMISSIONS = {
    'view_catalog': ['owner', 'admin', 'dispatcher', 'technician', 'viewer'],
    'create_part': ['owner', 'admin'],
    'edit_part': ['owner', 'admin'],
    'delete_part': ['owner'],
    'view_costs': ['owner', 'admin', 'dispatcher'],
    'view_margins': ['owner', 'admin'],
    'manage_locations': ['owner', 'admin'],
    'view_inventory': ['owner', 'admin', 'dispatcher', 'technician'],
    'adjust_stock': ['owner', 'admin'],
    'receive_stock': ['owner', 'admin', 'dispatcher'],
    'create_transfer': ['owner', 'admin', 'dispatcher'],
    'approve_transfer': ['owner', 'admin', 'dispatcher'],
    'complete_transfer': ['owner', 'admin', 'dispatcher'],
    'log_material_own_job': ['owner', 'admin', 'dispatcher', 'technician'],
    'log_material_any_job': ['owner', 'admin', 'dispatcher'],
    'verify_material': ['owner', 'admin', 'dispatcher'],
    'delete_material': ['owner', 'admin'],
    'view_truck_own': ['owner', 'admin', 'dispatcher', 'technician'],
    'view_truck_any': ['owner', 'admin', 'dispatcher'],
    'request_restock': ['owner', 'admin', 'dispatcher', 'technician'],
    'view_reports': ['owner', 'admin', 'dispatcher'],
    'import_parts': ['owner', 'admin'],
    'export_reports': ['owner', 'admin'],
}


def can_materials(user, permission):
    """Check if user has a specific materials/inventory permission."""
    role = getattr(user, 'role', 'viewer')
    return role in MATERIALS_PERMISSIONS.get(permission, [])


# ── Expense Permissions ───────────────────────────────────────────────────────

EXPENSE_PERMISSIONS = {
    'create': ['owner', 'admin', 'dispatcher', 'technician'],
    'read': ['owner', 'admin', 'dispatcher', 'technician', 'viewer'],
    'update': ['owner', 'admin', 'dispatcher'],
    'update_own': ['technician'],
    'delete': ['owner', 'admin'],
    'delete_own': ['technician'],
    'approve': ['owner', 'admin'],
    'reimburse': ['owner', 'admin'],
    'view_all': ['owner', 'admin', 'dispatcher'],
    'view_profitability': ['owner', 'admin'],
}


def can_expense(user, action, expense=None):
    """Check expense permission. For own-only actions, pass expense."""
    role = getattr(user, 'role', 'viewer')
    if role in EXPENSE_PERMISSIONS.get(action, []):
        return True
    own_action = action + '_own'
    if role in EXPENSE_PERMISSIONS.get(own_action, []):
        if expense and hasattr(user, 'id') and expense.created_by == user.id:
            return True
    return False


# ── Notification Permissions ─────────────────────────────────────────────────

NOTIFICATION_CATEGORY_ACCESS = {
    'owner':      'all',
    'admin':      'all',
    'dispatcher': [
        'job_update', 'schedule_change', 'request_new',
        'approval_needed', 'system',
    ],
    'technician': [
        'job_update', 'schedule_change', 'time_tracking', 'system',
    ],
    'viewer': ['system'],
}


def can_configure_category(user, category_value):
    """Return True if user can modify notification preferences for this category."""
    role = (getattr(user, 'role', 'viewer') or 'viewer').lower()
    access = NOTIFICATION_CATEGORY_ACCESS.get(role, ['system'])
    if access == 'all':
        return True
    return category_value in access


def can_manage_client_templates(user):
    return (getattr(user, 'role', 'viewer') or 'viewer').lower() in ('admin', 'owner')


def can_view_notification_log(user):
    return (getattr(user, 'role', 'viewer') or 'viewer').lower() in ('admin', 'owner')
