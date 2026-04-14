"""
Recurring Job Generation Engine
================================
Generates Jobs from RecurringSchedule rows and ContractLineItem rows.

Public API:
    run_generation_pass(db, user_id, method)  -> GenerationResult
    generate_for_schedule(db, schedule, user_id, method) -> Job | None
    generate_from_contract_line_items(db, user_id, method) -> list[Job]
    get_due_schedules(db, org_id)             -> list[RecurringSchedule]
    get_dashboard_summary(db, org_id)         -> dict
"""
import json
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional

from models.job import Job, JobStatus
from models.recurring_schedule import RecurringSchedule, RecurringJobLog

log = logging.getLogger(__name__)


@dataclass
class GenerationResult:
    jobs_created: list = field(default_factory=list)
    schedules_processed: int = 0
    schedules_skipped: int = 0
    errors: list = field(default_factory=list)
    contract_items_processed: int = 0

    @property
    def total_created(self):
        return len(self.jobs_created)

    def to_dict(self):
        return {
            'jobs_created': self.total_created,
            'schedules_processed': self.schedules_processed,
            'schedules_skipped': self.schedules_skipped,
            'contract_items_processed': self.contract_items_processed,
            'errors': self.errors,
        }


def _build_job_number(db):
    """Generate next job number: JOB-YYYY-XXXX."""
    year = date.today().year
    prefix = f"JOB-{year}-"
    last = db.query(Job).filter(
        Job.job_number.like(f"{prefix}%")
    ).order_by(Job.id.desc()).first()
    if last and last.job_number:
        try:
            seq = int(last.job_number.split('-')[-1]) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


def generate_schedule_number(db):
    """Generate next schedule number: REC-YYYY-XXXX."""
    year = date.today().year
    prefix = f"REC-{year}-"
    last = db.query(RecurringSchedule).filter(
        RecurringSchedule.schedule_number.like(f"{prefix}%")
    ).order_by(RecurringSchedule.id.desc()).first()
    if last and last.schedule_number:
        try:
            seq = int(last.schedule_number.split('-')[-1]) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


def get_due_schedules(db, org_id=None):
    """Return active schedules due for generation. Auto-resumes paused ones."""
    today = date.today()

    # Auto-resume paused schedules whose pause_until has passed
    paused = db.query(RecurringSchedule).filter(
        RecurringSchedule.status == 'paused',
        RecurringSchedule.pause_until != None,
        RecurringSchedule.pause_until <= today,
    )
    if org_id:
        paused = paused.filter(RecurringSchedule.organization_id == org_id)
    for s in paused.all():
        s.status = 'active'
        s.pause_until = None
        s.pause_reason = None
        log.info("Auto-resumed schedule %s", s.schedule_number)
    db.flush()

    # Fetch active auto-generate candidates
    query = db.query(RecurringSchedule).filter(
        RecurringSchedule.status == 'active',
        RecurringSchedule.is_active == True,
        RecurringSchedule.auto_generate == True,
    )
    if org_id:
        query = query.filter(RecurringSchedule.organization_id == org_id)

    due = []
    for s in query.all():
        if s.end_date and today > s.end_date:
            s.status = 'completed'
            continue
        delta = (s.next_due_date - today).days
        if delta <= s.advance_generation_days:
            due.append(s)
    db.flush()
    return due


