"""Expense CRUD + approval routes."""
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from sqlalchemy import desc, or_

from models.database import get_session
from models.expense import (
    Expense, MileageEntry,
    EXPENSE_CATEGORIES, EXPENSE_STATUSES, PAYMENT_METHODS,
)
from models.job import Job
from models.project import Project
from models.client import Client
from models.division import Division
from web.auth import role_required
from web.utils.expense_utils import generate_expense_number, get_expense_stats

expense_bp = Blueprint('expenses', __name__, url_prefix='/expenses')


def _get_divisions():
    db = get_session()
    try:
        return db.query(Division).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Division.sort_order).all()
    finally:
        db.close()


# ── List ──────────────────────────────────────────────────────────────────────

@expense_bp.route('/')
@login_required
def expense_list():
    db = get_session()
    try:
        org_id = current_user.organization_id
        query = db.query(Expense).join(Client, Expense.client_id == Client.id, isouter=True).filter(
            or_(Client.organization_id == org_id, Expense.client_id == None)
        )

        # Filters
        status = request.args.get('status', '')
        category = request.args.get('category', '')
        search = request.args.get('q', '').strip()

        if status:
            query = query.filter(Expense.status == status)
        if category:
            query = query.filter(Expense.expense_category == category)
        if search:
            s = f'%{search}%'
            query = query.filter(or_(
                Expense.title.ilike(s), Expense.expense_number.ilike(s),
                Expense.vendor_name.ilike(s),
            ))

        expenses = query.order_by(desc(Expense.expense_date)).limit(100).all()
        stats = get_expense_stats(db, current_user.id, current_user.role)

        return render_template('expenses/expense_list.html',
            active_page='expenses', user=current_user, divisions=_get_divisions(),
            can_admin=current_user.role in ('owner', 'admin'),
            expenses=expenses, stats=stats,
            categories=EXPENSE_CATEGORIES, statuses=EXPENSE_STATUSES,
            status_filter=status, category_filter=category, search=search,
        )
    finally:
        db.close()


# ── Detail ────────────────────────────────────────────────────────────────────

@expense_bp.route('/<int:expense_id>')
@login_required
def expense_detail(expense_id):
    db = get_session()
    try:
        expense = db.query(Expense).filter_by(id=expense_id).first()
        if not expense:
            flash('Expense not found.', 'error')
            return redirect(url_for('expenses.expense_list'))

        return render_template('expenses/expense_detail.html',
            active_page='expenses', user=current_user, divisions=_get_divisions(),
            can_admin=current_user.role in ('owner', 'admin'),
            expense=expense,
        )
    finally:
        db.close()


# ── Create ────────────────────────────────────────────────────────────────────

@expense_bp.route('/new', methods=['GET', 'POST'])
@login_required
def expense_new():
    db = get_session()
    try:
        org_id = current_user.organization_id

        if request.method == 'POST':
            return _handle_save(db, None)

        jobs = db.query(Job).filter_by(organization_id=org_id).order_by(desc(Job.id)).limit(100).all()
        projects = db.query(Project).filter_by(organization_id=org_id).order_by(desc(Project.id)).limit(50).all()
        clients = db.query(Client).filter_by(organization_id=org_id).order_by(Client.company_name).all()
        divisions_list = db.query(Division).filter_by(organization_id=org_id, is_active=True).all()

        prefill = {k: request.args.get(k) for k in ('job_id', 'project_id', 'client_id')}

        return render_template('expenses/expense_form.html',
            active_page='expenses', user=current_user, divisions=_get_divisions(),
            expense=None, jobs=jobs, projects=projects, clients=clients,
            all_divisions=divisions_list, prefill=prefill,
            categories=EXPENSE_CATEGORIES, payment_methods=PAYMENT_METHODS,
        )
    finally:
        db.close()


# ── Edit ──────────────────────────────────────────────────────────────────────

@expense_bp.route('/<int:expense_id>/edit', methods=['GET', 'POST'])
@login_required
def expense_edit(expense_id):
    db = get_session()
    try:
        org_id = current_user.organization_id
        expense = db.query(Expense).filter_by(id=expense_id).first()
        if not expense:
            flash('Not found.', 'error')
            return redirect(url_for('expenses.expense_list'))

        if request.method == 'POST':
            return _handle_save(db, expense)

        jobs = db.query(Job).filter_by(organization_id=org_id).order_by(desc(Job.id)).limit(100).all()
        projects = db.query(Project).filter_by(organization_id=org_id).order_by(desc(Project.id)).limit(50).all()
        clients = db.query(Client).filter_by(organization_id=org_id).order_by(Client.company_name).all()
        divisions_list = db.query(Division).filter_by(organization_id=org_id, is_active=True).all()

        return render_template('expenses/expense_form.html',
            active_page='expenses', user=current_user, divisions=_get_divisions(),
            expense=expense, jobs=jobs, projects=projects, clients=clients,
            all_divisions=divisions_list, prefill={},
            categories=EXPENSE_CATEGORIES, payment_methods=PAYMENT_METHODS,
        )
    finally:
        db.close()


