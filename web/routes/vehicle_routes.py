"""Vehicle management routes — dashboard, detail, mileage/fuel log CRUD."""
from datetime import date, datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user

from models.database import get_session
from models.equipment import Equipment
from models.vehicle_profile import VehicleProfile, FUEL_TYPES
from models.vehicle_mileage_log import VehicleMileageLog, MILEAGE_PURPOSES
from models.vehicle_fuel_log import VehicleFuelLog, FUEL_PAYMENT_METHODS
from models.technician import Technician
from models.division import Division
from web.auth import role_required

vehicle_bp = Blueprint('vehicles', __name__)


def _get_divisions():
    db = get_session()
    try:
        return db.query(Division).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Division.sort_order).all()
    finally:
        db.close()


def _parse_date(val):
    if not val:
        return None
    for fmt in ('%Y-%m-%d', '%m/%d/%Y'):
        try:
            return datetime.strptime(val, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


# ── Dashboard ─────────────────────────────────────────────────────────────────

@vehicle_bp.route('/vehicles')
@login_required
def vehicle_dashboard():
    db = get_session()
    try:
        org_id = current_user.organization_id
        search = request.args.get('search', '').strip()
        status_filter = request.args.get('status', '')
        tech_filter = request.args.get('technician_id', '', type=int) or None

        vehicles = db.query(Equipment).filter_by(
            organization_id=org_id, equipment_type='vehicle'
        ).order_by(Equipment.name).all()

        technicians = db.query(Technician).filter_by(
            organization_id=org_id, is_active=True
        ).order_by(Technician.first_name).all()

        # Stats
        stats = {'total': len(vehicles), 'available': 0, 'assigned': 0,
                 'in_maintenance': 0, 'expiring_soon': 0}
        for v in vehicles:
            s = (v.status or 'available').lower()
            if s in ('available', 'active'):
                stats['available'] += 1
            elif s == 'assigned':
                stats['assigned'] += 1
            elif s in ('maintenance', 'in_maintenance'):
                stats['in_maintenance'] += 1
            if v.vehicle_profile:
                if v.vehicle_profile.registration_status in ('expiring_soon', 'expired') or \
                   v.vehicle_profile.insurance_status in ('expiring_soon', 'expired'):
                    stats['expiring_soon'] += 1

        # Filters
        if search:
            sl = search.lower()
            vehicles = [v for v in vehicles
                        if sl in (v.name or '').lower()
                        or (v.vehicle_profile and sl in (v.vehicle_profile.license_plate or '').lower())
                        or (v.vehicle_profile and sl in (v.vehicle_profile.vin or '').lower())]
        if status_filter:
            vehicles = [v for v in vehicles if (v.status or '') == status_filter]
        if tech_filter:
            vehicles = [v for v in vehicles
                        if v.vehicle_profile and v.vehicle_profile.assigned_technician_id == tech_filter]

        return render_template('vehicles/dashboard.html',
            active_page='vehicles', user=current_user, divisions=_get_divisions(),
            vehicles=vehicles, stats=stats, technicians=technicians,
            search=search, status_filter=status_filter, tech_filter=tech_filter,
            fuel_types=FUEL_TYPES,
        )
    finally:
        db.close()


# ── New Vehicle ───────────────────────────────────────────────────────────────

@vehicle_bp.route('/vehicles/new', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'owner', 'dispatcher')
def vehicle_new():
    db = get_session()
    try:
        org_id = current_user.organization_id
        technicians = db.query(Technician).filter_by(
            organization_id=org_id, is_active=True
        ).order_by(Technician.first_name).all()
        all_divisions = db.query(Division).filter_by(
            organization_id=org_id, is_active=True
        ).order_by(Division.sort_order).all()

        if request.method == 'POST':
            f = request.form
            equip = Equipment(
                organization_id=org_id,
                name=f['name'].strip(),
                equipment_type='vehicle',
                status=f.get('status', 'available'),
                make=f.get('make', '').strip() or None,
                model=f.get('model_name', '').strip() or None,
                year=int(f['year']) if f.get('year') else None,
                identifier=f.get('vin', '').strip() or None,
                division_id=int(f['division_id']) if f.get('division_id') else None,
                notes=f.get('notes', '').strip() or None,
            )
            db.add(equip)
            db.flush()

            profile = VehicleProfile(
                equipment_id=equip.id,
                license_plate=f.get('license_plate', '').strip() or None,
                vin=f.get('vin', '').strip() or None,
                make=f.get('make', '').strip() or None,
                model=f.get('model_name', '').strip() or None,
                year=int(f['year']) if f.get('year') else None,
                color=f.get('color', '').strip() or None,
                fuel_type=f.get('fuel_type', 'gasoline'),
                fuel_tank_capacity=float(f['fuel_tank_capacity']) if f.get('fuel_tank_capacity') else None,
                current_odometer=int(f['current_odometer']) if f.get('current_odometer') else 0,
                registration_expiry=_parse_date(f.get('registration_expiry')),
                insurance_policy_number=f.get('insurance_policy_number', '').strip() or None,
                insurance_expiry=_parse_date(f.get('insurance_expiry')),
                assigned_technician_id=int(f['assigned_technician_id']) if f.get('assigned_technician_id') else None,
                home_base_address=f.get('home_base_address', '').strip() or None,
                ez_pass_number=f.get('ez_pass_number', '').strip() or None,
                notes=f.get('vehicle_notes', '').strip() or None,
            )
            db.add(profile)
            db.commit()
            flash(f'Vehicle "{equip.name}" created.', 'success')
            return redirect(url_for('vehicles.vehicle_detail', vehicle_id=equip.id))

        return render_template('vehicles/vehicle_form.html',
            active_page='vehicles', user=current_user, divisions=_get_divisions(),
            vehicle=None, profile=None, technicians=technicians,
            all_divisions=all_divisions, fuel_types=FUEL_TYPES, mode='new',
        )
    finally:
        db.close()


# ── Vehicle Detail ────────────────────────────────────────────────────────────

@vehicle_bp.route('/vehicles/<int:vehicle_id>')
@login_required
def vehicle_detail(vehicle_id):
    db = get_session()
    try:
        vehicle = db.query(Equipment).filter_by(
            id=vehicle_id, organization_id=current_user.organization_id
        ).first()
        if not vehicle:
            flash('Vehicle not found.', 'error')
            return redirect(url_for('vehicles.vehicle_dashboard'))

        profile = vehicle.vehicle_profile
        technicians = db.query(Technician).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Technician.first_name).all()

        year = request.args.get('year', date.today().year, type=int)
        tab = request.args.get('tab', 'profile')

        mileage_logs = db.query(VehicleMileageLog).filter_by(
            vehicle_id=vehicle_id
        ).order_by(VehicleMileageLog.date.desc()).limit(50).all()

        fuel_logs = db.query(VehicleFuelLog).filter_by(
            vehicle_id=vehicle_id
        ).order_by(VehicleFuelLog.date.desc()).limit(50).all()

        # Year totals
        total_miles_year = sum(ml.miles_driven for ml in
            db.query(VehicleMileageLog).filter(
                VehicleMileageLog.vehicle_id == vehicle_id,
            ).all() if ml.date and ml.date.year == year)

        total_fuel_cost_year = sum(fl.total_cost for fl in
            db.query(VehicleFuelLog).filter(
                VehicleFuelLog.vehicle_id == vehicle_id,
            ).all() if fl.date and fl.date.year == year)

        from models.job import Job
        recent_jobs = db.query(Job).filter(
            Job.organization_id == current_user.organization_id,
        ).order_by(Job.scheduled_date.desc()).limit(10).all()

        return render_template('vehicles/vehicle_detail.html',
            active_page='vehicles', user=current_user, divisions=_get_divisions(),
            vehicle=vehicle, profile=profile, technicians=technicians,
            mileage_logs=mileage_logs, fuel_logs=fuel_logs,
            total_miles_year=total_miles_year, total_fuel_cost_year=total_fuel_cost_year,
            year=year, tab=tab, today=date.today(),
            fuel_types=FUEL_TYPES, mileage_purposes=MILEAGE_PURPOSES,
            fuel_payment_methods=FUEL_PAYMENT_METHODS,
        )
    finally:
        db.close()