def generate_for_schedule(db, schedule, user_id=None, method='auto', force=False, dry_run=False):
    """
    Create a Job from a RecurringSchedule.
    Returns (Job, None) on success or (None, reason) on skip when called with force/dry_run.
    For backwards compat, returns Job or None when called without those params.
    """
    today = date.today()

    # Guard: don't double-generate
    if schedule.last_generated_date and schedule.last_generated_date >= schedule.next_due_date:
        if not force:
            if dry_run:
                return None, f'Already generated for due date {schedule.next_due_date}'
            return None

    if not schedule.auto_generate and not force:
        if dry_run:
            return None, 'auto_generate is off (alert-only mode)'
        return None

    if dry_run:
        return None, 'DRY RUN — would generate job'

    title = f"{schedule.title} — {schedule.next_due_date.strftime('%B %Y')}"

    desc_parts = []
    if schedule.default_description:
        desc_parts.append(schedule.default_description)
    desc_parts.append(f"Auto-generated from schedule {schedule.schedule_number}.")
    desc_parts.append(f"Scheduled due date: {schedule.next_due_date.isoformat()}")
    if schedule.requires_parts:
        try:
            parts = json.loads(schedule.requires_parts)
            if parts:
                desc_parts.append(f"Expected parts: {', '.join(str(p) for p in parts)}")
        except (json.JSONDecodeError, TypeError):
            desc_parts.append(f"Expected parts: {schedule.requires_parts}")

    scheduled_date = schedule.next_due_date if schedule.auto_schedule else None
    tech_id = schedule.default_technician_id if schedule.auto_assign else None
    status = JobStatus.SCHEDULED.value if scheduled_date else JobStatus.DRAFT.value

    job = Job(
        organization_id=schedule.organization_id,
        job_number=_build_job_number(db),
        title=title,
        description='\n\n'.join(desc_parts),
        client_id=schedule.client_id,
        property_id=schedule.property_id,
        project_id=schedule.project_id,
        division_id=schedule.division_id,
        job_type=schedule.job_type,
        status=status,
        priority=schedule.default_priority or 'normal',
        scheduled_date=scheduled_date,
        estimated_amount=float(schedule.estimated_amount) if schedule.estimated_amount else None,
        assigned_technician_id=tech_id,
        contract_id=schedule.contract_id,
        created_by_id=user_id,
        source='recurring',
    )
    db.add(job)
    db.flush()

    # Advance schedule
    next_date = schedule.calculate_next_due_date(from_date=schedule.next_due_date)
    schedule.last_generated_date = today
    schedule.last_generated_job_id = job.id
    schedule.next_due_date = next_date
    schedule.total_jobs_generated = (schedule.total_jobs_generated or 0) + 1
    if schedule.estimated_amount:
        schedule.total_value_generated = float(schedule.total_value_generated or 0) + float(schedule.estimated_amount)

    if schedule.end_date and next_date > schedule.end_date:
        schedule.status = 'completed'

    # Audit log
    db.add(RecurringJobLog(
        schedule_id=schedule.id,
        job_id=job.id,
        due_date=today,
        generation_method=method,
        generated_by=user_id,
        success=True,
        notes=f'Job {job.job_number} created',
    ))

    log.info("Generated job %s from schedule %s (next: %s)", job.job_number, schedule.schedule_number, next_date)
    return job


def generate_from_contract_line_items(db, org_id=None, user_id=None, method='auto'):
    """Scan ContractLineItems with auto_generate_jobs=True and generate jobs."""
    from models.contract import ContractLineItem, Contract

    today = date.today()
    created_jobs = []

    try:
        query = db.query(ContractLineItem).join(
            Contract, ContractLineItem.contract_id == Contract.id
        ).filter(
            ContractLineItem.auto_generate_jobs == True,
            ContractLineItem.next_scheduled_date != None,
            Contract.status == 'active',
        )
        if org_id:
            query = query.filter(Contract.organization_id == org_id)
        line_items = query.all()
    except Exception as e:
        log.warning("Could not query contract line items: %s", e)
        return []

    for item in line_items:
        try:
            advance = getattr(item, 'advance_generation_days', 14) or 14
            delta = (item.next_scheduled_date - today).days
            if delta > advance:
                continue

            if item.last_generated_date and item.last_generated_date >= item.next_scheduled_date:
                continue

            contract = item.contract
            title = f"{item.description or item.service_type or 'Service'} — {item.next_scheduled_date.strftime('%B %Y')}"

            job = Job(
                organization_id=contract.organization_id,
                job_number=_build_job_number(db),
                title=title,
                description=(
                    f"Auto-generated from Contract {contract.contract_number}, "
                    f"Line Item: {item.description or item.service_type}.\n"
                    f"Due: {item.next_scheduled_date.isoformat()}"
                ),
                client_id=contract.client_id,
                contract_id=contract.id,
                division_id=contract.division_id if hasattr(contract, 'division_id') else None,
                job_type='maintenance',
                status=JobStatus.DRAFT.value,
                priority='normal',
                scheduled_date=item.next_scheduled_date,
                estimated_amount=float(item.unit_price or 0) or None,
                created_by_id=user_id,
                source='contract_line_item',
            )
            db.add(job)
            db.flush()

            item.last_generated_date = today
            item.last_generated_job_id = job.id

            # Advance next_scheduled_date using the item's own method
            next_date = item.calculate_next_scheduled_date(from_date=item.next_scheduled_date)
            if next_date:
                item.next_scheduled_date = next_date

            created_jobs.append(job)
        except Exception as e:
            log.error("Error processing contract line item %d: %s", item.id, e)

    return created_jobs


def run_generation_pass(db, org_id=None, user_id=None, method='auto'):
    """Full generation pass. Commits on success, rolls back on failure."""
    result = GenerationResult()

    try:
        # 1. RecurringSchedules
        due_schedules = get_due_schedules(db, org_id)
        for schedule in due_schedules:
            try:
                job = generate_for_schedule(db, schedule, user_id=user_id, method=method)
                result.schedules_processed += 1
                if job:
                    result.jobs_created.append(job)
                else:
                    result.schedules_skipped += 1
            except Exception as e:
                result.schedules_skipped += 1
                result.errors.append({'schedule': schedule.schedule_number, 'error': str(e)})

        # 2. Contract line items
        try:
            contract_jobs = generate_from_contract_line_items(db, org_id, user_id, method)
            result.jobs_created.extend(contract_jobs)
            result.contract_items_processed = len(contract_jobs)
        except Exception as e:
            result.errors.append({'source': 'contract_line_items', 'error': str(e)})

        db.commit()
        log.info("Generation pass: %d jobs, %d errors", result.total_created, len(result.errors))
    except Exception as e:
        db.rollback()
        result.errors.append({'source': 'engine', 'error': str(e)})
        log.exception("Fatal error in generation pass: %s", e)

    return result


