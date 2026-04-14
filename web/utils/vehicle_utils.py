"""Helpers for vehicle management: odometer updates, MPG calculation,
expense auto-creation, navigation URLs, and route building."""
from datetime import date
from urllib.parse import quote_plus

from models.database import get_session
from models.equipment import Equipment
from models.vehicle_profile import VehicleProfile
from models.vehicle_fuel_log import VehicleFuelLog
from models.vehicle_mileage_log import VehicleMileageLog


# ── Navigation URL helpers ────────────────────────────────────────────────────

def google_maps_url(address):
    """Return a Google Maps directions URL for an address."""
    if not address or not address.strip():
        return '#'
    return f'https://www.google.com/maps/dir/?api=1&destination={quote_plus(address.strip())}'


def google_maps_multi_stop_url(addresses):
    """Build a Google Maps URL with multiple waypoints."""
    if not addresses:
        return '#'
    stops = [a.strip() for a in addresses if a and a.strip()]
    if len(stops) == 1:
        return google_maps_url(stops[0])

    origin = quote_plus(stops[0])
    destination = quote_plus(stops[-1])
    base = f'https://www.google.com/maps/dir/?api=1&origin={origin}&destination={destination}'
    if len(stops) > 2:
        waypoints = '|'.join(quote_plus(s) for s in stops[1:-1])
        base += f'&waypoints={waypoints}'
    return base


# ── Vehicle query helpers ─────────────────────────────────────────────────────

def get_all_vehicles(db, organization_id, division_id=None):
    """Return Equipment records with type='vehicle', optionally filtered."""
    q = db.query(Equipment).filter_by(
        organization_id=organization_id, equipment_type='vehicle'
    )
    if division_id:
        q = q.filter_by(division_id=division_id)
    return q.order_by(Equipment.name).all()


def get_vehicle_stats(db, organization_id):
    """Return aggregate stats for the vehicle dashboard."""
    vehicles = get_all_vehicles(db, organization_id)
    stats = {
        'total': len(vehicles),
        'available': 0,
        'assigned': 0,
        'in_maintenance': 0,
        'expiring_soon': 0,
    }
    for v in vehicles:
        status = (v.status or 'available').lower()
        if status in ('available', 'active'):
            stats['available'] += 1
        elif status == 'assigned':
            stats['assigned'] += 1
        elif status in ('maintenance', 'in_maintenance'):
            stats['in_maintenance'] += 1

        if v.vehicle_profile:
            reg = v.vehicle_profile.registration_status
            ins = v.vehicle_profile.insurance_status
            if reg in ('expiring_soon', 'expired') or ins in ('expiring_soon', 'expired'):
                stats['expiring_soon'] += 1
    return stats


# ── Odometer / MPG ────────────────────────────────────────────────────────────

def update_vehicle_odometer(db, vehicle_id, new_reading):
    """Update VehicleProfile.current_odometer if the new reading is higher."""
    profile = db.query(VehicleProfile).filter_by(equipment_id=vehicle_id).first()
    if profile and new_reading > (profile.current_odometer or 0):
        profile.current_odometer = new_reading


def calculate_mpg(db, vehicle_id, current_fuel_log):
    """Calculate MPG based on the last full-tank fill-up before this one."""
    if not current_fuel_log.is_full_tank:
        return None

    prev = db.query(VehicleFuelLog).filter(
        VehicleFuelLog.vehicle_id == vehicle_id,
        VehicleFuelLog.is_full_tank == True,
        VehicleFuelLog.odometer_reading < current_fuel_log.odometer_reading,
    ).order_by(VehicleFuelLog.odometer_reading.desc()).first()

    if not prev:
        return None

    miles = current_fuel_log.odometer_reading - prev.odometer_reading
    gallons = float(current_fuel_log.gallons or 0)

    if miles <= 0 or gallons <= 0:
        return None

    return round(miles / gallons, 2)


# ── Expense auto-creation ─────────────────────────────────────────────────────

def create_fuel_expense(db, fuel_log, created_by_user_id):
    """Auto-create an Expense record from a fuel log. Returns the Expense (not committed)."""
    from models.expense import Expense
    total = float(fuel_log.gallons or 0) * float(fuel_log.price_per_gallon or 0)
    if total <= 0:
        return None

    vehicle = db.query(Equipment).filter_by(id=fuel_log.vehicle_id).first()
    vname = vehicle.name if vehicle else 'Vehicle'

    # Generate expense number
    from sqlalchemy import func
    max_id = db.query(func.max(Expense.id)).scalar() or 0
    expense_number = f'EXP-{max_id + 1:05d}'

    expense = Expense(
        expense_number=expense_number,
        title=f'Fuel - {vname} ({fuel_log.date})',
        description=f'Fuel at {fuel_log.station or "Unknown Station"} - {fuel_log.gallons:.1f} gal @ ${fuel_log.price_per_gallon:.3f}/gal',
        expense_category='fuel_mileage',
        amount=round(total, 2), tax_amount=0, total_amount=round(total, 2),
        payment_method=fuel_log.payment_method or 'company_card',
        is_reimbursable=(fuel_log.payment_method in ('personal_card', 'cash')),
        expense_date=fuel_log.date,
        status='draft',
        created_by=created_by_user_id,
    )
    db.add(expense)
    db.flush()
    fuel_log.expense_id = expense.id
    return expense


