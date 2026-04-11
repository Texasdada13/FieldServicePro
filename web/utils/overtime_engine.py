"""Overtime calculation engine. Applies daily/weekly overtime rules to time entries."""
from datetime import date, timedelta
from sqlalchemy import func
from models.database import get_session
from models.time_entry import TimeEntry


def get_overtime_settings(db=None):
    """Load overtime settings. Returns dict with defaults."""
    defaults = {
        'overtime_threshold_daily': 8.0,
        'overtime_threshold_weekly': 40.0,
        'overtime_rate_multiplier': 1.5,
        'double_time_threshold_daily': 12.0,
        'double_time_rate_multiplier': 2.0,
        'auto_overtime_calculation': True,
    }
    try:
        from models.settings import OrganizationSettings
        own_session = db is None
        if own_session:
            db = get_session()
        settings = db.query(OrganizationSettings).first()
        if settings:
            for key in defaults:
                val = getattr(settings, key, None)
                if val is not None:
                    defaults[key] = bool(val) if key == 'auto_overtime_calculation' else float(val)
        if own_session:
            db.close()
    except Exception:
        pass
    return defaults


def calculate_overtime_for_tech_day(technician_id, target_date):
    """
    Analyze a tech's entries for a day and flag overtime/double-time.
    Modifies entry_type and recalculates rates. Returns summary dict.
    """
    db = get_session()
    try:
        settings = get_overtime_settings(db)
        if not settings['auto_overtime_calculation']:
            return {'flagged': False, 'message': 'Auto overtime disabled'}

        entries = db.query(TimeEntry).filter(
            TimeEntry.technician_id == technician_id,
            TimeEntry.date == target_date,
            TimeEntry.status != 'rejected',
            TimeEntry.entry_type.in_(['regular', 'overtime', 'double_time']),
        ).order_by(TimeEntry.start_time.asc().nullslast(), TimeEntry.created_at.asc()).all()

        if not entries:
            return {'flagged': False, 'total_hours': 0}

        daily_threshold = settings['overtime_threshold_daily']
        dt_threshold = settings['double_time_threshold_daily']
        ot_mult = settings['overtime_rate_multiplier']
        dt_mult = settings['double_time_rate_multiplier']

        cumulative = 0.0
        flagged_count = 0

        for entry in entries:
            hours = float(entry.duration_hours or 0)
            # Get base rate from technician
            tech = entry.technician
            base_rate = float(tech.hourly_rate or 55) if tech else 55.0

            if cumulative + hours > dt_threshold:
                if cumulative >= dt_threshold:
                    entry.entry_type = 'double_time'
                    entry.hourly_rate = round(base_rate * dt_mult, 2)
                else:
                    entry.entry_type = 'double_time'
                    entry.hourly_rate = round(base_rate * dt_mult, 2)
                flagged_count += 1
            elif cumulative + hours > daily_threshold:
                if cumulative >= daily_threshold:
                    entry.entry_type = 'overtime'
                    entry.hourly_rate = round(base_rate * ot_mult, 2)
                    flagged_count += 1
                else:
                    ot_portion = (cumulative + hours) - daily_threshold
                    if ot_portion > hours / 2:
                        entry.entry_type = 'overtime'
                        entry.hourly_rate = round(base_rate * ot_mult, 2)
                        flagged_count += 1
                    else:
                        entry.entry_type = 'regular'
                        entry.hourly_rate = base_rate
            else:
                entry.entry_type = 'regular'
                entry.hourly_rate = base_rate

            entry.compute_costs()
            cumulative += hours

        db.commit()
        return {
            'flagged': flagged_count > 0,
            'total_hours': round(cumulative, 2),
            'overtime_entries': flagged_count,
            'daily_threshold': daily_threshold,
        }
    finally:
        db.close()


def calculate_weekly_overtime(technician_id, week_start):
    """Check weekly overtime threshold. week_start should be a Monday."""
    db = get_session()
    try:
        settings = get_overtime_settings(db)
        week_end = week_start + timedelta(days=6)
        weekly_threshold = settings['overtime_threshold_weekly']

        total_hours = float(db.query(
            func.coalesce(func.sum(TimeEntry.duration_hours), 0)
        ).filter(
            TimeEntry.technician_id == technician_id,
            TimeEntry.date >= week_start,
            TimeEntry.date <= week_end,
            TimeEntry.status != 'rejected',
        ).scalar() or 0)

        return {
            'total_weekly_hours': total_hours,
            'weekly_threshold': weekly_threshold,
            'over_weekly': total_hours > weekly_threshold,
            'overtime_amount': max(0, total_hours - weekly_threshold),
        }
    finally:
        db.close()


def get_overtime_alerts():
    """Get technicians currently over daily or weekly thresholds."""
    db = get_session()
    try:
        settings = get_overtime_settings(db)
        today = date.today()
        monday = today - timedelta(days=today.weekday())

        from models.technician import Technician
        techs = db.query(Technician).filter_by(is_active=True).all()
        alerts = []

        for tech in techs:
            daily = float(db.query(
                func.coalesce(func.sum(TimeEntry.duration_hours), 0)
            ).filter(
                TimeEntry.technician_id == tech.id,
                TimeEntry.date == today,
                TimeEntry.status != 'rejected',
            ).scalar() or 0)

            weekly = float(db.query(
                func.coalesce(func.sum(TimeEntry.duration_hours), 0)
            ).filter(
                TimeEntry.technician_id == tech.id,
                TimeEntry.date >= monday,
                TimeEntry.date <= monday + timedelta(days=6),
                TimeEntry.status != 'rejected',
            ).scalar() or 0)

            name = tech.full_name

            if daily > settings['overtime_threshold_daily']:
                alerts.append({
                    'type': 'daily_overtime',
                    'technician_id': tech.id,
                    'technician_name': name,
                    'hours': daily,
                    'threshold': settings['overtime_threshold_daily'],
                    'date': today,
                })

            if weekly > settings['overtime_threshold_weekly']:
                alerts.append({
                    'type': 'weekly_overtime',
                    'technician_id': tech.id,
                    'technician_name': name,
                    'hours': weekly,
                    'threshold': settings['overtime_threshold_weekly'],
                    'week_start': monday,
                })

        return alerts
    finally:
        db.close()