# ── Edit Vehicle ──────────────────────────────────────────────────────────────

@vehicle_bp.route('/vehicles/<int:vehicle_id>/edit', methods=['GET', 'POST'])
@login_required
@role_required('admin', 'owner', 'dispatcher')
def vehicle_edit(vehicle_id):
    db = get_session()
    try:
        vehicle = db.query(Equipment).filter_by(
            id=vehicle_id, organization_id=current_user.organization_id
        ).first()
        if not vehicle:
            flash('Vehicle not found.', 'error')
            return redirect(url_for('vehicles.vehicle_dashboard'))

        profile = vehicle.vehicle_profile
        if not profile:
            profile = VehicleProfile(equipment_id=vehicle.id)
            db.add(profile)
            db.flush()

        technicians = db.query(Technician).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Technician.first_name).all()
        all_divisions = db.query(Division).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Division.sort_order).all()

        if request.method == 'POST':
            f = request.form
            vehicle.name = f.get('name', vehicle.name).strip()
            vehicle.status = f.get('status', vehicle.status)
            vehicle.division_id = int(f['division_id']) if f.get('division_id') else vehicle.division_id
            vehicle.notes = f.get('notes', '').strip() or None

            profile.license_plate = f.get('license_plate', '').strip() or None
            profile.vin = f.get('vin', '').strip() or None
            profile.make = f.get('make', '').strip() or None
            profile.model = f.get('model_name', '').strip() or None
            profile.year = int(f['year']) if f.get('year') else None
            profile.color = f.get('color', '').strip() or None
            profile.fuel_type = f.get('fuel_type', 'gasoline')
            profile.fuel_tank_capacity = float(f['fuel_tank_capacity']) if f.get('fuel_tank_capacity') else None
            profile.registration_expiry = _parse_date(f.get('registration_expiry'))
            profile.insurance_policy_number = f.get('insurance_policy_number', '').strip() or None
            profile.insurance_expiry = _parse_date(f.get('insurance_expiry'))
            profile.assigned_technician_id = int(f['assigned_technician_id']) if f.get('assigned_technician_id') else None
            profile.home_base_address = f.get('home_base_address', '').strip() or None
            profile.ez_pass_number = f.get('ez_pass_number', '').strip() or None
            profile.gps_tracker_id = f.get('gps_tracker_id', '').strip() or None
            profile.notes = f.get('vehicle_notes', '').strip() or None

            db.commit()
            flash('Vehicle updated.', 'success')
            return redirect(url_for('vehicles.vehicle_detail', vehicle_id=vehicle_id))

        return render_template('vehicles/vehicle_form.html',
            active_page='vehicles', user=current_user, divisions=_get_divisions(),
            vehicle=vehicle, profile=profile, technicians=technicians,
            all_divisions=all_divisions, fuel_types=FUEL_TYPES, mode='edit',
        )
    finally:
        db.close()