def create_mileage_expense(db, mileage_log, rate_per_mile, created_by_user_id):
    """Create a reimbursable mileage expense. Returns the Expense (not committed)."""
    from models.expense import Expense
    miles = mileage_log.miles_driven
    if miles <= 0 or rate_per_mile <= 0:
        return None

    amount = round(miles * rate_per_mile, 2)
    vehicle = db.query(Equipment).filter_by(id=mileage_log.vehicle_id).first()
    vname = vehicle.name if vehicle else 'Vehicle'

    from sqlalchemy import func
    max_id = db.query(func.max(Expense.id)).scalar() or 0
    expense_number = f'EXP-{max_id + 1:05d}'

    expense = Expense(
        expense_number=expense_number,
        title=f'Mileage - {vname} ({mileage_log.date})',
        description=f'{miles} mi @ ${rate_per_mile:.3f}/mi',
        expense_category='fuel_mileage',
        amount=amount, tax_amount=0, total_amount=amount,
        payment_method='personal_card_reimbursement',
        job_id=mileage_log.job_id,
        is_reimbursable=True,
        expense_date=mileage_log.date,
        status='draft',
        created_by=created_by_user_id,
    )
    db.add(expense)
    db.flush()
    mileage_log.expense_id = expense.id
    return expense


# ── Daily route builder ───────────────────────────────────────────────────────

def build_daily_route(db, technician_id, route_date):
    """Return structured dict with jobs sorted by schedule, addresses, and Maps URL."""
    from models.job import Job

    jobs = db.query(Job).filter(
        Job.assigned_technician_id == technician_id,
        Job.scheduled_date != None,
    ).all()

    # Filter to matching date (scheduled_date is DateTime, compare date portion)
    day_jobs = [j for j in jobs
                if j.scheduled_date and j.scheduled_date.date() == route_date]
    day_jobs.sort(key=lambda j: j.scheduled_date)

    stops = []
    for job in day_jobs:
        address = _job_address(job)
        stops.append({
            'job': job,
            'address': address,
            'navigate_url': google_maps_url(address) if address else '#',
        })

    addresses = [s['address'] for s in stops if s['address']]
    multi_url = google_maps_multi_stop_url(addresses) if len(addresses) > 1 else (
        google_maps_url(addresses[0]) if addresses else '#'
    )

    return {
        'stops': stops,
        'multi_stop_url': multi_url,
        'total_stops': len(stops),
    }


def _job_address(job):
    """Extract address from job's property or client."""
    if hasattr(job, 'property') and job.property:
        prop = job.property
        parts = [getattr(prop, 'address', None), getattr(prop, 'city', None),
                 getattr(prop, 'province', None), getattr(prop, 'postal_code', None)]
        filtered = [p for p in parts if p]
        if filtered:
            return ', '.join(filtered)
    if hasattr(job, 'client') and job.client:
        c = job.client
        parts = [getattr(c, 'address', None), getattr(c, 'city', None),
                 getattr(c, 'province', None), getattr(c, 'postal_code', None)]
        filtered = [p for p in parts if p]
        if filtered:
            return ', '.join(filtered)
    return None


# ── Monthly aggregates (for charts) ──────────────────────────────────────────

def vehicle_monthly_mileage(db, vehicle_id, year):
    """Return monthly mileage totals for chart rendering."""
    from sqlalchemy import func
    logs = db.query(VehicleMileageLog).filter(
        VehicleMileageLog.vehicle_id == vehicle_id,
    ).all()

    month_totals = {m: 0.0 for m in range(1, 13)}
    for log in logs:
        if log.date and log.date.year == year:
            month_totals[log.date.month] += log.miles_driven

    return [{'month': m, 'miles': month_totals[m]} for m in range(1, 13)]


def vehicle_monthly_fuel_cost(db, vehicle_id, year):
    """Return monthly fuel cost totals for chart rendering."""
    logs = db.query(VehicleFuelLog).filter(
        VehicleFuelLog.vehicle_id == vehicle_id,
    ).all()

    month_totals = {m: 0.0 for m in range(1, 13)}
    for log in logs:
        if log.date and log.date.year == year:
            month_totals[log.date.month] += log.total_cost

    return [{'month': m, 'cost': month_totals[m]} for m in range(1, 13)]