def get_dashboard_summary(db, org_id):
    """Lightweight summary for sidebar badge / dashboard."""
    today = date.today()

    total_active = db.query(RecurringSchedule).filter(
        RecurringSchedule.organization_id == org_id,
        RecurringSchedule.status == 'active',
        RecurringSchedule.is_active == True,
    ).count()

    overdue = db.query(RecurringSchedule).filter(
        RecurringSchedule.organization_id == org_id,
        RecurringSchedule.status == 'active',
        RecurringSchedule.is_active == True,
        RecurringSchedule.next_due_date < today,
    ).count()

    due_soon_rows = db.query(RecurringSchedule).filter(
        RecurringSchedule.organization_id == org_id,
        RecurringSchedule.status == 'active',
        RecurringSchedule.is_active == True,
        RecurringSchedule.auto_generate == True,
    ).all()

    due_soon = sum(1 for s in due_soon_rows if 0 <= (s.next_due_date - today).days <= s.advance_generation_days)

    return {
        'total_active': total_active,
        'overdue': overdue,
        'due_soon': due_soon,
        'alert_count': overdue + due_soon,
    }


def sync_from_contract_line_items(db, contract_id, created_by_user_id):
    """
    Scan a contract's line items and create RecurringSchedule records
    for any that have a frequency set but no schedule yet.
    Returns {'created': [...], 'skipped': [...]}
    """
    from models.contract import Contract, ContractLineItem

    contract = db.query(Contract).filter_by(id=contract_id).first()
    if not contract:
        return {'created': [], 'skipped': [], 'error': 'Contract not found'}

    FREQ_MAP = {
        'weekly': 'weekly', 'biweekly': 'biweekly', 'bi_weekly': 'biweekly',
        'monthly': 'monthly', 'quarterly': 'quarterly',
        'semi_annual': 'semi_annual', 'annual': 'annual',
        'annually': 'annual', 'yearly': 'annual', 'one_time': None,
    }

    created = []
    skipped = []

    for li in contract.line_items:
        # Get frequency string from the enum
        freq_val = li.frequency.value if hasattr(li.frequency, 'value') else str(li.frequency)
        freq_key = freq_val.lower().replace('-', '_').replace(' ', '_')
        frequency = FREQ_MAP.get(freq_key)

        if not frequency:
            skipped.append({'line_item_id': li.id, 'reason': f"Frequency '{freq_val}' not mappable or one-time"})
            continue

        # Check for existing schedule
        existing = db.query(RecurringSchedule).filter_by(contract_line_item_id=li.id).first()
        if existing:
            skipped.append({'line_item_id': li.id, 'reason': f'Already has schedule {existing.schedule_number}'})
            continue

        next_due = li.next_scheduled_date or date.today()
        start_dt = contract.start_date or date.today()

        sched = RecurringSchedule(
            organization_id=contract.organization_id,
            schedule_number=generate_schedule_number(db),
            title=li.description or f'{contract.contract_number} — {li.service_type}',
            description=f'Auto-created from contract {contract.contract_number}, line item: {li.service_type}',
            client_id=contract.client_id,
            contract_id=contract.id,
            contract_line_item_id=li.id,
            division_id=contract.division_id if hasattr(contract, 'division_id') else None,
            job_type='maintenance',
            default_description=li.description or li.service_type,
            default_priority='normal',
            estimated_amount=float(li.unit_price or 0) * float(li.quantity or 1),
            frequency=frequency,
            start_date=start_dt,
            end_date=contract.end_date,
            next_due_date=next_due,
            is_active=True,
            auto_generate=True,
            auto_assign=False,
            auto_schedule=False,
            advance_generation_days=14,
            status='active',
            total_jobs_generated=0,
            total_value_generated=0,
            created_by=created_by_user_id,
        )
        db.add(sched)
        db.flush()

        created.append({
            'line_item_id': li.id,
            'schedule_number': sched.schedule_number,
            'title': sched.title,
            'frequency': frequency,
            'next_due_date': str(next_due),
        })

    db.commit()
    return {'created': created, 'skipped': skipped}


def preview_upcoming_dates(schedule, count=6):
    """Generate the next N due dates without modifying the schedule."""
    dates = []
    current = schedule.next_due_date
    for _ in range(count):
        dates.append(current)
        current = schedule.calculate_next_due_date(from_date=current)
    return dates