# ── Log Mileage ───────────────────────────────────────────────────────────────

@vehicle_bp.route('/vehicles/<int:vehicle_id>/mileage', methods=['POST'])
@login_required
def log_mileage(vehicle_id):
    db = get_session()
    try:
        f = request.form
        start_odo = int(f.get('start_odometer', 0))
        end_odo = int(f.get('end_odometer', 0))
        tech_id = int(f['technician_id']) if f.get('technician_id') else None

        if not start_odo or not end_odo or end_odo < start_odo or not tech_id:
            flash('Valid odometer readings and driver required.', 'error')
            return redirect(url_for('vehicles.vehicle_detail', vehicle_id=vehicle_id, tab='mileage'))

        log = VehicleMileageLog(
            vehicle_id=vehicle_id,
            date=_parse_date(f.get('date')) or date.today(),
            start_odometer=start_odo, end_odometer=end_odo,
            purpose=f.get('purpose', 'job_travel'),
            job_id=int(f['job_id']) if f.get('job_id') else None,
            technician_id=tech_id,
            start_location=f.get('start_location', '').strip() or None,
            end_location=f.get('end_location', '').strip() or None,
            notes=f.get('notes', '').strip() or None,
            created_by=current_user.id,
        )
        db.add(log)

        # Update odometer on profile
        from web.utils.vehicle_utils import update_vehicle_odometer
        update_vehicle_odometer(db, vehicle_id, end_odo)

        # Optionally create mileage expense
        if f.get('create_expense') == '1':
            from web.utils.vehicle_utils import create_mileage_expense
            db.flush()
            create_mileage_expense(db, log, 0.67, current_user.id)

        db.commit()
        flash(f'Mileage logged: {log.miles_driven} miles.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {e}', 'error')
    finally:
        db.close()
    return redirect(url_for('vehicles.vehicle_detail', vehicle_id=vehicle_id, tab='mileage'))


# ── Log Fuel ──────────────────────────────────────────────────────────────────

