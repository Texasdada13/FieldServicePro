"""Utility functions for warranty management."""
from datetime import date, timedelta
from sqlalchemy import func
from models.warranty import Warranty, WarrantyClaim


def generate_warranty_number(db):
    year = date.today().year
    prefix = f"WTY-{year}-"
    last = db.query(Warranty).filter(Warranty.warranty_number.like(f"{prefix}%")).order_by(Warranty.id.desc()).first()
    seq = int(last.warranty_number.split('-')[-1]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


def generate_claim_number(db):
    year = date.today().year
    prefix = f"WCL-{year}-"
    last = db.query(WarrantyClaim).filter(WarrantyClaim.claim_number.like(f"{prefix}%")).order_by(WarrantyClaim.id.desc()).first()
    seq = int(last.claim_number.split('-')[-1]) + 1 if last else 1
    return f"{prefix}{seq:04d}"


def refresh_all_warranty_statuses(db):
    updated = 0
    warranties = db.query(Warranty).filter(Warranty.status != 'voided').all()
    for w in warranties:
        old = w.status
        w.refresh_status()
        if w.status != old:
            updated += 1
    if updated:
        db.commit()
    return updated


def get_warranty_stats(db):
    today = date.today()
    month_start = today.replace(day=1)
    return {
        'total_active': db.query(func.count(Warranty.id)).filter(Warranty.status.in_(['active', 'expiring_soon'])).scalar() or 0,
        'expiring_soon': db.query(func.count(Warranty.id)).filter(Warranty.status == 'expiring_soon').scalar() or 0,
        'expired_this_month': db.query(func.count(Warranty.id)).filter(Warranty.status == 'expired', Warranty.end_date >= month_start, Warranty.end_date <= today).scalar() or 0,
        'claims_this_month': db.query(func.count(WarrantyClaim.id)).filter(WarrantyClaim.claimed_date >= month_start).scalar() or 0,
    }


def get_active_warranties_for_client(db, client_id):
    return db.query(Warranty).filter(
        Warranty.client_id == client_id,
        Warranty.status.in_(['active', 'expiring_soon'])
    ).order_by(Warranty.end_date.asc()).all()
