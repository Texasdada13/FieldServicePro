"""Job cost breakdown — labor, materials, equipment, expenses with variance tracking."""
from models.job_material import JobMaterial
from models.time_entry import TimeEntry
from models.expense import Expense


def get_job_cost_breakdown(db, job):
    """Build full job cost breakdown including expenses."""
    # ── Material Costs ────────────────────────────────────────────────────
    materials = db.query(JobMaterial).filter_by(job_id=job.id).all()
    actual_material_cost = sum(
        float(m.total_cost or 0) for m in materials if float(m.quantity or 0) > 0
    )
    actual_material_sell = sum(
        float(m.total_sell or 0) for m in materials
        if m.is_billable and float(m.quantity or 0) > 0
    )

    # ── Labor Costs ───────────────────────────────────────────────────────
    time_entries = db.query(TimeEntry).filter(
        TimeEntry.job_id == job.id,
        TimeEntry.status.in_(['approved', 'exported', 'submitted']),
    ).all()
    actual_labor_cost = sum(float(e.labor_cost or 0) for e in time_entries)
    actual_labor_hours = sum(float(e.duration_hours or 0) for e in time_entries)

    # ── Equipment placeholder ─────────────────────────────────────────────
    actual_equipment_cost = 0.0

    # ── Expenses ──────────────────────────────────────────────────────────
    expense_rows = db.query(Expense).filter(
        Expense.job_id == job.id,
        Expense.status.in_(['approved', 'submitted']),
    ).all()
    actual_expense_cost = sum(float(e.total_amount or 0) for e in expense_rows)
    subcontractor_cost = sum(
        float(e.total_amount or 0) for e in expense_rows
        if e.expense_category == 'subcontractor'
    )
    expense_by_category = {}
    for e in expense_rows:
        expense_by_category[e.expense_category] = expense_by_category.get(e.expense_category, 0) + float(e.total_amount or 0)

    # ── Totals ────────────────────────────────────────────────────────────
    actual_total = actual_labor_cost + actual_material_cost + actual_equipment_cost + actual_expense_cost
    est_total = 0.0

    # ── Revenue ───────────────────────────────────────────────────────────
    quoted_amount = float(job.estimated_amount or 0)
    invoiced_amount = sum(float(inv.total_amount or 0) for inv in (job.invoices or []))

    profit_base = invoiced_amount if invoiced_amount > 0 else quoted_amount
    profit_margin = profit_base - actual_total
    profit_pct = round((profit_margin / profit_base * 100) if profit_base > 0 else 0, 1)

    # Health indicator
    if profit_pct >= 20:
        health = {'color': 'success', 'label': 'Healthy'}
    elif profit_pct >= 10:
        health = {'color': 'warning', 'label': 'Thin Margin'}
    elif profit_pct >= 0:
        health = {'color': 'warning', 'label': 'Break-Even'}
    else:
        health = {'color': 'danger', 'label': 'Unprofitable'}

    return {
        'labor': {
            'estimated': 0, 'actual': round(actual_labor_cost, 2),
            'hours': round(actual_labor_hours, 1),
            'variance': round(-actual_labor_cost, 2),
        },
        'materials': {
            'estimated': 0, 'actual': round(actual_material_cost, 2),
            'sell': round(actual_material_sell, 2),
            'variance': round(-actual_material_cost, 2),
        },
        'equipment': {
            'estimated': 0, 'actual': round(actual_equipment_cost, 2),
            'variance': round(-actual_equipment_cost, 2),
        },
        'expenses': {
            'actual': round(actual_expense_cost, 2),
            'subcontractor': round(subcontractor_cost, 2),
            'by_category': expense_by_category,
            'rows': expense_rows,
        },
        'totals': {
            'estimated': round(est_total, 2),
            'actual': round(actual_total, 2),
            'variance': round(est_total - actual_total, 2),
        },
        'revenue': {
            'quoted': round(quoted_amount, 2),
            'invoiced': round(invoiced_amount, 2),
            'profit_margin': round(profit_margin, 2),
            'profit_pct': profit_pct,
        },
        'health': health,
    }