@vehicle_bp.route('/vehicles/<int:vehicle_id>/fuel', methods=['POST'])
@login_required
def log_fuel(vehicle_id):
    db = get_session()
    try:
        f = request.form
        tech_id = int(f['technician_id']) if f.get('technician_id') else None
        odometer = int(f['odometer_reading']) if f.get('odometer_reading') else None
        gallons = float(f['gallons']) if f.get('gallons') else None
        ppg = float(f['price_per_gallon']) if f.get('price_per_gallon') else None

        if not all([tech_id, odometer, gallons, ppg]):
            flash('All fuel log fields required.', 'error')
            return redirect(url_for('vehicles.vehicle_detail', vehicle_id=vehicle_id, tab='fuel'))

        vehicle = db.query(Equipment).filter_by(id=vehicle_id).first()
        fuel = VehicleFuelLog(
            vehicle_id=vehicle_id,
            date=_parse_date(f.get('date')) or date.today(),
            odometer_reading=odometer, gallons=gallons, price_per_gallon=ppg,
            fuel_type=f.get('fuel_type') or (vehicle.vehicle_profile.fuel_type if vehicle and vehicle.vehicle_profile else 'gasoline'),
            station=f.get('station', '').strip() or None,
            is_full_tank=f.get('is_full_tank') == '1',
            payment_method=f.get('payment_method', 'company_card'),
            technician_id=tech_id,
            notes=f.get('notes', '').strip() or None,
            created_by=current_user.id,
        )
        db.add(fuel)
        db.flush()

        # Calculate MPG
        from web.utils.vehicle_utils import calculate_mpg, update_vehicle_odometer, create_fuel_expense
        mpg = calculate_mpg(db, vehicle_id, fuel)
        if mpg:
            fuel.mpg_calculated = mpg
            if vehicle and vehicle.vehicle_profile:
                existing = float(vehicle.vehicle_profile.average_mpg or 0)
                vehicle.vehicle_profile.average_mpg = mpg if not existing else round((existing + mpg) / 2, 2)

        update_vehicle_odometer(db, vehicle_id, odometer)

        # Auto-create expense
        create_fuel_expense(db, fuel, current_user.id)

        db.commit()
        msg = f'Fuel logged: {gallons:.2f} gal, ${fuel.total_cost:.2f}'
        if mpg:
            msg += f', {mpg:.1f} MPG'
        flash(msg, 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {e}', 'error')
    finally:
        db.close()
    return redirect(url_for('vehicles.vehicle_detail', vehicle_id=vehicle_id, tab='fuel'))


# ── Delete Mileage/Fuel Entries ───────────────────────────────────────────────

@vehicle_bp.route('/vehicles/mileage/<int:log_id>/delete', methods=['POST'])
@login_required
@role_required('admin', 'owner')
def delete_mileage(log_id):
    db = get_session()
    try:
        log = db.query(VehicleMileageLog).filter_by(id=log_id).first()
        if log:
            vid = log.vehicle_id
            db.delete(log)
            db.commit()
            flash('Mileage entry deleted.', 'info')
            return redirect(url_for('vehicles.vehicle_detail', vehicle_id=vid, tab='mileage'))
    finally:
        db.close()
    return redirect(url_for('vehicles.vehicle_dashboard'))


@vehicle_bp.route('/vehicles/fuel/<int:log_id>/delete', methods=['POST'])
@login_required
@role_required('admin', 'owner')
def delete_fuel(log_id):
    db = get_session()
    try:
        log = db.query(VehicleFuelLog).filter_by(id=log_id).first()
        if log:
            vid = log.vehicle_id
            db.delete(log)
            db.commit()
            flash('Fuel entry deleted.', 'info')
            return redirect(url_for('vehicles.vehicle_detail', vehicle_id=vid, tab='fuel'))
    finally:
        db.close()
    return redirect(url_for('vehicles.vehicle_dashboard'))


# ── Daily Route View ──────────────────────────────────────────────────────────

@vehicle_bp.route('/vehicles/route')
@login_required
def daily_route():
    db = get_session()
    try:
        technicians = db.query(Technician).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Technician.first_name).all()

        tech_id = request.args.get('technician_id', type=int)
        route_date_str = request.args.get('date', '')
        try:
            route_date = datetime.strptime(route_date_str, '%Y-%m-%d').date() if route_date_str else date.today()
        except ValueError:
            route_date = date.today()

        route_data = None
        selected_tech = None
        if tech_id:
            selected_tech = db.query(Technician).filter_by(id=tech_id).first()
            from web.utils.vehicle_utils import build_daily_route
            route_data = build_daily_route(db, tech_id, route_date)

        return render_template('vehicles/daily_route.html',
            active_page='vehicles', user=current_user, divisions=_get_divisions(),
            technicians=technicians, selected_tech=selected_tech,
            route_date=route_date, route_data=route_data, today=date.today(),
        )
    finally:
        db.close()


# ── API: Job address lookup ───────────────────────────────────────────────────

@vehicle_bp.route('/vehicles/api/job-address/<int:job_id>')
@login_required
def api_job_address(job_id):
    db = get_session()
    try:
        from models.job import Job
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            return jsonify({'address': '', 'job_number': ''})
        from web.utils.vehicle_utils import _job_address
        address = _job_address(job)
        return jsonify({'address': address or '', 'job_number': job.job_number or ''})
    finally:
        db.close()