def _handle_save(db, expense):
    is_new = expense is None
    f = request.form
    try:
        if is_new:
            expense = Expense(
                expense_number=generate_expense_number(db),
                created_by=current_user.id,
            )
            db.add(expense)

        expense.title = f.get('title', '').strip()
        expense.description = f.get('description', '').strip() or None
        expense.expense_category = f.get('expense_category', 'other')
        expense.amount = float(f.get('amount', 0) or 0)
        expense.tax_amount = float(f.get('tax_amount', 0) or 0)

        def _fk(field):
            v = f.get(field)
            return int(v) if v and v.isdigit() else None

        expense.job_id = _fk('job_id')
        expense.project_id = _fk('project_id')
        expense.client_id = _fk('client_id')
        expense.division_id = _fk('division_id')
        expense.phase_id = _fk('phase_id')

        expense.is_billable = 'is_billable' in f
        expense.is_reimbursable = 'is_reimbursable' in f
        expense.markup_percentage = float(f.get('markup_percentage', 0) or 0)
        expense.vendor_name = f.get('vendor_name', '').strip() or None
        expense.receipt_number = f.get('receipt_number', '').strip() or None
        expense.payment_method = f.get('payment_method', 'company_card')
        expense.paid_by = _fk('paid_by') or current_user.id
        expense.expense_date = date.fromisoformat(f['expense_date'])

        expense.compute_totals()
        db.commit()
        flash(f"Expense {expense.expense_number} saved.", 'success')
        return redirect(url_for('expenses.expense_detail', expense_id=expense.id))
    except Exception as e:
        db.rollback()
        flash(f'Error: {e}', 'error')
        return redirect(request.referrer or url_for('expenses.expense_list'))


# ── Submit ────────────────────────────────────────────────────────────────────

@expense_bp.route('/<int:expense_id>/submit', methods=['POST'])
@login_required
def expense_submit(expense_id):
    db = get_session()
    try:
        expense = db.query(Expense).filter_by(id=expense_id).first()
        if expense and expense.status == 'draft':
            expense.status = 'submitted'
            expense.submitted_date = date.today()
            db.commit()
            try:
                from web.utils.notification_service import NotificationService
                NotificationService.notify('expense_submitted', expense, triggered_by=current_user,
                                           extra_context={'amount': f'${float(expense.total_amount or 0):,.2f}'})
            except Exception:
                pass
            flash('Expense submitted for approval.', 'success')
    finally:
        db.close()
    return redirect(url_for('expenses.expense_detail', expense_id=expense_id))


# ── Approve / Reject ──────────────────────────────────────────────────────────

@expense_bp.route('/<int:expense_id>/approve', methods=['POST'])
@login_required
@role_required('owner', 'admin')
def expense_approve(expense_id):
    db = get_session()
    try:
        expense = db.query(Expense).filter_by(id=expense_id).first()
        if expense and expense.status == 'submitted':
            expense.status = 'approved'
            expense.approved_by = current_user.id
            expense.approved_date = date.today()
            db.commit()
            try:
                from web.utils.notification_service import NotificationService
                NotificationService.notify('item_approved', expense, triggered_by=current_user)
            except Exception:
                pass
            flash('Expense approved.', 'success')
    finally:
        db.close()
    return redirect(url_for('expenses.expense_detail', expense_id=expense_id))


@expense_bp.route('/<int:expense_id>/reject', methods=['POST'])
@login_required
@role_required('owner', 'admin')
def expense_reject(expense_id):
    db = get_session()
    try:
        expense = db.query(Expense).filter_by(id=expense_id).first()
        if expense and expense.status == 'submitted':
            expense.status = 'rejected'
            expense.rejection_reason = request.form.get('rejection_reason', '')
            db.commit()
            try:
                from web.utils.notification_service import NotificationService
                NotificationService.notify('item_rejected', expense, triggered_by=current_user,
                                           extra_context={'reason': expense.rejection_reason})
            except Exception:
                pass
            flash('Expense rejected.', 'warning')
    finally:
        db.close()
    return redirect(url_for('expenses.expense_detail', expense_id=expense_id))


# ── Approval Queue ────────────────────────────────────────────────────────────

@expense_bp.route('/approval-queue')
@login_required
@role_required('owner', 'admin')
def approval_queue():
    db = get_session()
    try:
        pending = db.query(Expense).filter_by(status='submitted').order_by(Expense.submitted_date).all()
        return render_template('expenses/approval_queue.html',
            active_page='expenses', user=current_user, divisions=_get_divisions(),
            pending=pending,
        )
    finally:
        db.close()


# ── Bulk Approve/Reject ───────────────────────────────────────────────────────

@expense_bp.route('/approvals/bulk', methods=['POST'])
@login_required
@role_required('owner', 'admin')
def bulk_approve():
    db = get_session()
    try:
        action = request.form.get('bulk_action', 'approve')
        ids = request.form.getlist('expense_ids')
        reason = request.form.get('bulk_rejection_reason', '').strip()

        if not ids:
            flash('No expenses selected.', 'warning')
            return redirect(url_for('expenses.approval_queue'))

        count = 0
        for eid in ids:
            expense = db.query(Expense).filter_by(id=int(eid)).first()
            if not expense or expense.status != 'submitted':
                continue
            if action == 'approve':
                expense.status = 'approved'
                expense.approved_by = current_user.id
                expense.approved_date = date.today()
                count += 1
            elif action == 'reject' and reason:
                expense.status = 'rejected'
                expense.rejection_reason = reason
                count += 1

        db.commit()
        flash(f'{count} expense(s) {action}d.', 'success')
    finally:
        db.close()
    return redirect(url_for('expenses.approval_queue'))


