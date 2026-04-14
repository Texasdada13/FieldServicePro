"""Warranty and callback quality reports."""
import csv, io
from datetime import date, timedelta
from flask import Blueprint, render_template, request, Response
from flask_login import login_required, current_user
from sqlalchemy import func, and_

from models.database import get_session
from models.callback import Callback, CALLBACK_REASONS
from models.warranty import Warranty, WarrantyClaim
from models.job import Job
from models.technician import Technician
from models.time_entry import TimeEntry
from models.division import Division
from web.auth import role_required

warranty_reports_bp = Blueprint('warranty_reports', __name__, url_prefix='/reports')


def _get_divisions():
    db = get_session()
    try:
        return db.query(Division).filter_by(
            organization_id=current_user.organization_id, is_active=True
        ).order_by(Division.sort_order).all()
    finally:
        db.close()


@warranty_reports_bp.route('/callbacks')
@login_required
@role_required('owner', 'admin', 'dispatcher')
def callbacks_report():
    db = get_session()
    try:
        # Tech callback rates
        techs = db.query(Technician).filter_by(is_active=True).all()
        tech_stats = []
        for tech in techs:
            total_callbacks = db.query(func.count(Callback.id)).filter(
                Callback.responsible_technician_id == tech.id
            ).scalar() or 0
            total_jobs = db.query(func.count(func.distinct(TimeEntry.job_id))).filter(
                TimeEntry.technician_id == tech.id
            ).scalar() or 0
            if total_jobs > 0:
                rate = round((total_callbacks / total_jobs) * 100, 1)
                tech_stats.append({
                    'tech': tech, 'total_jobs': total_jobs,
                    'total_callbacks': total_callbacks, 'callback_rate': rate,
                    'above_threshold': rate > 5.0,
                })
        tech_stats.sort(key=lambda x: x['callback_rate'], reverse=True)

        # Reason breakdown
        reason_stats = []
        total_cbs = db.query(func.count(Callback.id)).scalar() or 0
        for val, label in CALLBACK_REASONS:
            count = db.query(func.count(Callback.id)).filter(Callback.reason == val).scalar() or 0
            reason_stats.append({
                'reason': label, 'count': count,
                'pct': round((count / total_cbs * 100) if total_cbs else 0, 1),
            })
        reason_stats.sort(key=lambda x: x['count'], reverse=True)

        # Monthly trend (last 12 months)
        today = date.today()
        monthly_trend = []
        for i in range(11, -1, -1):
            ms = (today.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
            me = (ms.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1) if i > 0 else today
            cb_count = db.query(func.count(Callback.id)).filter(
                Callback.reported_date >= ms, Callback.reported_date <= me
            ).scalar() or 0
            job_count = db.query(func.count(Job.id)).filter(
                Job.status == 'completed', Job.completed_at >= ms, Job.completed_at <= me
            ).scalar() or 1
            monthly_trend.append({
                'month': ms.strftime('%b %Y'), 'callbacks': cb_count,
                'jobs': job_count, 'rate': round((cb_count / job_count) * 100, 1),
            })

        # CSV export
        if request.args.get('export') == 'csv':
            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Technician', 'Total Jobs', 'Callbacks', 'Rate %', 'Above Threshold'])
            for r in tech_stats:
                writer.writerow([r['tech'].full_name, r['total_jobs'], r['total_callbacks'], r['callback_rate'], 'Yes' if r['above_threshold'] else 'No'])
            return Response(output.getvalue(), mimetype='text/csv',
                headers={'Content-Disposition': 'attachment;filename=callback_report.csv'})

        return render_template('reports/callbacks_report.html',
            active_page='reports', user=current_user, divisions=_get_divisions(),
            tech_stats=tech_stats, reason_stats=reason_stats,
            total_callbacks=total_cbs, monthly_trend=monthly_trend,
        )
    finally:
        db.close()


@warranty_reports_bp.route('/warranties')
@login_required
@role_required('owner', 'admin', 'dispatcher')
def warranties_report():
    db = get_session()
    try:
        today = date.today()

        # Claims by month (last 6)
        claims_by_month = []
        for i in range(5, -1, -1):
            ms = (today.replace(day=1) - timedelta(days=30 * i)).replace(day=1)
            me = (ms.replace(day=28) + timedelta(days=4)).replace(day=1) - timedelta(days=1) if i > 0 else today
            count = db.query(func.count(WarrantyClaim.id)).filter(
                WarrantyClaim.claimed_date >= ms, WarrantyClaim.claimed_date <= me
            ).scalar() or 0
            cost = db.query(func.sum(WarrantyClaim.labor_cost + WarrantyClaim.parts_cost)).filter(
                WarrantyClaim.claimed_date >= ms, WarrantyClaim.claimed_date <= me
            ).scalar() or 0
            claims_by_month.append({'month': ms.strftime('%b %Y'), 'count': count, 'cost': round(float(cost), 2)})

        # Expiring warranties
        expiring_30 = db.query(Warranty).filter(
            Warranty.status == 'expiring_soon'
        ).order_by(Warranty.end_date).all()
        expiring_90 = db.query(Warranty).filter(
            Warranty.status.in_(['active', 'expiring_soon']),
            Warranty.end_date <= today + timedelta(days=90)
        ).order_by(Warranty.end_date).all()

        return render_template('reports/warranties_report.html',
            active_page='reports', user=current_user, divisions=_get_divisions(),
            claims_by_month=claims_by_month,
            expiring_30=expiring_30, expiring_90=expiring_90, today=today,
        )
    finally:
        db.close()
