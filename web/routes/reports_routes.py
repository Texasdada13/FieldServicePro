"""Reports & Analytics Blueprint — main hub and individual report routes."""
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from datetime import datetime, date, timedelta
from dateutil.relativedelta import relativedelta
from functools import wraps

from models.database import get_session
from models.job import Job
from models.client import Client
from models.invoice import Invoice
from models.technician import Technician
from models.division import Division
from models.expense import Expense
from models.time_entry import TimeEntry
from models.project import Project
from web.auth import role_required

reports_bp = Blueprint('reports', __name__)


# ── Date Range Helpers ────────────────────────────────────────────────────────

def parse_date_range(args):
    """Parse preset or custom date range. Returns (start, end, label)."""
    preset = args.get('preset', 'this_month')
    today = date.today()

    presets = {
        'today': (today, today, 'Today'),
        'this_week': (today - timedelta(days=today.weekday()),
                      today - timedelta(days=today.weekday()) + timedelta(days=6), 'This Week'),
        'this_month': (today.replace(day=1),
                       (today.replace(day=1) + relativedelta(months=1)) - timedelta(days=1), 'This Month'),
        'this_quarter': (date(today.year, ((today.month - 1) // 3) * 3 + 1, 1),
                         date(today.year, ((today.month - 1) // 3) * 3 + 1, 1) + relativedelta(months=3) - timedelta(days=1), 'This Quarter'),
        'this_year': (date(today.year, 1, 1), date(today.year, 12, 31), 'This Year'),
        'last_month': ((today.replace(day=1) - relativedelta(months=1)),
                       today.replace(day=1) - timedelta(days=1), 'Last Month'),
        'last_quarter': (date(today.year, ((today.month - 1) // 3) * 3 + 1, 1) - relativedelta(months=3),
                         date(today.year, ((today.month - 1) // 3) * 3 + 1, 1) - timedelta(days=1), 'Last Quarter'),
        'last_year': (date(today.year - 1, 1, 1), date(today.year - 1, 12, 31), 'Last Year'),
    }

    if preset == 'custom':
        try:
            start = datetime.strptime(args.get('start_date', ''), '%Y-%m-%d').date()
            end = datetime.strptime(args.get('end_date', ''), '%Y-%m-%d').date()
            return start, end, f"{start.strftime('%b %d, %Y')} - {end.strftime('%b %d, %Y')}"
        except (ValueError, TypeError):
            pass

    return presets.get(preset, presets['this_month'])


def get_12_month_labels():
    today = date.today()
    return [(today - relativedelta(months=i)) for i in range(11, -1, -1)]


def safe_divide(num, denom, default=0.0):
    return num / denom if denom else default


def _get_divisions(db):
    return db.query(Division).filter_by(
        organization_id=current_user.organization_id, is_active=True
    ).order_by(Division.sort_order).all()


# ── Landing Page ──────────────────────────────────────────────────────────────

@reports_bp.route('/reports')
@login_required
def index():
    db = get_session()
    try:
        org_id = current_user.organization_id
        today_date = date.today()
        month_start = today_date.replace(day=1)

        jobs_this_month = db.query(Job).filter(
            Job.organization_id == org_id,
            Job.created_at >= datetime.combine(month_start, datetime.min.time()),
        ).count()

        open_invoice_total = float(db.query(
            func.coalesce(func.sum(Invoice.balance_due), 0)
        ).filter(
            Invoice.organization_id == org_id,
            Invoice.status.in_(['sent', 'overdue', 'partial']),
        ).scalar() or 0)

        active_projects = db.query(Project).filter_by(
            organization_id=org_id, status='active'
        ).count()

        categories = _build_report_categories()

        if current_user.role not in ('owner', 'admin'):
            categories = [c for c in categories if c['id'] != 'financial']

        return render_template('reports/index.html',
            active_page='reports', user=current_user, divisions=_get_divisions(db),
            categories=categories, jobs_this_month=jobs_this_month,
            open_invoice_total=open_invoice_total, active_projects=active_projects,
        )
    finally:
        db.close()


def _build_report_categories():
    return [
        {'id': 'financial', 'name': 'Financial Reports', 'icon': 'bi-currency-dollar', 'color': 'success',
         'description': 'Revenue, profitability, AR aging, and expense analysis',
         'reports': [
             {'name': 'Profitability Report', 'url': 'reports.profitability', 'desc': 'Revenue vs. cost vs. profit by job, client, division'},
             {'name': 'Revenue Report', 'url': 'reports.revenue', 'desc': 'Invoiced, collected, and outstanding revenue'},
             {'name': 'AR Aging Report', 'url': 'reports.ar_aging', 'desc': 'Outstanding invoices by aging bucket'},
             {'name': 'Expense Report', 'url': 'reports.expense_report', 'desc': 'Expenses by category, employee, and period'},
             {'name': 'AP Aging Report', 'url': 'reports.ap_aging', 'desc': 'Outstanding vendor payables by aging bucket'},
         ]},
        {'id': 'jobs', 'name': 'Job & Project Reports', 'icon': 'bi-briefcase', 'color': 'accent',
         'description': 'Job performance, project budgets, and change orders',
         'reports': [
             {'name': 'Job Performance', 'url': 'reports.job_performance', 'desc': 'Completion rates, durations, on-time %'},
             {'name': 'Project Budget', 'url': 'reports.project_budget', 'desc': 'Budget vs. actual by project'},
             {'name': 'Change Orders', 'url': 'reports.change_order_report', 'desc': 'CO volume, value, and approval rates'},
         ]},
        {'id': 'labor', 'name': 'Technician & Labor Reports', 'icon': 'bi-people', 'color': 'info',
         'description': 'Tech performance, labor utilization, and payroll summary',
         'reports': [
             {'name': 'Technician Performance', 'url': 'reports.tech_performance', 'desc': 'Jobs, revenue, utilization by tech'},
             {'name': 'Labor Utilization', 'url': 'reports.labor_utilization', 'desc': 'Billable vs. non-billable hours'},
         ]},
        {'id': 'clients', 'name': 'Client Reports', 'icon': 'bi-person-lines-fill', 'color': 'warning',
         'description': 'Client activity, retention, and value analysis',
         'reports': [
             {'name': 'Client Activity', 'url': 'reports.client_activity', 'desc': 'Active vs. inactive, revenue by client'},
             {'name': 'Sales Pipeline', 'url': 'reports.sales_pipeline', 'desc': 'Quote funnel, win rate, deal size'},
         ]},
        {'id': 'inventory', 'name': 'Inventory & Materials', 'icon': 'bi-boxes', 'color': 'secondary',
         'description': 'Stock levels, valuation, and parts usage',
         'reports': [
             {'name': 'Inventory Valuation', 'url': 'reports.inventory_valuation', 'desc': 'Current stock value by location'},
         ]},
        {'id': 'quality', 'name': 'Compliance & Quality', 'icon': 'bi-shield-check', 'color': 'danger',
         'description': 'Permits, certifications, callbacks, and quality metrics',
         'reports': [
             {'name': 'Compliance Status', 'url': 'reports.compliance_report', 'desc': 'Expiring certs, permits, insurance'},
             {'name': 'Quality & Callbacks', 'url': 'reports.quality_report', 'desc': 'Callback rates, root causes'},
         ]},
        {'id': 'advanced', 'name': 'Advanced Analytics', 'icon': 'bi-trophy', 'color': 'warning',
         'description': 'Leaderboards, pipeline analytics, and capacity planning',
         'reports': [
             {'name': 'Tech Leaderboard', 'url': 'advanced_reports.tech_leaderboard', 'desc': 'Gamified rankings with composite scores and achievements'},
             {'name': 'Sales Pipeline Dashboard', 'url': 'advanced_reports.sales_pipeline', 'desc': 'Funnel visualization, Kanban board, revenue forecasting'},
             {'name': 'Capacity Planner', 'url': 'advanced_reports.capacity_planner', 'desc': 'Heatmap grid, demand forecast, what-if scenarios'},
         ]},
    ]


# ── Profitability Report ──────────────────────────────────────────────────────

@reports_bp.route('/reports/profitability')
@login_required
@role_required('admin', 'owner')
def profitability():
    db = get_session()
    try:
        org_id = current_user.organization_id
        start_date, end_date, date_label = parse_date_range(request.args)
        selected_preset = request.args.get('preset', 'this_month')
        division_id = request.args.get('division_id', type=int)

        from models.job_material import JobMaterial

        # Jobs in date range
        job_q = db.query(Job).filter(
            Job.organization_id == org_id,
            Job.created_at >= datetime.combine(start_date, datetime.min.time()),
            Job.created_at <= datetime.combine(end_date, datetime.max.time()),
        )
        if division_id:
            job_q = job_q.filter(Job.division_id == division_id)

        jobs = job_q.all()
        job_ids = [j.id for j in jobs]

        divisions = _get_divisions(db)
        all_clients = db.query(Client).filter_by(
            organization_id=org_id, is_active=True
        ).order_by(Client.company_name).all()

        if not job_ids:
            return render_template('reports/profitability.html',
                active_page='reports', user=current_user, divisions=divisions,
                report_title='Profitability Report', report_category='Financial',
                date_label=date_label, selected_preset=selected_preset,
                start_date=start_date, end_date=end_date,
                empty=True, all_divisions=divisions, all_clients=all_clients,
            )

        # Aggregate costs per job
        labor_by_job = dict(db.query(
            TimeEntry.job_id, func.coalesce(func.sum(TimeEntry.labor_cost), 0)
        ).filter(TimeEntry.job_id.in_(job_ids)).group_by(TimeEntry.job_id).all())

        material_by_job = dict(db.query(
            JobMaterial.job_id, func.coalesce(func.sum(JobMaterial.total_cost), 0)
        ).filter(JobMaterial.job_id.in_(job_ids)).group_by(JobMaterial.job_id).all())

        expense_by_job = dict(db.query(
            Expense.job_id, func.coalesce(func.sum(Expense.total_amount), 0)
        ).filter(Expense.job_id.in_(job_ids)).group_by(Expense.job_id).all())

        revenue_by_job = dict(db.query(
            Invoice.job_id, func.coalesce(func.sum(Invoice.total), 0)
        ).filter(Invoice.job_id.in_(job_ids)).group_by(Invoice.job_id).all())

        # Build per-job rows
        job_rows = []
        for job in jobs:
            revenue = float(revenue_by_job.get(job.id, 0) or 0)
            labor = float(labor_by_job.get(job.id, 0) or 0)
            materials = float(material_by_job.get(job.id, 0) or 0)
            expenses = float(expense_by_job.get(job.id, 0) or 0)
            total_cost = labor + materials + expenses
            profit = revenue - total_cost
            margin = safe_divide(profit, revenue) * 100 if revenue else 0

            job_rows.append({
                'id': job.id, 'number': job.job_number,
                'client': job.client.display_name if job.client else '--',
                'type': job.job_type or '--', 'status': job.status,
                'revenue': revenue, 'labor': labor, 'materials': materials,
                'expenses': expenses, 'total_cost': total_cost,
                'profit': profit, 'margin': round(margin, 1),
                'unprofitable': profit < 0,
            })

        # Summaries
        total_revenue = sum(r['revenue'] for r in job_rows)
        total_cost_sum = sum(r['total_cost'] for r in job_rows)
        total_profit = total_revenue - total_cost_sum
        total_margin = safe_divide(total_profit, total_revenue) * 100
        total_labor = sum(r['labor'] for r in job_rows)
        total_materials = sum(r['materials'] for r in job_rows)
        total_expenses = sum(r['expenses'] for r in job_rows)

        # By client
        client_agg = {}
        for r in job_rows:
            c = r['client']
            if c not in client_agg:
                client_agg[c] = {'client': c, 'revenue': 0, 'cost': 0, 'jobs': 0}
            client_agg[c]['revenue'] += r['revenue']
            client_agg[c]['cost'] += r['total_cost']
            client_agg[c]['jobs'] += 1
        client_rows = []
        for d in client_agg.values():
            p = d['revenue'] - d['cost']
            client_rows.append({**d, 'profit': p, 'margin': round(safe_divide(p, d['revenue']) * 100, 1)})
        client_rows.sort(key=lambda x: x['revenue'], reverse=True)

        # Monthly trend
        months_data = get_12_month_labels()
        month_labels = [m.strftime('%b %Y') for m in months_data]
        monthly_revenue = []
        monthly_cost = []
        monthly_profit = []
        for m in months_data:
            m_start = m.replace(day=1)
            m_end = (m_start + relativedelta(months=1)) - timedelta(days=1)
            m_job_ids = [j.id for j in db.query(Job).filter(
                Job.organization_id == org_id,
                Job.created_at >= datetime.combine(m_start, datetime.min.time()),
                Job.created_at <= datetime.combine(m_end, datetime.max.time()),
            ).all()]
            if m_job_ids:
                m_rev = float(db.query(func.coalesce(func.sum(Invoice.total), 0)).filter(
                    Invoice.job_id.in_(m_job_ids)).scalar() or 0)
                m_lab = float(db.query(func.coalesce(func.sum(TimeEntry.labor_cost), 0)).filter(
                    TimeEntry.job_id.in_(m_job_ids)).scalar() or 0)
                m_mat = float(db.query(func.coalesce(func.sum(JobMaterial.total_cost), 0)).filter(
                    JobMaterial.job_id.in_(m_job_ids)).scalar() or 0)
                m_exp = float(db.query(func.coalesce(func.sum(Expense.total_amount), 0)).filter(
                    Expense.job_id.in_(m_job_ids)).scalar() or 0)
                m_cost = m_lab + m_mat + m_exp
            else:
                m_rev = m_cost = 0
            monthly_revenue.append(round(m_rev, 2))
            monthly_cost.append(round(m_cost, 2))
            monthly_profit.append(round(m_rev - m_cost, 2))

        summary_json = {
            'Total Revenue': f'${total_revenue:,.2f}',
            'Total Cost': f'${total_cost_sum:,.2f}',
            'Gross Profit': f'${total_profit:,.2f}',
            'Gross Margin': f'{total_margin:.1f}%',
            'Jobs Analyzed': len(job_rows),
            'Labor Cost': f'${total_labor:,.2f}',
            'Materials Cost': f'${total_materials:,.2f}',
            'Other Expenses': f'${total_expenses:,.2f}',
            'Unprofitable Jobs': sum(1 for r in job_rows if r['unprofitable']),
        }

        return render_template('reports/profitability.html',
            active_page='reports', user=current_user, divisions=divisions,
            report_title='Profitability Report', report_category='Financial',
            date_label=date_label, selected_preset=selected_preset,
            start_date=start_date, end_date=end_date, empty=False,
            total_revenue=total_revenue, total_cost=total_cost_sum,
            total_profit=total_profit, total_margin=total_margin,
            total_labor=total_labor, total_materials=total_materials,
            total_expenses_val=total_expenses,
            job_rows=job_rows, client_rows=client_rows,
            month_labels=month_labels, monthly_revenue=monthly_revenue,
            monthly_cost=monthly_cost, monthly_profit=monthly_profit,
            all_divisions=divisions, all_clients=all_clients,
            selected_division=division_id,
            summary_json=summary_json,
        )
    finally:
        db.close()


# ── Revenue Report ─────────────────────────────────────────────────────────────

@reports_bp.route('/reports/revenue')
@login_required
@role_required('admin', 'owner')
def revenue():
    db = get_session()
    try:
        org_id = current_user.organization_id
        start_date, end_date, date_label = parse_date_range(request.args)
        selected_preset = request.args.get('preset', 'this_month')
        division_id = request.args.get('division_id', type=int)
        client_id = request.args.get('client_id', type=int)

        inv_q = db.query(Invoice).filter(
            Invoice.organization_id == org_id,
            Invoice.issued_date != None,
            Invoice.issued_date >= datetime.combine(start_date, datetime.min.time()),
            Invoice.issued_date <= datetime.combine(end_date, datetime.max.time()),
        )
        if client_id:
            inv_q = inv_q.filter(Invoice.client_id == client_id)

        invoices = inv_q.all()

        total_invoiced = sum(float(i.total or 0) for i in invoices)
        total_collected = sum(float(i.amount_paid or 0) for i in invoices)
        total_outstanding = sum(float(i.balance_due or 0) for i in invoices)
        avg_invoice = safe_divide(total_invoiced, len(invoices)) if invoices else 0

        # Monthly
        months_data = get_12_month_labels()
        month_labels = [m.strftime('%b %Y') for m in months_data]
        monthly_invoiced, monthly_collected = [], []
        for m in months_data:
            m_start = m.replace(day=1)
            m_end = (m_start + relativedelta(months=1)) - timedelta(days=1)
            m_invs = db.query(Invoice).filter(
                Invoice.organization_id == org_id,
                Invoice.issued_date >= datetime.combine(m_start, datetime.min.time()),
                Invoice.issued_date <= datetime.combine(m_end, datetime.max.time()),
            ).all()
            monthly_invoiced.append(round(sum(float(i.total or 0) for i in m_invs), 2))
            monthly_collected.append(round(sum(float(i.amount_paid or 0) for i in m_invs), 2))

        # By client
        client_agg = {}
        for inv in invoices:
            cn = inv.client.display_name if inv.client else 'Unknown'
            if cn not in client_agg:
                client_agg[cn] = {'client': cn, 'invoiced': 0, 'collected': 0, 'outstanding': 0, 'count': 0}
            client_agg[cn]['invoiced'] += float(inv.total or 0)
            client_agg[cn]['collected'] += float(inv.amount_paid or 0)
            client_agg[cn]['outstanding'] += float(inv.balance_due or 0)
            client_agg[cn]['count'] += 1
        client_rows = sorted(client_agg.values(), key=lambda x: x['invoiced'], reverse=True)

        divisions = _get_divisions(db)
        all_clients = db.query(Client).filter_by(organization_id=org_id, is_active=True).order_by(Client.company_name).all()

        summary_json = {
            'Total Invoiced': f'${total_invoiced:,.2f}',
            'Total Collected': f'${total_collected:,.2f}',
            'Total Outstanding': f'${total_outstanding:,.2f}',
            'Average Invoice': f'${avg_invoice:,.2f}',
            'Invoice Count': len(invoices),
            'Collection Rate': f'{safe_divide(total_collected, total_invoiced)*100:.1f}%',
        }

        return render_template('reports/revenue.html',
            active_page='reports', user=current_user, divisions=divisions,
            report_title='Revenue Report', report_category='Financial',
            date_label=date_label, selected_preset=selected_preset,
            start_date=start_date, end_date=end_date,
            empty=len(invoices) == 0,
            total_invoiced=total_invoiced, total_collected=total_collected,
            total_outstanding=total_outstanding, avg_invoice=avg_invoice,
            month_labels=month_labels, monthly_invoiced=monthly_invoiced,
            monthly_collected=monthly_collected,
            client_rows=client_rows, invoices=invoices,
            all_divisions=divisions, all_clients=all_clients,
            selected_division=division_id, selected_client=client_id,
            summary_json=summary_json,
        )
    finally:
        db.close()


# ── AR Aging Report ───────────────────────────────────────────────────────────

@reports_bp.route('/reports/ar-aging')
@login_required
@role_required('admin', 'owner')
def ar_aging():
    db = get_session()
    try:
        org_id = current_user.organization_id
        client_id = request.args.get('client_id', type=int)
        today_date = date.today()

        inv_q = db.query(Invoice).filter(
            Invoice.organization_id == org_id,
            Invoice.status.in_(['sent', 'overdue', 'partial']),
            Invoice.balance_due > 0,
        )
        if client_id:
            inv_q = inv_q.filter(Invoice.client_id == client_id)

        invoices = inv_q.all()

        def aging_bucket(inv):
            if not inv.due_date:
                return 'current'
            d = inv.due_date.date() if hasattr(inv.due_date, 'date') else inv.due_date
            days = (today_date - d).days
            if days <= 0: return 'current'
            if days <= 30: return '1_30'
            if days <= 60: return '31_60'
            if days <= 90: return '61_90'
            return '90_plus'

        invoice_rows = []
        for inv in invoices:
            bucket = aging_bucket(inv)
            d = inv.due_date.date() if inv.due_date and hasattr(inv.due_date, 'date') else inv.due_date
            days_overdue = max(0, (today_date - d).days) if d else 0
            invoice_rows.append({
                'id': inv.id, 'number': inv.invoice_number,
                'client': inv.client.display_name if inv.client else '--',
                'amount': float(inv.balance_due or 0),
                'total': float(inv.total or 0),
                'due_date': d, 'days_overdue': days_overdue,
                'bucket': bucket, 'status': inv.status,
            })

        client_agg = {}
        for r in invoice_rows:
            cn = r['client']
            if cn not in client_agg:
                client_agg[cn] = {'client': cn, 'current': 0, '1_30': 0, '31_60': 0, '61_90': 0, '90_plus': 0, 'total': 0}
            client_agg[cn][r['bucket']] += r['amount']
            client_agg[cn]['total'] += r['amount']
        client_rows = sorted(client_agg.values(), key=lambda x: x['total'], reverse=True)

        total_current = sum(r['current'] for r in client_rows)
        total_1_30 = sum(r['1_30'] for r in client_rows)
        total_31_60 = sum(r['31_60'] for r in client_rows)
        total_61_90 = sum(r['61_90'] for r in client_rows)
        total_90_plus = sum(r['90_plus'] for r in client_rows)
        grand_total = sum(r['total'] for r in client_rows)

        divisions = _get_divisions(db)
        all_clients = db.query(Client).filter_by(organization_id=org_id, is_active=True).order_by(Client.company_name).all()

        summary_json = {
            'Total Outstanding': f'${grand_total:,.2f}',
            'Current': f'${total_current:,.2f}',
            '1-30 Days': f'${total_1_30:,.2f}',
            '31-60 Days': f'${total_31_60:,.2f}',
            '61-90 Days': f'${total_61_90:,.2f}',
            '90+ Days': f'${total_90_plus:,.2f}',
            'Total Invoices': len(invoice_rows),
        }

        return render_template('reports/ar_aging.html',
            active_page='reports', user=current_user, divisions=divisions,
            report_title='AR Aging Report', report_category='Financial',
            date_label=f"As of {today_date.strftime('%B %d, %Y')}",
            selected_preset='custom', start_date=today_date, end_date=today_date,
            empty=len(invoice_rows) == 0,
            invoice_rows=sorted(invoice_rows, key=lambda x: x['days_overdue'], reverse=True),
            client_rows=client_rows,
            total_current=total_current, total_1_30=total_1_30,
            total_31_60=total_31_60, total_61_90=total_61_90,
            total_90_plus=total_90_plus, grand_total=grand_total,
            all_clients=all_clients, selected_client=client_id,
            summary_json=summary_json,
        )
    finally:
        db.close()


# ── AP Aging Report ───────────────────────────────────────────────────────────

@reports_bp.route('/reports/ap-aging')
@login_required
@role_required('admin', 'owner')
def ap_aging():
    db = get_session()
    try:
        from models.supplier_po import SupplierPurchaseOrder
        from models.vendor import Vendor
        vendor_id = request.args.get('vendor_id', type=int)
        today_date = date.today()

        q = db.query(SupplierPurchaseOrder).filter(
            SupplierPurchaseOrder.status.notin_(['cancelled', 'draft']),
            SupplierPurchaseOrder.amount_paid < SupplierPurchaseOrder.total,
        )
        if vendor_id:
            q = q.filter(SupplierPurchaseOrder.vendor_id == vendor_id)

        pos = [po for po in q.all() if po.balance_due > 0]

        def aging_bucket(po):
            if not po.payment_due_date:
                return 'current'
            d = po.payment_due_date
            days = (today_date - d).days
            if days <= 0: return 'current'
            if days <= 30: return '1_30'
            if days <= 60: return '31_60'
            if days <= 90: return '61_90'
            return '90_plus'

        po_rows = []
        for po in pos:
            bucket = aging_bucket(po)
            d = po.payment_due_date
            days_overdue = max(0, (today_date - d).days) if d else 0
            po_rows.append({
                'id': po.id, 'number': po.po_number,
                'vendor': po.vendor.company_name if po.vendor else '--',
                'vendor_id': po.vendor_id,
                'amount': float(po.balance_due),
                'total': float(po.total or 0),
                'due_date': d, 'days_overdue': days_overdue,
                'bucket': bucket, 'status': po.payment_status,
            })

        vendor_agg = {}
        for r in po_rows:
            vn = r['vendor']
            if vn not in vendor_agg:
                vendor_agg[vn] = {'vendor': vn, 'vendor_id': r['vendor_id'],
                                  'current': 0, '1_30': 0, '31_60': 0, '61_90': 0, '90_plus': 0, 'total': 0}
            vendor_agg[vn][r['bucket']] += r['amount']
            vendor_agg[vn]['total'] += r['amount']
        vendor_rows = sorted(vendor_agg.values(), key=lambda x: x['total'], reverse=True)

        total_current = sum(r['current'] for r in vendor_rows)
        total_1_30 = sum(r['1_30'] for r in vendor_rows)
        total_31_60 = sum(r['31_60'] for r in vendor_rows)
        total_61_90 = sum(r['61_90'] for r in vendor_rows)
        total_90_plus = sum(r['90_plus'] for r in vendor_rows)
        grand_total = sum(r['total'] for r in vendor_rows)

        divisions = _get_divisions(db)
        all_vendors = db.query(Vendor).filter_by(is_active=True).order_by(Vendor.company_name).all()

        summary_json = {
            'Total Payable': f'${grand_total:,.2f}',
            'Current': f'${total_current:,.2f}',
            '1-30 Days': f'${total_1_30:,.2f}',
            '31-60 Days': f'${total_31_60:,.2f}',
            '61-90 Days': f'${total_61_90:,.2f}',
            '90+ Days': f'${total_90_plus:,.2f}',
            'Total POs': len(po_rows),
        }

        return render_template('reports/ap_aging.html',
            active_page='reports', user=current_user, divisions=divisions,
            report_title='AP Aging Report', report_category='Financial',
            date_label=f"As of {today_date.strftime('%B %d, %Y')}",
            empty=len(po_rows) == 0,
            po_rows=sorted(po_rows, key=lambda x: x['days_overdue'], reverse=True),
            vendor_rows=vendor_rows,
            total_current=total_current, total_1_30=total_1_30,
            total_31_60=total_31_60, total_61_90=total_61_90,
            total_90_plus=total_90_plus, grand_total=grand_total,
            all_vendors=all_vendors, selected_vendor=vendor_id,
            summary_json=summary_json,
        )
    finally:
        db.close()


# ── Expense Report ────────────────────────────────────────────────────────────

@reports_bp.route('/reports/expenses')
@login_required
@role_required('admin', 'owner')
def expense_report():
    db = get_session()
    try:
        start_date, end_date, date_label = parse_date_range(request.args)
        selected_preset = request.args.get('preset', 'this_month')
        category_filter = request.args.get('category', '')
        status_filter = request.args.get('status', '')

        exp_q = db.query(Expense).filter(
            Expense.expense_date >= start_date,
            Expense.expense_date <= end_date,
        )
        if category_filter:
            exp_q = exp_q.filter(Expense.expense_category == category_filter)
        if status_filter:
            exp_q = exp_q.filter(Expense.status == status_filter)

        expenses = exp_q.order_by(Expense.expense_date.desc()).all()

        total_expenses = sum(float(e.total_amount or 0) for e in expenses)
        billable = sum(float(e.total_amount or 0) for e in expenses if e.is_billable)
        reimbursable = sum(float(e.total_amount or 0) for e in expenses if e.is_reimbursable)
        pending = sum(float(e.total_amount or 0) for e in expenses if e.status == 'submitted')

        # By category
        cat_agg = {}
        for e in expenses:
            c = e.expense_category or 'other'
            if c not in cat_agg:
                cat_agg[c] = {'category': c, 'count': 0, 'total': 0}
            cat_agg[c]['count'] += 1
            cat_agg[c]['total'] += float(e.total_amount or 0)
        category_rows = sorted(cat_agg.values(), key=lambda x: x['total'], reverse=True)

        # By paid_by user
        user_agg = {}
        for e in expenses:
            uname = e.paid_by_user.full_name if e.paid_by_user else 'Unknown'
            if uname not in user_agg:
                user_agg[uname] = {'name': uname, 'count': 0, 'total': 0}
            user_agg[uname]['count'] += 1
            user_agg[uname]['total'] += float(e.total_amount or 0)
        employee_rows = sorted(user_agg.values(), key=lambda x: x['total'], reverse=True)

        # Monthly
        months_data = get_12_month_labels()
        month_labels = [m.strftime('%b %Y') for m in months_data]
        monthly_amounts = []
        for m in months_data:
            m_start = m.replace(day=1)
            m_end = (m_start + relativedelta(months=1)) - timedelta(days=1)
            m_total = sum(float(e.total_amount or 0) for e in db.query(Expense).filter(
                Expense.expense_date >= m_start, Expense.expense_date <= m_end).all())
            monthly_amounts.append(round(m_total, 2))

        from models.expense import EXPENSE_CATEGORIES
        divisions = _get_divisions(db)

        summary_json = {
            'Total Expenses': f'${total_expenses:,.2f}',
            'Billable': f'${billable:,.2f}',
            'Reimbursable': f'${reimbursable:,.2f}',
            'Pending': f'${pending:,.2f}',
            'Count': len(expenses),
        }

        return render_template('reports/expense_report.html',
            active_page='reports', user=current_user, divisions=divisions,
            report_title='Expense Report', report_category='Financial',
            date_label=date_label, selected_preset=selected_preset,
            start_date=start_date, end_date=end_date,
            empty=len(expenses) == 0,
            total_expenses=total_expenses, billable=billable,
            reimbursable=reimbursable, pending=pending,
            category_rows=category_rows, employee_rows=employee_rows,
            expenses=expenses,
            month_labels=month_labels, monthly_amounts=monthly_amounts,
            expense_categories=EXPENSE_CATEGORIES,
            selected_category=category_filter, selected_status=status_filter,
            summary_json=summary_json,
        )
    finally:
        db.close()


# ── Job Performance Report ─────────────────────────────────────────────────────

@reports_bp.route('/reports/job-performance')
@login_required
def job_performance():
    db = get_session()
    try:
        org_id = current_user.organization_id
        start_date, end_date, date_label = parse_date_range(request.args)
        selected_preset = request.args.get('preset', 'this_month')
        division_id = request.args.get('division_id', type=int)
        job_type = request.args.get('job_type', '')
        status_filter = request.args.get('status', '')

        job_q = db.query(Job).filter(
            Job.organization_id == org_id,
            Job.created_at >= datetime.combine(start_date, datetime.min.time()),
            Job.created_at <= datetime.combine(end_date, datetime.max.time()),
        )
        if division_id:
            job_q = job_q.filter(Job.division_id == division_id)
        if job_type:
            job_q = job_q.filter(Job.job_type == job_type)
        if status_filter:
            job_q = job_q.filter(Job.status == status_filter)

        jobs = job_q.order_by(Job.created_at.desc()).all()

        job_rows = []
        for job in jobs:
            duration = None
            if job.completed_at and job.created_at:
                duration = (job.completed_at - job.created_at).days

            on_time = None
            if job.status in ('completed', 'invoiced') and job.scheduled_end and job.completed_at:
                target = job.scheduled_end.date() if hasattr(job.scheduled_end, 'date') else job.scheduled_end
                completed = job.completed_at.date() if hasattr(job.completed_at, 'date') else job.completed_at
                on_time = completed <= target

            actual_hours = float(db.query(func.coalesce(func.sum(TimeEntry.duration_hours), 0)).filter(
                TimeEntry.job_id == job.id).scalar() or 0)

            job_rows.append({
                'id': job.id, 'number': job.job_number,
                'client': job.client.display_name if job.client else '--',
                'type': job.job_type or '--', 'status': job.status,
                'duration': duration, 'actual_hours': round(actual_hours, 1),
                'estimated': float(job.estimated_amount or 0),
                'on_time': on_time, 'created_at': job.created_at,
            })

        total = len(jobs)
        completed = sum(1 for j in jobs if j.status in ('completed', 'invoiced'))
        in_progress = sum(1 for j in jobs if j.status == 'in_progress')
        durations = [r['duration'] for r in job_rows if r['duration'] is not None]
        avg_duration = round(safe_divide(sum(durations), len(durations)), 1) if durations else 0
        on_time_jobs = [r for r in job_rows if r['on_time'] is not None]
        on_time_pct = round(safe_divide(sum(1 for r in on_time_jobs if r['on_time']), len(on_time_jobs)) * 100, 1) if on_time_jobs else 0

        status_counts = {}
        for j in jobs:
            s = j.status or 'unknown'
            status_counts[s] = status_counts.get(s, 0) + 1

        # Monthly completed
        months_data = get_12_month_labels()
        month_labels = [m.strftime('%b %Y') for m in months_data]
        monthly_completed = []
        for m in months_data:
            m_start = m.replace(day=1)
            m_end = (m_start + relativedelta(months=1)) - timedelta(days=1)
            count = db.query(Job).filter(
                Job.organization_id == org_id,
                Job.completed_at >= datetime.combine(m_start, datetime.min.time()),
                Job.completed_at <= datetime.combine(m_end, datetime.max.time()),
            ).count()
            monthly_completed.append(count)

        # Job types for filter
        job_types = sorted(set(j.job_type for j in db.query(Job).filter(
            Job.organization_id == org_id, Job.job_type != None).all() if j.job_type))

        divisions = _get_divisions(db)

        summary_json = {
            'Total Jobs': total, 'Completed': completed, 'In Progress': in_progress,
            'Avg Duration (days)': avg_duration, 'On-Time Rate': f'{on_time_pct}%',
        }

        return render_template('reports/job_performance.html',
            active_page='reports', user=current_user, divisions=divisions,
            report_title='Job Performance', report_category='Job & Project',
            date_label=date_label, selected_preset=selected_preset,
            start_date=start_date, end_date=end_date, empty=total == 0,
            total=total, completed=completed, in_progress=in_progress,
            avg_duration=avg_duration, on_time_pct=on_time_pct,
            job_rows=job_rows, status_counts=status_counts,
            month_labels=month_labels, monthly_completed=monthly_completed,
            all_divisions=divisions, job_types=job_types,
            selected_division=division_id, selected_job_type=job_type,
            selected_status=status_filter, summary_json=summary_json,
        )
    finally:
        db.close()


# ── Project Budget Report ─────────────────────────────────────────────────────

@reports_bp.route('/reports/project-budget')
@login_required
def project_budget():
    db = get_session()
    try:
        org_id = current_user.organization_id
        status_filter = request.args.get('status', '')
        client_id = request.args.get('client_id', type=int)

        from models.job_material import JobMaterial

        proj_q = db.query(Project).filter(Project.organization_id == org_id)
        if status_filter:
            proj_q = proj_q.filter(Project.status == status_filter)
        if client_id:
            proj_q = proj_q.filter(Project.client_id == client_id)

        projects = proj_q.order_by(Project.created_at.desc()).all()

        project_rows = []
        for proj in projects:
            proj_jobs = db.query(Job).filter_by(project_id=proj.id).all()
            proj_job_ids = [j.id for j in proj_jobs]

            if proj_job_ids:
                labor_cost = float(db.query(func.coalesce(func.sum(TimeEntry.labor_cost), 0)).filter(
                    TimeEntry.job_id.in_(proj_job_ids)).scalar() or 0)
                mat_cost = float(db.query(func.coalesce(func.sum(JobMaterial.total_cost), 0)).filter(
                    JobMaterial.job_id.in_(proj_job_ids)).scalar() or 0)
                exp_cost = float(db.query(func.coalesce(func.sum(Expense.total_amount), 0)).filter(
                    Expense.job_id.in_(proj_job_ids)).scalar() or 0)
            else:
                labor_cost = mat_cost = exp_cost = 0

            total_spent = labor_cost + mat_cost + exp_cost
            budget = float(proj.approved_budget or proj.estimated_budget or 0)
            variance = budget - total_spent

            project_rows.append({
                'id': proj.id, 'title': proj.title,
                'client': proj.client.display_name if proj.client else '--',
                'budget': budget, 'spent': total_spent, 'variance': variance,
                'pct_complete': proj.percent_complete or 0,
                'jobs_count': len(proj_jobs), 'status': proj.status or 'active',
                'over_budget': total_spent > budget and budget > 0,
                'pct_spent': round(safe_divide(total_spent, budget) * 100, 1) if budget else 0,
            })

        project_rows.sort(key=lambda x: (not x['over_budget'], -x['spent']))

        total_budget = sum(r['budget'] for r in project_rows)
        total_spent = sum(r['spent'] for r in project_rows)
        total_variance = total_budget - total_spent
        active_count = sum(1 for r in project_rows if r['status'] == 'active')

        divisions = _get_divisions(db)
        all_clients = db.query(Client).filter_by(organization_id=org_id, is_active=True).order_by(Client.company_name).all()

        summary_json = {
            'Projects': len(project_rows), 'Total Budget': f'${total_budget:,.2f}',
            'Total Spent': f'${total_spent:,.2f}', 'Variance': f'${total_variance:,.2f}',
            'Over Budget': sum(1 for r in project_rows if r['over_budget']),
        }

        return render_template('reports/project_budget.html',
            active_page='reports', user=current_user, divisions=divisions,
            report_title='Project Budget', report_category='Job & Project',
            date_label=f'{len(project_rows)} projects', selected_preset='this_year',
            start_date=date.today(), end_date=date.today(), empty=not project_rows,
            project_rows=project_rows, total_budget=total_budget,
            total_spent=total_spent, total_variance=total_variance,
            active_count=active_count, all_clients=all_clients,
            selected_client=client_id, selected_status=status_filter,
            summary_json=summary_json,
        )
    finally:
        db.close()


# ── Change Order Report ───────────────────────────────────────────────────────

@reports_bp.route('/reports/change-orders')
@login_required
def change_order_report():
    db = get_session()
    try:
        org_id = current_user.organization_id
        start_date, end_date, date_label = parse_date_range(request.args)
        selected_preset = request.args.get('preset', 'this_month')
        status_filter = request.args.get('status', '')

        from models.change_order import ChangeOrder

        co_q = db.query(ChangeOrder).join(Job).filter(
            Job.organization_id == org_id,
            ChangeOrder.created_at >= datetime.combine(start_date, datetime.min.time()),
            ChangeOrder.created_at <= datetime.combine(end_date, datetime.max.time()),
        )
        if status_filter:
            co_q = co_q.filter(ChangeOrder.status == status_filter)

        cos = co_q.order_by(ChangeOrder.created_at.desc()).all()

        total_cos = len(cos)
        approved_count = sum(1 for c in cos if c.status == 'approved')
        pending_count = sum(1 for c in cos if c.status in ('submitted', 'pending_approval'))
        total_value = sum(c.cost_difference for c in cos if c.status == 'approved')
        approval_rate = round(safe_divide(approved_count, total_cos) * 100, 1) if total_cos else 0

        co_rows = []
        for co in cos:
            days_to_approve = None
            if co.internal_approved_date and co.created_at:
                days_to_approve = (co.internal_approved_date - co.created_at).days

            co_rows.append({
                'id': co.id, 'number': co.change_order_number,
                'job': co.job.job_number if co.job else '--',
                'client': co.job.client.display_name if co.job and co.job.client else '--',
                'reason': co.reason or '--',
                'amount': co.cost_difference,
                'status': co.status, 'days_to_approve': days_to_approve,
                'created_at': co.created_at,
            })

        # By reason
        reason_agg = {}
        for r in co_rows:
            reason = r['reason']
            if reason not in reason_agg:
                reason_agg[reason] = {'reason': reason, 'count': 0, 'total_value': 0}
            reason_agg[reason]['count'] += 1
            reason_agg[reason]['total_value'] += abs(r['amount'])
        reason_rows = sorted(reason_agg.values(), key=lambda x: x['count'], reverse=True)

        # Monthly
        months_data = get_12_month_labels()
        month_labels = [m.strftime('%b %Y') for m in months_data]
        monthly_count = []
        for m in months_data:
            m_start = m.replace(day=1)
            m_end = (m_start + relativedelta(months=1)) - timedelta(days=1)
            count = db.query(ChangeOrder).join(Job).filter(
                Job.organization_id == org_id,
                ChangeOrder.created_at >= datetime.combine(m_start, datetime.min.time()),
                ChangeOrder.created_at <= datetime.combine(m_end, datetime.max.time()),
            ).count()
            monthly_count.append(count)

        divisions = _get_divisions(db)

        summary_json = {
            'Total COs': total_cos, 'Approved': approved_count,
            'Pending': pending_count, 'Approved Value': f'${total_value:,.2f}',
            'Approval Rate': f'{approval_rate}%',
        }

        return render_template('reports/change_orders_report.html',
            active_page='reports', user=current_user, divisions=divisions,
            report_title='Change Order Report', report_category='Job & Project',
            date_label=date_label, selected_preset=selected_preset,
            start_date=start_date, end_date=end_date, empty=total_cos == 0,
            total_cos=total_cos, approved_count=approved_count,
            pending_count=pending_count, total_value=total_value,
            approval_rate=approval_rate,
            co_rows=co_rows, reason_rows=reason_rows,
            month_labels=month_labels, monthly_count=monthly_count,
            selected_status=status_filter, summary_json=summary_json,
        )
    finally:
        db.close()


# ── Tech Performance Report ───────────────────────────────────────────────────

@reports_bp.route('/reports/tech-performance')
@login_required
def tech_performance():
    db = get_session()
    try:
        org_id = current_user.organization_id
        start_date, end_date, date_label = parse_date_range(request.args)
        selected_preset = request.args.get('preset', 'this_month')
        division_id = request.args.get('division_id', type=int)

        tech_q = db.query(Technician).filter_by(organization_id=org_id, is_active=True)
        if division_id:
            tech_q = tech_q.filter(Technician.division_id == division_id)
        techs = tech_q.all()

        from models.callback import Callback
        tech_rows = []
        for tech in techs:
            entries = db.query(TimeEntry).filter(
                TimeEntry.technician_id == tech.id,
                TimeEntry.date >= start_date, TimeEntry.date <= end_date,
            ).all()
            job_ids = list(set(e.job_id for e in entries if e.job_id))
            total_hours = sum(float(e.duration_hours or 0) for e in entries)
            billable_hours = sum(float(e.duration_hours or 0) for e in entries if e.billable)
            jobs_completed = db.query(Job).filter(Job.id.in_(job_ids), Job.status.in_(['completed', 'invoiced'])).count() if job_ids else 0
            revenue = float(db.query(func.coalesce(func.sum(Invoice.total), 0)).filter(Invoice.job_id.in_(job_ids)).scalar() or 0) if job_ids else 0
            callbacks = db.query(Callback).filter(Callback.original_job_id.in_(job_ids)).count() if job_ids else 0
            callback_rate = round(safe_divide(callbacks, len(job_ids)) * 100, 1) if job_ids else 0
            workdays = max(1, (end_date - start_date).days * 5 // 7)
            utilization = round(safe_divide(billable_hours, workdays * 8) * 100, 1)

            tech_rows.append({
                'id': tech.id, 'name': tech.full_name,
                'jobs_completed': jobs_completed, 'job_count': len(job_ids),
                'total_hours': round(total_hours, 1), 'billable_hours': round(billable_hours, 1),
                'utilization': utilization, 'revenue': round(revenue, 2),
                'callbacks': callbacks, 'callback_rate': callback_rate,
            })
        tech_rows.sort(key=lambda x: x['revenue'], reverse=True)

        divisions = _get_divisions(db)
        summary_json = {
            'Technicians': len(tech_rows),
            'Avg Utilization': f"{round(safe_divide(sum(r['utilization'] for r in tech_rows), len(tech_rows)), 1) if tech_rows else 0}%",
        }

        return render_template('reports/tech_performance.html',
            active_page='reports', user=current_user, divisions=divisions,
            report_title='Technician Performance', report_category='Labor',
            date_label=date_label, selected_preset=selected_preset,
            start_date=start_date, end_date=end_date, empty=not tech_rows,
            tech_rows=tech_rows, all_divisions=divisions, all_techs=techs,
            selected_division=division_id, summary_json=summary_json,
        )
    finally:
        db.close()


# ── Labor Utilization Report ──────────────────────────────────────────────────

@reports_bp.route('/reports/labor-utilization')
@login_required
def labor_utilization():
    db = get_session()
    try:
        start_date, end_date, date_label = parse_date_range(request.args)
        selected_preset = request.args.get('preset', 'this_month')

        entries = db.query(TimeEntry).filter(
            TimeEntry.date >= start_date, TimeEntry.date <= end_date,
        ).all()

        tech_agg = {}
        for e in entries:
            tid = e.technician_id
            if tid not in tech_agg:
                tech = db.query(Technician).filter_by(id=tid).first()
                tech_agg[tid] = {'name': tech.full_name if tech else f'Tech {tid}',
                                 'total': 0, 'billable': 0, 'non_billable': 0}
            hours = float(e.duration_hours or 0)
            tech_agg[tid]['total'] += hours
            if e.billable:
                tech_agg[tid]['billable'] += hours
            else:
                tech_agg[tid]['non_billable'] += hours

        tech_rows = []
        for t in tech_agg.values():
            t['billable_pct'] = round(safe_divide(t['billable'], t['total']) * 100, 1)
            tech_rows.append(t)
        tech_rows.sort(key=lambda x: x['total'], reverse=True)

        total_hours = sum(r['total'] for r in tech_rows)
        billable_hours = sum(r['billable'] for r in tech_rows)
        overall_util = round(safe_divide(billable_hours, total_hours) * 100, 1)

        divisions = _get_divisions(db)
        summary_json = {'Total Hours': round(total_hours, 1), 'Billable': round(billable_hours, 1), 'Utilization': f'{overall_util}%'}

        return render_template('reports/labor_utilization.html',
            active_page='reports', user=current_user, divisions=divisions,
            report_title='Labor Utilization', report_category='Labor',
            date_label=date_label, selected_preset=selected_preset,
            start_date=start_date, end_date=end_date, empty=not entries,
            total_hours=round(total_hours, 1), billable_hours=round(billable_hours, 1),
            non_billable_hours=round(total_hours - billable_hours, 1),
            overall_util=overall_util, tech_rows=tech_rows, summary_json=summary_json,
        )
    finally:
        db.close()


# ── Client Activity Report ────────────────────────────────────────────────────

@reports_bp.route('/reports/client-activity')
@login_required
def client_activity():
    db = get_session()
    try:
        org_id = current_user.organization_id
        start_date, end_date, date_label = parse_date_range(request.args)
        selected_preset = request.args.get('preset', 'this_year')

        all_clients = db.query(Client).filter_by(organization_id=org_id, is_active=True).all()
        client_rows = []
        active_count = 0
        for c in all_clients:
            period_jobs = db.query(Job).filter(
                Job.client_id == c.id,
                Job.created_at >= datetime.combine(start_date, datetime.min.time()),
                Job.created_at <= datetime.combine(end_date, datetime.max.time()),
            ).count()
            total_jobs = db.query(Job).filter_by(client_id=c.id).count()
            revenue = float(db.query(func.coalesce(func.sum(Invoice.total), 0)).filter(
                Invoice.client_id == c.id).scalar() or 0)
            outstanding = float(db.query(func.coalesce(func.sum(Invoice.balance_due), 0)).filter(
                Invoice.client_id == c.id, Invoice.status.in_(['sent', 'overdue', 'partial'])).scalar() or 0)

            if period_jobs > 0:
                active_count += 1
            client_rows.append({
                'id': c.id, 'name': c.display_name,
                'jobs_period': period_jobs, 'jobs_total': total_jobs,
                'revenue': revenue, 'outstanding': outstanding,
                'active': period_jobs > 0,
            })
        client_rows.sort(key=lambda x: x['revenue'], reverse=True)

        divisions = _get_divisions(db)
        summary_json = {'Total': len(all_clients), 'Active': active_count, 'Inactive': len(all_clients) - active_count}

        return render_template('reports/client_activity.html',
            active_page='reports', user=current_user, divisions=divisions,
            report_title='Client Activity', report_category='Clients',
            date_label=date_label, selected_preset=selected_preset,
            start_date=start_date, end_date=end_date, empty=not all_clients,
            total_clients=len(all_clients), active_count=active_count,
            inactive_count=len(all_clients) - active_count,
            client_rows=client_rows, summary_json=summary_json,
        )
    finally:
        db.close()


# ── Sales Pipeline Report ─────────────────────────────────────────────────────

@reports_bp.route('/reports/sales-pipeline')
@login_required
def sales_pipeline():
    db = get_session()
    try:
        org_id = current_user.organization_id
        start_date, end_date, date_label = parse_date_range(request.args)
        selected_preset = request.args.get('preset', 'this_quarter')

        from models.quote import Quote
        quotes = db.query(Quote).filter(
            Quote.organization_id == org_id,
            Quote.created_at >= datetime.combine(start_date, datetime.min.time()),
            Quote.created_at <= datetime.combine(end_date, datetime.max.time()),
        ).order_by(Quote.created_at.desc()).all()

        total = len(quotes)
        sent = sum(1 for q in quotes if q.status in ('sent', 'approved', 'converted', 'rejected'))
        approved = sum(1 for q in quotes if q.status in ('approved', 'converted'))
        pipeline_value = sum(float(q.total or 0) for q in quotes if q.status == 'sent')
        win_rate = round(safe_divide(approved, sent) * 100, 1) if sent else 0
        avg_deal = round(safe_divide(sum(float(q.total or 0) for q in quotes), total), 2) if total else 0

        quote_rows = [{'id': q.id, 'number': q.quote_number,
                       'client': q.client.display_name if q.client else '--',
                       'value': float(q.total or 0), 'status': q.status,
                       'created': q.created_at} for q in quotes]

        # Monthly
        months_data = get_12_month_labels()
        month_labels = [m.strftime('%b %Y') for m in months_data]
        monthly_sent, monthly_won = [], []
        for m in months_data:
            m_start = m.replace(day=1)
            m_end = (m_start + relativedelta(months=1)) - timedelta(days=1)
            m_qs = db.query(Quote).filter(
                Quote.organization_id == org_id,
                Quote.created_at >= datetime.combine(m_start, datetime.min.time()),
                Quote.created_at <= datetime.combine(m_end, datetime.max.time()),
            ).all()
            monthly_sent.append(len(m_qs))
            monthly_won.append(sum(1 for q in m_qs if q.status in ('approved', 'converted')))

        divisions = _get_divisions(db)
        summary_json = {'Total Quotes': total, 'Win Rate': f'{win_rate}%', 'Pipeline': f'${pipeline_value:,.2f}', 'Avg Deal': f'${avg_deal:,.2f}'}

        return render_template('reports/sales_pipeline.html',
            active_page='reports', user=current_user, divisions=divisions,
            report_title='Sales Pipeline', report_category='Sales',
            date_label=date_label, selected_preset=selected_preset,
            start_date=start_date, end_date=end_date, empty=total == 0,
            total=total, sent=sent, approved=approved,
            pipeline_value=pipeline_value, win_rate=win_rate, avg_deal=avg_deal,
            quote_rows=quote_rows,
            month_labels=month_labels, monthly_sent=monthly_sent, monthly_won=monthly_won,
            summary_json=summary_json,
        )
    finally:
        db.close()


# ── Inventory Valuation ───────────────────────────────────────────────────────

@reports_bp.route('/reports/inventory-valuation')
@login_required
def inventory_valuation():
    db = get_session()
    try:
        from models.inventory import InventoryStock, InventoryLocation
        from models.part import Part

        stocks = db.query(InventoryStock).join(Part).all()

        total_value = 0
        items_below_reorder = 0
        total_skus = set()
        location_agg = {}
        category_agg = {}
        part_rows = []

        for s in stocks:
            qty = s.quantity_on_hand or 0
            cost = float(s.part.cost_price or 0)
            value = qty * cost
            total_value += value
            total_skus.add(s.part_id)

            reorder = s.part.reorder_quantity or 0
            if qty <= reorder and reorder > 0:
                items_below_reorder += 1

            loc = s.location.name if s.location else 'Unassigned'
            if loc not in location_agg:
                location_agg[loc] = {'location': loc, 'items': 0, 'value': 0}
            location_agg[loc]['items'] += 1
            location_agg[loc]['value'] += value

            cat = s.part.category or 'other'
            if cat not in category_agg:
                category_agg[cat] = {'category': cat, 'value': 0, 'items': 0}
            category_agg[cat]['value'] += value
            category_agg[cat]['items'] += 1

            part_rows.append({
                'part_number': s.part.part_number, 'name': s.part.name,
                'location': loc, 'qty': qty, 'unit_cost': cost,
                'value': round(value, 2), 'reorder': reorder,
                'below_reorder': qty <= reorder and reorder > 0,
            })

        part_rows.sort(key=lambda x: x['value'], reverse=True)
        location_rows = sorted(location_agg.values(), key=lambda x: x['value'], reverse=True)
        category_rows = sorted(category_agg.values(), key=lambda x: x['value'], reverse=True)

        divisions = _get_divisions(db)
        summary_json = {'Total Value': f'${total_value:,.2f}', 'SKUs': len(total_skus), 'Below Reorder': items_below_reorder}

        return render_template('reports/inventory_valuation.html',
            active_page='reports', user=current_user, divisions=divisions,
            report_title='Inventory Valuation', report_category='Inventory',
            date_label=f"As of {date.today().strftime('%B %d, %Y')}",
            selected_preset='custom', start_date=date.today(), end_date=date.today(),
            empty=not part_rows, total_value=round(total_value, 2),
            items_below_reorder=items_below_reorder, total_skus=len(total_skus),
            part_rows=part_rows, location_rows=location_rows, category_rows=category_rows,
            summary_json=summary_json,
        )
    finally:
        db.close()


# ── Compliance Report ─────────────────────────────────────────────────────────

@reports_bp.route('/reports/compliance')
@login_required
def compliance_report():
    db = get_session()
    try:
        today_date = date.today()
        threshold_90 = today_date + timedelta(days=90)
        threshold_30 = today_date + timedelta(days=30)

        from models.permit import Permit
        from models.certification import TechnicianCertification
        from models.insurance import InsurancePolicy

        expiring = []

        # Permits
        permits = db.query(Permit).filter(
            Permit.expiry_date != None, Permit.expiry_date <= threshold_90,
            Permit.expiry_date >= today_date,
        ).all()
        for p in permits:
            days = (p.expiry_date - today_date).days
            expiring.append({'type': 'Permit', 'name': p.permit_number or f'Permit {p.id}',
                'entity': p.job.job_number if p.job else '--', 'expiry': p.expiry_date,
                'days_until': days, 'status': 'Critical' if days <= 7 else ('Warning' if days <= 30 else 'Notice')})

        # Certifications
        certs = db.query(TechnicianCertification).filter(
            TechnicianCertification.expiry_date != None, TechnicianCertification.expiry_date <= threshold_90,
            TechnicianCertification.expiry_date >= today_date,
        ).all()
        for c in certs:
            days = (c.expiry_date - today_date).days
            tech = db.query(Technician).filter_by(id=c.technician_id).first()
            expiring.append({'type': 'Certification', 'name': c.certification_name,
                'entity': tech.full_name if tech else '--', 'expiry': c.expiry_date,
                'days_until': days, 'status': 'Critical' if days <= 7 else ('Warning' if days <= 30 else 'Notice')})

        # Insurance
        policies = db.query(InsurancePolicy).filter(
            InsurancePolicy.end_date != None, InsurancePolicy.end_date <= threshold_90,
            InsurancePolicy.end_date >= today_date,
        ).all()
        for p in policies:
            days = (p.end_date - today_date).days
            expiring.append({'type': 'Insurance', 'name': p.policy_number,
                'entity': p.policy_type or '--', 'expiry': p.end_date,
                'days_until': days, 'status': 'Critical' if days <= 7 else ('Warning' if days <= 30 else 'Notice')})

        expiring.sort(key=lambda x: x['days_until'])

        critical = sum(1 for e in expiring if e['status'] == 'Critical')
        warning = sum(1 for e in expiring if e['status'] == 'Warning')

        divisions = _get_divisions(db)
        summary_json = {'Expiring (90d)': len(expiring), 'Critical': critical, 'Warning': warning}

        return render_template('reports/compliance_report.html',
            active_page='reports', user=current_user, divisions=divisions,
            report_title='Compliance Status', report_category='Compliance',
            date_label=f"As of {today_date.strftime('%B %d, %Y')}",
            selected_preset='custom', start_date=today_date, end_date=today_date,
            empty=not expiring, expiring=expiring,
            critical=critical, warning=warning, total_expiring=len(expiring),
            summary_json=summary_json,
        )
    finally:
        db.close()


# ── Quality & Callback Report ─────────────────────────────────────────────────

@reports_bp.route('/reports/quality')
@login_required
def quality_report():
    db = get_session()
    try:
        org_id = current_user.organization_id
        start_date, end_date, date_label = parse_date_range(request.args)
        selected_preset = request.args.get('preset', 'this_quarter')

        from models.callback import Callback

        callbacks = db.query(Callback).filter(
            Callback.created_at >= datetime.combine(start_date, datetime.min.time()),
            Callback.created_at <= datetime.combine(end_date, datetime.max.time()),
        ).all()

        total_jobs = db.query(Job).filter(
            Job.organization_id == org_id,
            Job.created_at >= datetime.combine(start_date, datetime.min.time()),
            Job.created_at <= datetime.combine(end_date, datetime.max.time()),
        ).count()

        callback_rate = round(safe_divide(len(callbacks), total_jobs) * 100, 1)

        callback_rows = []
        reason_agg = {}
        for cb in callbacks:
            reason = cb.reason or 'other'
            if reason not in reason_agg:
                reason_agg[reason] = {'reason': reason, 'count': 0}
            reason_agg[reason]['count'] += 1
            callback_rows.append({
                'id': cb.id, 'original_job': cb.original_job.job_number if cb.original_job else '--',
                'reason': cb.reason_display, 'severity': cb.severity or '--',
                'tech': cb.responsible_technician.full_name if cb.responsible_technician else '--',
                'status': cb.status, 'created_at': cb.created_at,
            })
        reason_rows = sorted(reason_agg.values(), key=lambda x: x['count'], reverse=True)

        # Monthly
        months_data = get_12_month_labels()
        month_labels = [m.strftime('%b %Y') for m in months_data]
        monthly_callbacks = []
        for m in months_data:
            m_start = m.replace(day=1)
            m_end = (m_start + relativedelta(months=1)) - timedelta(days=1)
            count = db.query(Callback).filter(
                Callback.created_at >= datetime.combine(m_start, datetime.min.time()),
                Callback.created_at <= datetime.combine(m_end, datetime.max.time()),
            ).count()
            monthly_callbacks.append(count)

        divisions = _get_divisions(db)
        summary_json = {'Callback Rate': f'{callback_rate}%', 'Callbacks': len(callbacks), 'Jobs': total_jobs}

        return render_template('reports/quality_report.html',
            active_page='reports', user=current_user, divisions=divisions,
            report_title='Quality & Callbacks', report_category='Compliance',
            date_label=date_label, selected_preset=selected_preset,
            start_date=start_date, end_date=end_date, empty=not callbacks,
            callback_rate=callback_rate, total_callbacks=len(callbacks),
            total_jobs=total_jobs,
            callback_rows=callback_rows, reason_rows=reason_rows,
            month_labels=month_labels, monthly_callbacks=monthly_callbacks,
            summary_json=summary_json,
        )
    finally:
        db.close()


# ── Capacity Planning Report ──────────────────────────────────────────────────

@reports_bp.route('/reports/capacity')
@login_required
def capacity_planning():
    db = get_session()
    try:
        org_id = current_user.organization_id
        weeks_ahead = request.args.get('weeks_ahead', 4, type=int)
        division_id = request.args.get('division_id', type=int)
        today_date = date.today()
        end_date = today_date + timedelta(weeks=weeks_ahead)
        date_label = f"Next {weeks_ahead} weeks"

        tech_q = db.query(Technician).filter_by(organization_id=org_id, is_active=True)
        if division_id:
            tech_q = tech_q.filter(Technician.division_id == division_id)
        techs = tech_q.all()

        hours_per_day = 8
        tech_rows = []
        week_start = today_date - timedelta(days=today_date.weekday())
        week_end = week_start + timedelta(days=6)

        for tech in techs:
            scheduled = float(db.query(func.coalesce(func.sum(TimeEntry.duration_hours), 0)).filter(
                TimeEntry.technician_id == tech.id,
                TimeEntry.date >= week_start, TimeEntry.date <= week_end,
            ).scalar() or 0)
            capacity = hours_per_day * 5
            available = max(0, capacity - scheduled)
            utilization = round(safe_divide(scheduled, capacity) * 100, 1)
            tech_rows.append({
                'name': tech.full_name, 'capacity': capacity,
                'scheduled': round(scheduled, 1), 'available': round(available, 1),
                'utilization': utilization,
                'over_booked': utilization > 100, 'under_utilized': utilization < 50,
            })
        tech_rows.sort(key=lambda x: x['utilization'], reverse=True)

        # Weekly forecast
        week_rows = []
        for w in range(weeks_ahead):
            ws = today_date + timedelta(weeks=w) - timedelta(days=(today_date + timedelta(weeks=w)).weekday())
            we = ws + timedelta(days=6)
            sched = float(db.query(func.coalesce(func.sum(TimeEntry.duration_hours), 0)).filter(
                TimeEntry.date >= ws, TimeEntry.date <= we).scalar() or 0)
            cap = hours_per_day * 5 * len(techs)
            week_rows.append({
                'week': ws.strftime('Week of %b %d'), 'capacity': cap,
                'scheduled': round(sched, 1), 'available': round(max(0, cap - sched), 1),
                'utilization': round(safe_divide(sched, cap) * 100, 1) if cap else 0,
            })

        divisions = _get_divisions(db)
        total_capacity = hours_per_day * 5 * len(techs)
        summary_json = {'Technicians': len(techs), 'Capacity/Week': total_capacity}

        return render_template('reports/capacity_planning.html',
            active_page='reports', user=current_user, divisions=divisions,
            report_title='Capacity Planning', report_category='Operations',
            date_label=date_label, selected_preset='custom',
            start_date=today_date, end_date=end_date, empty=not techs,
            tech_rows=tech_rows, week_rows=week_rows, weeks_ahead=weeks_ahead,
            total_capacity=total_capacity, all_divisions=divisions,
            selected_division=division_id, summary_json=summary_json,
        )
    finally:
        db.close()


# ── SLA Performance Report ────────────────────────────────────────────────────

@reports_bp.route('/reports/sla-performance')
@login_required
def sla_performance():
    db = get_session()
    try:
        org_id = current_user.organization_id
        start_date, end_date, date_label = parse_date_range(request.args)
        selected_preset = request.args.get('preset', 'this_month')

        from models.sla import SLA
        sla_jobs = db.query(Job).filter(
            Job.organization_id == org_id,
            Job.sla_id != None,
            Job.created_at >= datetime.combine(start_date, datetime.min.time()),
            Job.created_at <= datetime.combine(end_date, datetime.max.time()),
        ).all()

        total = len(sla_jobs)
        resp_met = res_met = 0
        sla_rows = []
        for job in sla_jobs:
            sla = db.query(SLA).filter_by(id=job.sla_id).first()
            if not sla:
                continue
            resp_target = float(sla.response_time_hours or 24)
            res_target = float(sla.resolution_time_hours or 72)

            first_entry = db.query(TimeEntry).filter_by(job_id=job.id).order_by(TimeEntry.date).first()
            actual_resp = None
            if first_entry and job.created_at:
                actual_resp = round((datetime.combine(first_entry.date, datetime.min.time()) - job.created_at).total_seconds() / 3600, 1)
            actual_res = None
            if job.completed_at and job.created_at:
                actual_res = round((job.completed_at - job.created_at).total_seconds() / 3600, 1)

            r_met = actual_resp is not None and actual_resp <= resp_target
            s_met = actual_res is not None and actual_res <= res_target
            if r_met: resp_met += 1
            if s_met: res_met += 1

            sla_rows.append({
                'job_id': job.id, 'job_number': job.job_number,
                'client': job.client.display_name if job.client else '--',
                'resp_target': resp_target, 'resp_actual': actual_resp, 'resp_met': r_met,
                'res_target': res_target, 'res_actual': actual_res, 'res_met': s_met,
            })

        resp_pct = round(safe_divide(resp_met, total) * 100, 1)
        res_pct = round(safe_divide(res_met, total) * 100, 1)

        divisions = _get_divisions(db)
        summary_json = {'SLA Jobs': total, 'Response Met': f'{resp_pct}%', 'Resolution Met': f'{res_pct}%'}

        return render_template('reports/sla_performance.html',
            active_page='reports', user=current_user, divisions=divisions,
            report_title='SLA Performance', report_category='Operations',
            date_label=date_label, selected_preset=selected_preset,
            start_date=start_date, end_date=end_date, empty=total == 0,
            total=total, resp_pct=resp_pct, res_pct=res_pct,
            sla_rows=sla_rows, summary_json=summary_json,
        )
    finally:
        db.close()


# ── Fleet Report ──────────────────────────────────────────────────────────────

@reports_bp.route('/reports/fleet')
@login_required
def fleet_report():
    db = get_session()
    try:
        start_date, end_date, date_label = parse_date_range(request.args)
        selected_preset = request.args.get('preset', 'this_month')

        from models.vehicle_profile import VehicleProfile
        from models.vehicle_mileage_log import VehicleMileageLog
        from models.vehicle_fuel_log import VehicleFuelLog

        vehicles = db.query(VehicleProfile).all()
        vehicle_rows = []
        total_miles = total_fuel_cost = total_gallons = 0

        for v in vehicles:
            ml = db.query(VehicleMileageLog).filter(
                VehicleMileageLog.vehicle_id == v.equipment_id,
                VehicleMileageLog.date >= start_date, VehicleMileageLog.date <= end_date,
            ).all()
            miles = sum(m.miles_driven for m in ml)

            fl = db.query(VehicleFuelLog).filter(
                VehicleFuelLog.vehicle_id == v.equipment_id,
                VehicleFuelLog.date >= start_date, VehicleFuelLog.date <= end_date,
            ).all()
            gallons = sum(float(f.gallons or 0) for f in fl)
            fuel_cost = sum(f.total_cost for f in fl)
            mpg = round(safe_divide(miles, gallons), 1) if gallons > 0 else 0

            total_miles += miles
            total_fuel_cost += fuel_cost
            total_gallons += gallons

            vehicle_rows.append({
                'name': v.display_name, 'plate': v.license_plate or '--',
                'miles': round(miles, 1), 'gallons': round(gallons, 1),
                'fuel_cost': round(fuel_cost, 2), 'mpg': mpg,
                'cost_per_mile': round(safe_divide(fuel_cost, miles), 2) if miles else 0,
            })
        vehicle_rows.sort(key=lambda x: x['miles'], reverse=True)
        avg_mpg = round(safe_divide(total_miles, total_gallons), 1) if total_gallons else 0

        # Monthly
        months_data = get_12_month_labels()
        month_labels = [m.strftime('%b %Y') for m in months_data]
        monthly_miles = []
        monthly_fuel = []
        for m in months_data:
            m_start = m.replace(day=1)
            m_end = (m_start + relativedelta(months=1)) - timedelta(days=1)
            mm = sum(ml.miles_driven for ml in db.query(VehicleMileageLog).filter(
                VehicleMileageLog.date >= m_start, VehicleMileageLog.date <= m_end).all())
            mf = sum(fl.total_cost for fl in db.query(VehicleFuelLog).filter(
                VehicleFuelLog.date >= m_start, VehicleFuelLog.date <= m_end).all())
            monthly_miles.append(round(mm, 1))
            monthly_fuel.append(round(mf, 2))

        divisions = _get_divisions(db)
        summary_json = {'Miles': round(total_miles, 1), 'Fuel Cost': f'${total_fuel_cost:,.2f}', 'Avg MPG': avg_mpg}

        return render_template('reports/fleet_report.html',
            active_page='reports', user=current_user, divisions=divisions,
            report_title='Fleet Report', report_category='Operations',
            date_label=date_label, selected_preset=selected_preset,
            start_date=start_date, end_date=end_date,
            empty=not vehicle_rows or total_miles == 0,
            vehicle_rows=vehicle_rows,
            total_miles=round(total_miles, 1), total_fuel_cost=round(total_fuel_cost, 2),
            avg_mpg=avg_mpg,
            cost_per_mile=round(safe_divide(total_fuel_cost, total_miles), 2) if total_miles else 0,
            month_labels=month_labels, monthly_miles=monthly_miles, monthly_fuel=monthly_fuel,
            summary_json=summary_json,
        )
    finally:
        db.close()


# ── Communication Activity Report ─────────────────────────────────────────────

@reports_bp.route('/reports/communication-activity')
@login_required
def communication_activity():
    db = get_session()
    try:
        start_date, end_date, date_label = parse_date_range(request.args)
        selected_preset = request.args.get('preset', 'this_month')

        from models.communication import CommunicationLog
        comms = db.query(CommunicationLog).filter(
            CommunicationLog.communication_date >= datetime.combine(start_date, datetime.min.time()),
            CommunicationLog.communication_date <= datetime.combine(end_date, datetime.max.time()),
        ).all()

        total = len(comms)
        inbound = sum(1 for c in comms if c.direction == 'inbound')
        outbound = total - inbound
        followups_required = sum(1 for c in comms if c.follow_up_required)
        followups_completed = sum(1 for c in comms if c.follow_up_required and c.follow_up_completed)
        followup_pct = round(safe_divide(followups_completed, followups_required) * 100, 1) if followups_required else 100

        # By type
        type_agg = {}
        for c in comms:
            t = c.communication_type or 'other'
            if t not in type_agg:
                type_agg[t] = {'type': t, 'total': 0, 'inbound': 0, 'outbound': 0}
            type_agg[t]['total'] += 1
            if c.direction == 'inbound':
                type_agg[t]['inbound'] += 1
            else:
                type_agg[t]['outbound'] += 1
        type_rows = sorted(type_agg.values(), key=lambda x: x['total'], reverse=True)

        # By client
        client_agg = {}
        for c in comms:
            cn = c.client.display_name if c.client else 'Unknown'
            if cn not in client_agg:
                client_agg[cn] = {'client': cn, 'total': 0, 'inbound': 0, 'outbound': 0, 'last_contact': None}
            client_agg[cn]['total'] += 1
            if c.direction == 'inbound':
                client_agg[cn]['inbound'] += 1
            else:
                client_agg[cn]['outbound'] += 1
            cd = c.communication_date.date() if c.communication_date and hasattr(c.communication_date, 'date') else (c.communication_date if c.communication_date else None)
            if cd and (not client_agg[cn]['last_contact'] or cd > client_agg[cn]['last_contact']):
                client_agg[cn]['last_contact'] = cd
        client_comm_rows = sorted(client_agg.values(), key=lambda x: x['total'], reverse=True)

        # Monthly
        months_data = get_12_month_labels()
        month_labels = [m.strftime('%b %Y') for m in months_data]
        monthly_inbound, monthly_outbound = [], []
        for m in months_data:
            m_start = m.replace(day=1)
            m_end = (m_start + relativedelta(months=1)) - timedelta(days=1)
            m_comms = db.query(CommunicationLog).filter(
                CommunicationLog.communication_date >= datetime.combine(m_start, datetime.min.time()),
                CommunicationLog.communication_date <= datetime.combine(m_end, datetime.max.time()),
            ).all()
            monthly_inbound.append(sum(1 for c in m_comms if c.direction == 'inbound'))
            monthly_outbound.append(len(m_comms) - sum(1 for c in m_comms if c.direction == 'inbound'))

        divisions = _get_divisions(db)
        summary_json = {'Total': total, 'Inbound': inbound, 'Outbound': outbound, 'Follow-up Rate': f'{followup_pct}%'}

        return render_template('reports/communication_activity.html',
            active_page='reports', user=current_user, divisions=divisions,
            report_title='Communication Activity', report_category='Operations',
            date_label=date_label, selected_preset=selected_preset,
            start_date=start_date, end_date=end_date, empty=total == 0,
            total=total, inbound=inbound, outbound=outbound,
            followup_pct=followup_pct,
            type_rows=type_rows, client_comm_rows=client_comm_rows,
            month_labels=month_labels, monthly_inbound=monthly_inbound,
            monthly_outbound=monthly_outbound,
            today=date.today(), summary_json=summary_json,
        )
    finally:
        db.close()


# ── Scheduled Reports ─────────────────────────────────────────────────────────

@reports_bp.route('/reports/scheduled')
@login_required
@role_required('admin', 'owner')
def scheduled_reports():
    """Placeholder for scheduled reports page."""
    db = get_session()
    try:
        divisions = _get_divisions(db)
        return render_template('reports/scheduled_reports.html',
            active_page='reports', user=current_user, divisions=divisions,
            report_title='Scheduled Reports', scheduled=[],
        )
    finally:
        db.close()


# ── AI Insights endpoint ──────────────────────────────────────────────────────

@reports_bp.route('/reports/ai-insights', methods=['POST'])
@login_required
@role_required('admin', 'owner')
def ai_insights():
    data = request.get_json()
    summary_data = data.get('summary_data', {})
    report_title = data.get('report_title', 'Report')
    summary_lines = [f"  {k}: {v}" for k, v in summary_data.items()]

    prompt = f"""Analyze this field service business data and provide 4-5 specific actionable insights.

Report: {report_title}
Metrics:
{chr(10).join(summary_lines)}

Focus on trends, issues needing attention, positives, and recommended actions. Be concise."""

    try:
        from src.ai_core.claude_client import ClaudeClient
        client = ClaudeClient()
        response = client.send_message(prompt)
        return jsonify({'insights': response})
    except Exception as e:
        return jsonify({'insights': f'AI insights unavailable: {e}. Check AI configuration.'})