# ── Delete ────────────────────────────────────────────────────────────────────

@expense_bp.route('/<int:expense_id>/delete', methods=['POST'])
@login_required
@role_required('owner', 'admin')
def expense_delete(expense_id):
    db = get_session()
    try:
        expense = db.query(Expense).filter_by(id=expense_id).first()
        if expense and expense.status in ('draft', 'rejected'):
            db.delete(expense)
            db.commit()
            flash('Expense deleted.', 'warning')
            return redirect(url_for('expenses.expense_list'))
    finally:
        db.close()
    return redirect(url_for('expenses.expense_detail', expense_id=expense_id))


# ── Mileage Entry ─────────────────────────────────────────────────────────────

@expense_bp.route('/mileage/new', methods=['GET', 'POST'])
@login_required
def mileage_new():
    db = get_session()
    try:
        org_id = current_user.organization_id

        if request.method == 'POST':
            f = request.form
            try:
                miles = float(f.get('distance_miles', 0) or 0)
                rate = float(f.get('mileage_rate', 0.67) or 0.67)
                round_trip = 'is_round_trip' in f
                effective = miles * 2 if round_trip else miles
                amount = round(effective * rate, 2)

                from_loc = f.get('start_location', '').strip()
                to_loc = f.get('end_location', '').strip()
                purpose = f.get('purpose', '').strip()

                expense = Expense(
                    expense_number=generate_expense_number(db),
                    title=purpose or f'Mileage: {from_loc} → {to_loc}',
                    description=f"{'Round trip: ' if round_trip else ''}{from_loc} → {to_loc} | {effective:.1f} mi @ ${rate:.4f}/mi",
                    expense_category='fuel_mileage',
                    amount=amount, tax_amount=0,
                    expense_date=date.fromisoformat(f['expense_date']),
                    job_id=int(f['job_id']) if f.get('job_id') else None,
                    is_reimbursable='is_reimbursable' in f,
                    payment_method='company_card',
                    paid_by=current_user.id,
                    created_by=current_user.id,
                    status='submitted', submitted_date=date.today(),
                )
                if expense.job_id:
                    job = db.query(Job).filter_by(id=expense.job_id).first()
                    if job:
                        expense.client_id = job.client_id
                        expense.project_id = getattr(job, 'project_id', None)
                expense.compute_totals()
                db.add(expense)
                db.flush()

                mileage = MileageEntry(
                    expense_id=expense.id,
                    start_location=from_loc, end_location=to_loc,
                    distance_miles=miles, mileage_rate=rate,
                    is_round_trip=round_trip, purpose=purpose,
                    vehicle_id=int(f['vehicle_id']) if f.get('vehicle_id') else None,
                )
                mileage.compute_amount()
                db.add(mileage)
                db.commit()
                flash(f'Mileage {expense.expense_number} logged.', 'success')
                return redirect(url_for('expenses.expense_detail', expense_id=expense.id))
            except Exception as e:
                db.rollback()
                flash(f'Error: {e}', 'error')

        jobs = db.query(Job).filter_by(organization_id=org_id).order_by(desc(Job.id)).limit(50).all()
        return render_template('expenses/mileage_form.html',
            active_page='expenses', user=current_user, divisions=_get_divisions(),
            jobs=jobs, mileage_rate=0.67,
        )
    finally:
        db.close()


# ── Reimbursement Queue ───────────────────────────────────────────────────────

@expense_bp.route('/reimbursements')
@login_required
@role_required('owner', 'admin')
def reimbursement_queue():
    db = get_session()
    try:
        pending = db.query(Expense).filter(
            Expense.status == 'approved', Expense.is_reimbursable == True, Expense.reimbursed_date == None,
        ).order_by(Expense.expense_date).all()
        total = sum(float(e.total_amount or 0) for e in pending)
        return render_template('expenses/reimbursement_queue.html',
            active_page='expenses', user=current_user, divisions=_get_divisions(),
            pending=pending, total=total,
        )
    finally:
        db.close()


@expense_bp.route('/<int:expense_id>/reimburse', methods=['POST'])
@login_required
@role_required('owner', 'admin')
def mark_reimbursed(expense_id):
    db = get_session()
    try:
        expense = db.query(Expense).filter_by(id=expense_id).first()
        if expense and expense.status == 'approved':
            expense.status = 'reimbursed'
            expense.reimbursed_date = date.today()
            expense.reimbursed_amount = float(expense.total_amount or 0)
            db.commit()
            flash(f'Expense {expense.expense_number} reimbursed.', 'success')
    finally:
        db.close()
    return redirect(request.referrer or url_for('expenses.reimbursement_queue'))
