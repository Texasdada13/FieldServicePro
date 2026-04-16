"""Mobile Technician View — all routes.

Consolidated route file for the mobile blueprint. Each task adds routes here.
Uses raw SQLAlchemy (get_session / try-finally-db.close) pattern.
"""
from datetime import date, datetime, timedelta
from functools import wraps
import os
import uuid

from flask import (
    render_template, redirect, url_for, flash, request,
    jsonify, g, current_app,
)
from flask_login import login_required, current_user

from web.routes.mobile import mobile_bp
from web.routes.mobile.helpers import mobile_login_required, get_current_technician
from models.database import get_session
from models.job import Job
from models.client import Client
from models.time_entry import TimeEntry
from models.part import Part
from models.job_material import JobMaterial
from models.document import Document
from models.notification import Notification
from models.expense import Expense
from models.technician import Technician


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_tech_jobs_today(db, tech):
    """Return today's jobs for a technician."""
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    today_end = datetime.combine(today, datetime.max.time())
    return db.query(Job).filter(
        Job.assigned_technician_id == tech.id,
        Job.scheduled_date >= today_start,
        Job.scheduled_date <= today_end,
        Job.status.notin_(['cancelled']),
    ).order_by(Job.scheduled_date.asc(), Job.id.asc()).all()


# ── Today / Dashboard ────────────────────────────────────────────────────────

@mobile_bp.route('/')
@mobile_bp.route('/today')
@mobile_login_required
def dashboard():
    """Technician's daily dashboard."""
    db = get_session()
    try:
        tech = g.technician
        today_date = date.today()
        now = datetime.now()

        hour = now.hour
        greeting = 'Good morning' if hour < 12 else ('Good afternoon' if hour < 17 else 'Good evening')

        todays_jobs = get_tech_jobs_today(db, tech)

        # Active time entry
        active_entry = db.query(TimeEntry).filter(
            TimeEntry.technician_id == tech.id,
            TimeEntry.end_time.is_(None),
        ).first()

        active_job = None
        if active_entry and active_entry.job_id:
            active_job = db.query(Job).filter_by(id=active_entry.job_id).first()

        # Today's hours
        today_entries = db.query(TimeEntry).filter(
            TimeEntry.technician_id == tech.id,
            TimeEntry.date == today_date,
            TimeEntry.end_time.isnot(None),
        ).all()
        total_hours = sum(float(e.duration_hours or 0) for e in today_entries)
        if active_entry and active_entry.start_time:
            start_dt = datetime.combine(active_entry.date or today_date, active_entry.start_time)
            total_hours += max((now - start_dt).total_seconds() / 3600, 0)

        # Week stats
        week_start = today_date - timedelta(days=today_date.weekday())
        ws = datetime.combine(week_start, datetime.min.time())
        we = datetime.combine(week_start + timedelta(days=6), datetime.max.time())
        week_jobs = db.query(Job).filter(
            Job.assigned_technician_id == tech.id,
            Job.scheduled_date >= ws, Job.scheduled_date <= we,
        ).count()

        completed_today = sum(1 for j in todays_jobs if j.status == 'completed')

        # Preload clients
        client_ids = [j.client_id for j in todays_jobs if j.client_id]
        clients = {}
        if client_ids:
            for c in db.query(Client).filter(Client.id.in_(client_ids)).all():
                clients[c.id] = c

        # Unread notifications
        unread = db.query(Notification).filter_by(
            recipient_id=current_user.id, is_read=False,
        ).order_by(Notification.created_at.desc()).limit(5).all()

        return render_template('mobile/today.html',
            active_nav='today',
            greeting=greeting, tech=tech,
            today_date=today_date,
            todays_jobs=todays_jobs, clients=clients,
            active_entry=active_entry, active_job=active_job,
            total_hours=round(total_hours, 1),
            jobs_count=len(todays_jobs),
            completed_count=completed_today,
            week_jobs=week_jobs,
            notifications=unread,
        )
    finally:
        db.close()


# ── Job List ─────────────────────────────────────────────────────────────────

@mobile_bp.route('/jobs')
@mobile_login_required
def job_list():
    """All jobs for this technician."""
    db = get_session()
    try:
        tech = g.technician
        tab = request.args.get('tab', 'today')
        today = date.today()
        today_start = datetime.combine(today, datetime.min.time())
        today_end = datetime.combine(today, datetime.max.time())

        q = db.query(Job).filter(Job.assigned_technician_id == tech.id)

        if tab == 'today':
            q = q.filter(Job.scheduled_date >= today_start, Job.scheduled_date <= today_end)
        elif tab == 'upcoming':
            q = q.filter(Job.scheduled_date > today_end, Job.status.notin_(['completed', 'cancelled']))
        elif tab == 'completed':
            q = q.filter(Job.status == 'completed')
        elif tab == 'all':
            q = q.filter(Job.status.notin_(['cancelled']))

        if tab == 'completed':
            jobs = q.order_by(Job.completed_at.desc().nullslast(), Job.id.desc()).limit(50).all()
        else:
            jobs = q.order_by(Job.scheduled_date.asc(), Job.id.asc()).all()

        client_ids = list(set(j.client_id for j in jobs if j.client_id))
        clients = {}
        if client_ids:
            for c in db.query(Client).filter(Client.id.in_(client_ids)).all():
                clients[c.id] = c

        return render_template('mobile/jobs.html',
            active_nav='jobs', tab=tab,
            jobs=jobs, clients=clients,
        )
    finally:
        db.close()


# ── Job Detail ───────────────────────────────────────────────────────────────

@mobile_bp.route('/jobs/<int:job_id>')
@mobile_login_required
def job_detail(job_id):
    """Full job detail — tech's primary work screen."""
    db = get_session()
    try:
        tech = g.technician
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            flash('Job not found.', 'error')
            return redirect(url_for('mobile.job_list'))

        client = db.query(Client).filter_by(id=job.client_id).first() if job.client_id else None

        active_entry = db.query(TimeEntry).filter(
            TimeEntry.technician_id == tech.id,
            TimeEntry.job_id == job.id,
            TimeEntry.end_time.is_(None),
        ).first()

        any_active = db.query(TimeEntry).filter(
            TimeEntry.technician_id == tech.id,
            TimeEntry.end_time.is_(None),
        ).first()

        time_entries = db.query(TimeEntry).filter(
            TimeEntry.job_id == job.id, TimeEntry.technician_id == tech.id,
        ).order_by(TimeEntry.date.desc(), TimeEntry.id.desc()).all()
        total_hours = sum(float(e.duration_hours or 0) for e in time_entries)

        materials = db.query(JobMaterial).filter_by(job_id=job.id).order_by(JobMaterial.id.desc()).all()

        photos = db.query(Document).filter_by(
            entity_type='job', entity_id=job.id,
        ).order_by(Document.created_at.desc()).all()

        notes = []
        try:
            from models.communication import CommunicationLog
            notes = db.query(CommunicationLog).filter_by(
                job_id=job.id,
            ).order_by(CommunicationLog.communication_date.desc()).limit(10).all()
        except Exception:
            pass

        phases = []
        try:
            from models.job_phase import JobPhase
            phases = db.query(JobPhase).filter_by(job_id=job.id).order_by(JobPhase.phase_number.asc()).all()
        except Exception:
            pass

        return render_template('mobile/job_detail.html',
            active_nav='jobs', job=job, client=client,
            active_entry=active_entry, any_active=any_active,
            time_entries=time_entries, total_hours=round(total_hours, 1),
            materials=materials, photos=photos, notes=notes, phases=phases,
        )
    finally:
        db.close()


# ── Clock In/Out ─────────────────────────────────────────────────────────────

@mobile_bp.route('/clock')
@mobile_login_required
def timeclock():
    """Time clock page."""
    db = get_session()
    try:
        tech = g.technician
        today_date = date.today()
        now = datetime.now()

        active_entry = db.query(TimeEntry).filter(
            TimeEntry.technician_id == tech.id,
            TimeEntry.end_time.is_(None),
        ).first()

        active_job = None
        if active_entry and active_entry.job_id:
            active_job = db.query(Job).filter_by(id=active_entry.job_id).first()

        todays_jobs = get_tech_jobs_today(db, tech)

        today_entries = db.query(TimeEntry).filter(
            TimeEntry.technician_id == tech.id,
            TimeEntry.date == today_date,
            TimeEntry.end_time.isnot(None),
        ).order_by(TimeEntry.id.desc()).all()

        total_hours = sum(float(e.duration_hours or 0) for e in today_entries)
        if active_entry and active_entry.start_time:
            start_dt = datetime.combine(active_entry.date or today_date, active_entry.start_time)
            total_hours += max((now - start_dt).total_seconds() / 3600, 0)

        return render_template('mobile/clock.html',
            active_nav='clock',
            active_entry=active_entry, active_job=active_job,
            todays_jobs=todays_jobs, today_entries=today_entries,
            total_hours=round(total_hours, 1),
        )
    finally:
        db.close()


@mobile_bp.route('/clock/in', methods=['POST'])
@mobile_login_required
def clock_in():
    """Clock in."""
    db = get_session()
    try:
        tech = g.technician
        now = datetime.now()
        job_id = request.form.get('job_id', type=int)

        active = db.query(TimeEntry).filter(
            TimeEntry.technician_id == tech.id, TimeEntry.end_time.is_(None),
        ).first()
        if active:
            flash('Already clocked in. Clock out first.', 'warning')
            return redirect(url_for('mobile.timeclock'))

        entry = TimeEntry(
            technician_id=tech.id, job_id=job_id or None,
            start_time=now.time(), date=date.today(),
            entry_type='regular', status='draft', source='clock_in_out',
            created_by=current_user.id,
        )
        db.add(entry)

        if job_id:
            job = db.query(Job).filter_by(id=job_id).first()
            if job and job.status in ('draft', 'scheduled', 'pending'):
                job.status = 'in_progress'
                if not job.started_at:
                    job.started_at = now

        db.commit()
        flash('Clocked in!', 'success')
    finally:
        db.close()
    return redirect(url_for('mobile.timeclock'))


@mobile_bp.route('/clock/out', methods=['POST'])
@mobile_login_required
def clock_out():
    """Clock out."""
    db = get_session()
    try:
        tech = g.technician
        now = datetime.now()

        active = db.query(TimeEntry).filter(
            TimeEntry.technician_id == tech.id, TimeEntry.end_time.is_(None),
        ).first()
        if not active:
            flash('Not currently clocked in.', 'warning')
            return redirect(url_for('mobile.timeclock'))

        active.end_time = now.time()
        if active.start_time:
            start_dt = datetime.combine(active.date or date.today(), active.start_time)
            end_dt = datetime.combine(date.today(), now.time())
            active.duration_hours = round((end_dt - start_dt).total_seconds() / 3600, 2)

        desc = request.form.get('description', '').strip()
        if desc:
            active.description = desc

        db.commit()
        flash(f'Clocked out. Logged {active.duration_hours or 0:.1f} hours.', 'success')
    finally:
        db.close()
    return redirect(url_for('mobile.timeclock'))


@mobile_bp.route('/clock/switch', methods=['POST'])
@mobile_login_required
def clock_switch():
    """Switch to a different job."""
    db = get_session()
    try:
        tech = g.technician
        now = datetime.now()
        new_job_id = request.form.get('job_id', type=int)
        if not new_job_id:
            flash('Select a job to switch to.', 'warning')
            return redirect(url_for('mobile.timeclock'))

        active = db.query(TimeEntry).filter(
            TimeEntry.technician_id == tech.id, TimeEntry.end_time.is_(None),
        ).first()
        if active:
            active.end_time = now.time()
            if active.start_time:
                start_dt = datetime.combine(active.date or date.today(), active.start_time)
                active.duration_hours = round((datetime.combine(date.today(), now.time()) - start_dt).total_seconds() / 3600, 2)

        entry = TimeEntry(
            technician_id=tech.id, job_id=new_job_id,
            start_time=now.time(), date=date.today(),
            entry_type='regular', status='draft', source='clock_in_out',
            created_by=current_user.id,
        )
        db.add(entry)

        job = db.query(Job).filter_by(id=new_job_id).first()
        if job and job.status in ('draft', 'scheduled', 'pending'):
            job.status = 'in_progress'
            if not job.started_at:
                job.started_at = now

        db.commit()
        flash('Switched jobs!', 'success')
    finally:
        db.close()
    return redirect(url_for('mobile.timeclock'))


# ── Job Actions ──────────────────────────────────────────────────────────────

@mobile_bp.route('/jobs/<int:job_id>/clock-in', methods=['POST'])
@mobile_login_required
def job_clock_in(job_id):
    """Clock in to a specific job."""
    db = get_session()
    try:
        tech = g.technician
        now = datetime.now()

        active = db.query(TimeEntry).filter(
            TimeEntry.technician_id == tech.id, TimeEntry.end_time.is_(None),
        ).first()
        if active:
            active.end_time = now.time()
            if active.start_time:
                start_dt = datetime.combine(active.date or date.today(), active.start_time)
                active.duration_hours = round((datetime.combine(date.today(), now.time()) - start_dt).total_seconds() / 3600, 2)
            db.commit()

        entry = TimeEntry(
            technician_id=tech.id, job_id=job_id,
            start_time=now.time(), date=date.today(),
            entry_type='regular', status='draft', source='clock_in_out',
            created_by=current_user.id,
        )
        db.add(entry)

        job = db.query(Job).filter_by(id=job_id).first()
        if job and job.status in ('draft', 'scheduled', 'pending'):
            job.status = 'in_progress'
            if not job.started_at:
                job.started_at = now

        db.commit()
        flash('Clocked in!', 'success')
    finally:
        db.close()
    return redirect(url_for('mobile.job_detail', job_id=job_id))


@mobile_bp.route('/jobs/<int:job_id>/clock-out', methods=['POST'])
@mobile_login_required
def job_clock_out(job_id):
    """Clock out from a job."""
    db = get_session()
    try:
        tech = g.technician
        now = datetime.now()
        active = db.query(TimeEntry).filter(
            TimeEntry.technician_id == tech.id, TimeEntry.job_id == job_id,
            TimeEntry.end_time.is_(None),
        ).first()
        if active:
            active.end_time = now.time()
            if active.start_time:
                start_dt = datetime.combine(active.date or date.today(), active.start_time)
                active.duration_hours = round((datetime.combine(date.today(), now.time()) - start_dt).total_seconds() / 3600, 2)
            desc = request.form.get('description', '').strip()
            if desc:
                active.description = desc
            db.commit()
            flash('Clocked out.', 'success')
        else:
            flash('No active clock entry found.', 'warning')
    finally:
        db.close()
    return redirect(url_for('mobile.job_detail', job_id=job_id))


@mobile_bp.route('/jobs/<int:job_id>/complete', methods=['GET', 'POST'])
@mobile_login_required
def complete_job(job_id):
    """Job completion wizard — GET shows wizard, POST processes it."""
    db = get_session()
    try:
        tech = g.technician
        now = datetime.now()
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            flash('Job not found.', 'error')
            return redirect(url_for('mobile.job_list'))

        if request.method == 'POST':
            # 1. Clock out if still in
            active = db.query(TimeEntry).filter(
                TimeEntry.technician_id == tech.id, TimeEntry.job_id == job_id,
                TimeEntry.end_time.is_(None),
            ).first()
            if active:
                active.end_time = now.time()
                if active.start_time:
                    start_dt = datetime.combine(active.date or date.today(), active.start_time)
                    active.duration_hours = round((datetime.combine(date.today(), now.time()) - start_dt).total_seconds() / 3600, 2)

            # 2. Save work summary
            summary = request.form.get('work_summary', '').strip()
            if summary:
                existing_desc = job.description or ''
                job.description = f"{existing_desc}\n\n[Completion Notes] {summary}".strip()

            # 3. Save completion photo if provided
            if 'completion_photo' in request.files:
                file = request.files['completion_photo']
                if file and file.filename:
                    ext = os.path.splitext(file.filename)[1] or '.jpg'
                    fname = f'job_{job.id}_after_{uuid.uuid4().hex[:6]}{ext}'
                    upload_dir = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), 'job_photos')
                    os.makedirs(upload_dir, exist_ok=True)
                    file.save(os.path.join(upload_dir, fname))
                    doc = Document(
                        entity_type='job', entity_id=job.id,
                        filename=fname, file_path=os.path.join(upload_dir, fname),
                        file_type=file.content_type or 'image/jpeg',
                        display_name='Completion photo', category='after',
                        uploaded_by=current_user.id,
                    )
                    db.add(doc)

            # 4. Mark job complete
            job.status = 'completed'
            job.completed_at = now

            db.commit()
            return redirect(url_for('mobile.job_complete_success', job_id=job.id))

        # GET — show wizard
        active_entry = db.query(TimeEntry).filter(
            TimeEntry.technician_id == tech.id, TimeEntry.job_id == job_id,
            TimeEntry.end_time.is_(None),
        ).first()

        time_entries = db.query(TimeEntry).filter(
            TimeEntry.job_id == job_id, TimeEntry.technician_id == tech.id,
            TimeEntry.date == date.today(),
        ).all()

        materials = db.query(JobMaterial).filter_by(job_id=job_id).all()

        photos = db.query(Document).filter_by(
            entity_type='job', entity_id=job_id,
        ).all()

        checklists = []
        incomplete_checklists = []
        try:
            from models.checklist import CompletedChecklist, ChecklistTemplate
            checklists = db.query(CompletedChecklist).filter_by(job_id=job_id).all()
            # Find templates assigned but not completed
            completed_template_ids = {c.template_id for c in checklists}
            all_templates = db.query(ChecklistTemplate).filter_by(is_active=True).all()
            incomplete_checklists = [t for t in all_templates if t.id not in completed_template_ids]
        except Exception:
            pass

        return render_template('mobile/complete_wizard.html',
            active_nav='jobs', job=job,
            active_entry=active_entry, time_entries=time_entries,
            materials=materials, photos=photos,
            checklists=checklists, incomplete_checklists=incomplete_checklists,
        )
    finally:
        db.close()


@mobile_bp.route('/jobs/<int:job_id>/complete/success')
@mobile_login_required
def job_complete_success(job_id):
    """Success screen after job completion."""
    db = get_session()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        return render_template('mobile/job_complete_success.html',
            active_nav='jobs', job=job,
        )
    finally:
        db.close()


@mobile_bp.route('/jobs/<int:job_id>/add-note', methods=['POST'])
@mobile_login_required
def job_add_note(job_id):
    """Add a field note."""
    db = get_session()
    try:
        tech = g.technician
        note_text = request.form.get('note', '').strip()
        if not note_text:
            flash('Note cannot be empty.', 'warning')
            return redirect(url_for('mobile.job_detail', job_id=job_id))

        from models.communication import CommunicationLog
        comm = CommunicationLog(
            job_id=job_id, communication_type='note', direction='internal',
            subject=f'Field note from {tech.first_name or "Tech"}',
            description=note_text, logged_by_id=current_user.id,
            communication_date=datetime.now(),
        )
        db.add(comm)
        db.commit()
        flash('Note added.', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {e}', 'error')
    finally:
        db.close()
    return redirect(url_for('mobile.job_detail', job_id=job_id))


@mobile_bp.route('/jobs/<int:job_id>/upload-photo', methods=['POST'])
@mobile_login_required
def job_upload_photo(job_id):
    """Upload a photo."""
    db = get_session()
    try:
        if 'photo' not in request.files or request.files['photo'].filename == '':
            flash('No photo selected.', 'warning')
            return redirect(url_for('mobile.job_detail', job_id=job_id))

        photo = request.files['photo']
        category = request.form.get('photo_category', 'during')
        upload_dir = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), 'job_photos')
        os.makedirs(upload_dir, exist_ok=True)
        fname = f"job{job_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}.jpg"
        photo.save(os.path.join(upload_dir, fname))

        doc = Document(
            entity_type='job', entity_id=job_id,
            filename=fname, file_path=os.path.join(upload_dir, fname),
            file_type=photo.content_type or 'image/jpeg',
            display_name=f'{category.title()} photo', category=category,
            uploaded_by=current_user.id,
        )
        db.add(doc)
        db.commit()
        flash('Photo uploaded!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {e}', 'error')
    finally:
        db.close()
    return redirect(url_for('mobile.job_detail', job_id=job_id))


# ── Truck Stock ──────────────────────────────────────────────────────────────

@mobile_bp.route('/truck')
@mobile_login_required
def truck_stock():
    """Truck inventory."""
    db = get_session()
    try:
        tech = g.technician
        from models.inventory import InventoryLocation, InventoryTransaction

        truck_loc = db.query(InventoryLocation).filter_by(technician_id=tech.id).first()
        if not truck_loc:
            truck_loc = db.query(InventoryLocation).filter(
                InventoryLocation.location_type.in_(['truck', 'vehicle']),
                InventoryLocation.name.ilike(f'%{tech.first_name or ""}%'),
            ).first()

        items = []
        if truck_loc:
            txns = db.query(InventoryTransaction).filter_by(location_id=truck_loc.id).all()
            stock = {}
            for t in txns:
                stock.setdefault(t.part_id, 0)
                if t.transaction_type in ('received', 'transferred_in', 'returned'):
                    stock[t.part_id] += (t.quantity or 0)
                elif t.transaction_type in ('issued', 'transferred_out', 'scrapped'):
                    stock[t.part_id] -= (t.quantity or 0)

            part_ids = [pid for pid, qty in stock.items() if qty > 0]
            parts = {p.id: p for p in db.query(Part).filter(Part.id.in_(part_ids)).all()} if part_ids else {}

            items = sorted([
                {'part_id': pid, 'name': parts[pid].name if pid in parts else f'Part #{pid}',
                 'part_number': parts[pid].part_number if pid in parts else '',
                 'qty': stock[pid],
                 'reorder_qty': parts[pid].reorder_quantity if pid in parts and hasattr(parts[pid], 'reorder_quantity') else None}
                for pid in part_ids if stock[pid] > 0
            ], key=lambda x: x['name'])

        # Today's jobs for "I Used This" modal
        import json
        todays_jobs = get_tech_jobs_today(db, tech)
        todays_jobs_json = json.dumps([
            {'id': j.id, 'number': j.job_number or str(j.id), 'title': j.title or 'Job'}
            for j in todays_jobs if j.status != 'completed'
        ])

        return render_template('mobile/truck.html',
            active_nav='truck', truck_location=truck_loc, items=items,
            todays_jobs_json=todays_jobs_json,
        )
    finally:
        db.close()


# ── More Menu ────────────────────────────────────────────────────────────────

@mobile_bp.route('/more')
@mobile_login_required
def menu():
    """More menu."""
    db = get_session()
    try:
        tech = g.technician
        unread = db.query(Notification).filter_by(
            recipient_id=current_user.id, is_read=False,
        ).count()

        expiring_certs = 0
        try:
            from models.certification import TechnicianCertification
            threshold = date.today() + timedelta(days=30)
            expiring_certs = db.query(TechnicianCertification).filter(
                TechnicianCertification.technician_id == tech.id,
                TechnicianCertification.expiry_date <= threshold,
                TechnicianCertification.expiry_date >= date.today(),
            ).count()
        except Exception:
            pass

        return render_template('mobile/more.html',
            active_nav='menu', unread_count=unread, expiring_certs=expiring_certs,
        )
    finally:
        db.close()


# ── Notifications ────────────────────────────────────────────────────────────

@mobile_bp.route('/notifications')
@mobile_login_required
def notifications():
    """Notification list."""
    db = get_session()
    try:
        notifs = db.query(Notification).filter_by(
            recipient_id=current_user.id,
        ).order_by(Notification.created_at.desc()).limit(50).all()

        return render_template('mobile/notifications.html',
            active_nav='menu', notifications=notifs,
        )
    finally:
        db.close()


@mobile_bp.route('/notifications/<int:nid>/read', methods=['POST'])
@mobile_login_required
def mark_read(nid):
    """Mark notification as read."""
    db = get_session()
    try:
        n = db.query(Notification).filter_by(id=nid).first()
        if n and n.recipient_id == current_user.id:
            n.is_read = True
            n.read_at = datetime.now()
            db.commit()
    finally:
        db.close()
    return redirect(url_for('mobile.notifications'))


# ── Expenses & Mileage ──────────────────────────────────────────────────────

@mobile_bp.route('/expense', methods=['GET', 'POST'])
@mobile_bp.route('/expense/<int:job_id>', methods=['GET', 'POST'])
@mobile_login_required
def log_expense(job_id=None):
    """Log an expense."""
    db = get_session()
    try:
        tech = g.technician
        if request.method == 'POST':
            amount = request.form.get('amount', 0, type=float)
            expense = Expense(
                job_id=request.form.get('job_id', type=int) or None,
                expense_category=request.form.get('category', 'other'),
                title=request.form.get('description', '').strip() or 'Mobile Expense',
                description=request.form.get('description', '').strip(),
                amount=amount, total_amount=amount,
                expense_date=date.today(), status='draft',
                paid_by=current_user.id, created_by=current_user.id,
            )
            db.add(expense)
            db.commit()
            flash('Expense logged!', 'success')
            redir_job = request.form.get('job_id', type=int)
            if redir_job:
                return redirect(url_for('mobile.job_detail', job_id=redir_job))
            return redirect(url_for('mobile.menu'))

        jobs = db.query(Job).filter(
            Job.assigned_technician_id == tech.id,
            Job.status.notin_(['completed', 'cancelled']),
        ).order_by(Job.scheduled_date.desc()).limit(20).all()
        return render_template('mobile/expense_form.html',
            active_nav='menu', job_id=job_id, jobs=jobs,
        )
    finally:
        db.close()


@mobile_bp.route('/mileage', methods=['GET', 'POST'])
@mobile_bp.route('/mileage/<int:job_id>', methods=['GET', 'POST'])
@mobile_login_required
def log_mileage(job_id=None):
    """Log mileage."""
    db = get_session()
    try:
        tech = g.technician
        if request.method == 'POST':
            miles = request.form.get('miles', 0, type=float)
            rate = 0.70
            amount = round(miles * rate, 2)
            expense = Expense(
                job_id=request.form.get('job_id', type=int) or None,
                expense_category='mileage',
                title=f'{miles} miles', description=request.form.get('description', f'{miles} miles').strip(),
                amount=amount, total_amount=amount,
                expense_date=date.today(), status='draft',
                is_reimbursable=True,
                paid_by=current_user.id, created_by=current_user.id,
            )
            db.add(expense)
            db.commit()
            flash(f'Mileage: {miles} mi = ${amount:.2f}', 'success')
            redir_job = request.form.get('job_id', type=int)
            if redir_job:
                return redirect(url_for('mobile.job_detail', job_id=redir_job))
            return redirect(url_for('mobile.menu'))

        jobs = db.query(Job).filter(
            Job.assigned_technician_id == tech.id,
            Job.status.notin_(['completed', 'cancelled']),
        ).order_by(Job.scheduled_date.desc()).limit(20).all()
        return render_template('mobile/mileage_form.html',
            active_nav='menu', job_id=job_id, jobs=jobs,
        )
    finally:
        db.close()


# ── Material Logging ─────────────────────────────────────────────────────────

@mobile_bp.route('/jobs/<int:job_id>/materials/add', methods=['GET', 'POST'])
@mobile_login_required
def job_add_material(job_id):
    """Add material to a job."""
    db = get_session()
    try:
        tech = g.technician
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            flash('Job not found.', 'error')
            return redirect(url_for('mobile.job_list'))

        if request.method == 'POST':
            mode = request.form.get('mode', 'custom')
            if mode == 'truck':
                part_id = request.form.get('part_id', type=int)
                quantity = request.form.get('quantity', 1, type=int)
                if not part_id:
                    flash('Select a part.', 'warning')
                    return redirect(url_for('mobile.job_add_material', job_id=job_id))

                part = db.query(Part).filter_by(id=part_id).first()
                mat = JobMaterial(
                    job_id=job_id, part_id=part_id,
                    custom_description=part.name if part else f'Part #{part_id}',
                    quantity=quantity,
                    unit_cost=float(part.cost_price or 0) if part else 0,
                    added_by=current_user.id, status='logged',
                )
                db.add(mat)
                try:
                    from models.inventory import InventoryLocation, InventoryTransaction
                    truck_loc = db.query(InventoryLocation).filter_by(technician_id=tech.id).first()
                    if truck_loc:
                        txn = InventoryTransaction(
                            location_id=truck_loc.id, part_id=part_id,
                            transaction_type='issued', quantity=quantity,
                            job_id=job_id, notes=f'Used on Job #{job.job_number or job.id}',
                            created_by=current_user.id,
                        )
                        db.add(txn)
                except Exception:
                    pass
            else:
                desc = request.form.get('description', '').strip()
                if not desc:
                    flash('Enter a description.', 'warning')
                    return redirect(url_for('mobile.job_add_material', job_id=job_id))
                mat = JobMaterial(
                    job_id=job_id,
                    custom_description=desc,
                    quantity=request.form.get('quantity', 1, type=int),
                    unit_cost=request.form.get('unit_cost', 0, type=float),
                    added_by=current_user.id, status='logged',
                )
                db.add(mat)

            db.commit()
            flash('Material logged!', 'success')
            return redirect(url_for('mobile.job_detail', job_id=job_id))

        # GET: build truck stock list
        truck_items = []
        try:
            from models.inventory import InventoryLocation, InventoryTransaction
            truck_loc = db.query(InventoryLocation).filter_by(technician_id=tech.id).first()
            if truck_loc:
                txns = db.query(InventoryTransaction).filter_by(location_id=truck_loc.id).all()
                stock = {}
                for t in txns:
                    stock.setdefault(t.part_id, 0)
                    if t.transaction_type in ('received', 'transferred_in', 'returned'):
                        stock[t.part_id] += (t.quantity or 0)
                    elif t.transaction_type in ('issued', 'transferred_out', 'scrapped'):
                        stock[t.part_id] -= (t.quantity or 0)
                pids = [pid for pid, qty in stock.items() if qty > 0]
                parts = {p.id: p for p in db.query(Part).filter(Part.id.in_(pids)).all()} if pids else {}
                truck_items = sorted([
                    {'part_id': pid, 'name': parts[pid].name if pid in parts else f'Part #{pid}',
                     'part_number': parts[pid].part_number if pid in parts else '', 'qty': stock[pid]}
                    for pid in pids if stock[pid] > 0
                ], key=lambda x: x['name'])
        except Exception:
            pass

        recent = db.query(JobMaterial).filter_by(job_id=job_id).order_by(JobMaterial.id.desc()).limit(5).all()
        return render_template('mobile/material_add.html',
            active_nav='jobs', job=job, truck_items=truck_items, recent_materials=recent,
        )
    finally:
        db.close()


# ── Phase Update ─────────────────────────────────────────────────────────────

@mobile_bp.route('/jobs/<int:job_id>/phase/<int:phase_id>', methods=['POST'])
@mobile_login_required
def job_update_phase(job_id, phase_id):
    """Update a phase status."""
    db = get_session()
    try:
        from models.job_phase import JobPhase
        phase = db.query(JobPhase).filter_by(id=phase_id).first()
        if phase and phase.job_id == job_id:
            new_status = request.form.get('status', '')
            if new_status:
                phase.status = new_status
                db.commit()
                flash(f'Phase updated.', 'success')
    finally:
        db.close()
    return redirect(url_for('mobile.job_detail', job_id=job_id))


# ── Restock Request ──────────────────────────────────────────────────────────

@mobile_bp.route('/truck/restock', methods=['GET', 'POST'])
@mobile_login_required
def restock_request():
    """Request parts restock from warehouse."""
    db = get_session()
    try:
        tech = g.technician
        from models.restock_request import RestockRequest
        from models.inventory import InventoryLocation, InventoryTransaction

        if request.method == 'POST':
            part_ids = request.form.getlist('part_id')
            quantities = request.form.getlist('quantity')
            notes = request.form.get('notes', '')

            count = 0
            for pid, qty in zip(part_ids, quantities):
                try:
                    pid = int(pid)
                    qty = float(qty)
                    if qty <= 0:
                        continue
                except (ValueError, TypeError):
                    continue

                rr = RestockRequest(
                    technician_id=current_user.id,
                    part_id=pid,
                    quantity_requested=qty,
                    notes=notes,
                )
                db.add(rr)
                count += 1

            db.commit()
            flash(f'Restock request submitted ({count} items)!', 'success')
            return redirect(url_for('mobile.truck_stock'))

        # GET: show form
        preselect_ids = request.args.getlist('part_id', type=int)
        items = []
        truck_loc = db.query(InventoryLocation).filter_by(technician_id=tech.id).first()
        if truck_loc:
            txns = db.query(InventoryTransaction).filter_by(location_id=truck_loc.id).all()
            stock = {}
            for t in txns:
                stock.setdefault(t.part_id, 0)
                if t.transaction_type in ('received', 'transferred_in', 'returned'):
                    stock[t.part_id] += (t.quantity or 0)
                elif t.transaction_type in ('issued', 'transferred_out', 'scrapped'):
                    stock[t.part_id] -= (t.quantity or 0)
            pids = list(stock.keys())
            parts = {p.id: p for p in db.query(Part).filter(Part.id.in_(pids)).all()} if pids else {}
            items = sorted([
                {'part_id': pid, 'name': parts[pid].name if pid in parts else f'Part #{pid}',
                 'part_number': parts[pid].part_number if pid in parts else '',
                 'qty': max(stock[pid], 0), 'preselected': pid in preselect_ids}
                for pid in pids if pid in parts
            ], key=lambda x: x['name'])

        return render_template('mobile/restock_request.html',
            active_nav='truck', items=items, preselect_ids=preselect_ids,
        )
    finally:
        db.close()


@mobile_bp.route('/api/log-used-part', methods=['POST'])
@mobile_login_required
def api_log_used_part():
    """Log material to job and decrement truck stock."""
    db = get_session()
    try:
        tech = g.technician
        job_id = request.form.get('job_id', type=int)
        part_id = request.form.get('part_id', type=int)
        quantity = request.form.get('quantity', type=float) or 1

        if not job_id or not part_id:
            flash('Please select a job.', 'error')
            return redirect(url_for('mobile.truck_stock'))

        job = db.query(Job).filter_by(id=job_id).first()
        part = db.query(Part).filter_by(id=part_id).first()
        mat = JobMaterial(
            job_id=job_id, part_id=part_id,
            custom_description=part.name if part else f'Part #{part_id}',
            quantity=quantity,
            unit_cost=float(part.cost_price or 0) if part else 0,
            added_by=current_user.id, status='logged',
        )
        db.add(mat)
        try:
            from models.inventory import InventoryLocation, InventoryTransaction
            truck_loc = db.query(InventoryLocation).filter_by(technician_id=tech.id).first()
            if truck_loc:
                txn = InventoryTransaction(
                    location_id=truck_loc.id, part_id=part_id,
                    transaction_type='issued', quantity=int(quantity),
                    job_id=job_id,
                    notes=f'Used on Job #{job.job_number or job.id}' if job else 'Used from truck',
                    created_by=current_user.id,
                )
                db.add(txn)
        except Exception:
            pass
        db.commit()
        flash('Material logged!', 'success')
    finally:
        db.close()
    return redirect(url_for('mobile.truck_stock'))


# ── Checklist Completion ─────────────────────────────────────────────────────

@mobile_bp.route('/jobs/<int:job_id>/checklist/<int:template_id>')
@mobile_login_required
def checklist_form(job_id, template_id):
    """Show checklist form for a job."""
    db = get_session()
    try:
        from models.checklist import ChecklistTemplate, ChecklistItem, CompletedChecklist, CompletedChecklistItem

        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            flash('Job not found.', 'error')
            return redirect(url_for('mobile.job_list'))

        template = db.query(ChecklistTemplate).filter_by(id=template_id).first()
        if not template:
            flash('Checklist not found.', 'error')
            return redirect(url_for('mobile.job_detail', job_id=job_id))

        items = db.query(ChecklistItem).filter_by(
            template_id=template_id
        ).order_by(ChecklistItem.sort_order).all()

        # Load existing completion if any
        existing = db.query(CompletedChecklist).filter_by(
            job_id=job_id, template_id=template_id,
        ).first()

        existing_responses = {}
        if existing:
            for resp in db.query(CompletedChecklistItem).filter_by(
                completed_checklist_id=existing.id,
            ).all():
                existing_responses[resp.checklist_item_id] = resp

        return render_template('mobile/checklist.html',
            active_nav='jobs', job=job, template=template,
            items=items, existing_responses=existing_responses,
        )
    finally:
        db.close()


@mobile_bp.route('/jobs/<int:job_id>/checklist/<int:template_id>/submit', methods=['POST'])
@mobile_login_required
def checklist_submit(job_id, template_id):
    """Submit completed checklist."""
    db = get_session()
    try:
        from models.checklist import ChecklistTemplate, ChecklistItem, CompletedChecklist, CompletedChecklistItem

        job = db.query(Job).filter_by(id=job_id).first()
        template = db.query(ChecklistTemplate).filter_by(id=template_id).first()
        items = db.query(ChecklistItem).filter_by(template_id=template_id).all()

        # Get or create CompletedChecklist
        completed = db.query(CompletedChecklist).filter_by(
            job_id=job_id, template_id=template_id,
        ).first()
        if not completed:
            completed = CompletedChecklist(
                job_id=job_id, template_id=template_id,
                completed_by=current_user.id,
            )
            db.add(completed)
            db.flush()

        all_pass = True
        has_fail = False
        any_blocking = False

        for item in items:
            answer = request.form.get(f'item_{item.id}', '')

            is_compliant = True
            if item.item_type in ('yes_no', 'pass_fail'):
                fail_value = 'no' if item.item_type == 'yes_no' else 'fail'
                if answer.lower() == fail_value:
                    is_compliant = False
                    has_fail = True
                    if item.failure_action == 'block_work':
                        any_blocking = True
            if not answer and item.is_required:
                is_compliant = False
            if not is_compliant:
                all_pass = False

            # Upsert response
            resp = db.query(CompletedChecklistItem).filter_by(
                completed_checklist_id=completed.id,
                checklist_item_id=item.id,
            ).first()
            if not resp:
                resp = CompletedChecklistItem(
                    completed_checklist_id=completed.id,
                    checklist_item_id=item.id,
                    sort_order=item.sort_order,
                )
                db.add(resp)
            resp.response = answer
            resp.is_compliant = is_compliant

        # Set status
        if all_pass:
            completed.overall_status = 'passed'
        elif has_fail and not any_blocking:
            completed.overall_status = 'passed_with_exceptions'
        else:
            completed.overall_status = 'failed'

        completed.completed_at = datetime.now()
        completed.completed_by = current_user.id
        db.commit()

        return render_template('mobile/checklist_result.html',
            active_nav='jobs', job=job,
            all_pass=all_pass, has_fail=has_fail, any_blocking=any_blocking,
        )
    finally:
        db.close()


# ── Photo Gallery ────────────────────────────────────────────────────────────

@mobile_bp.route('/jobs/<int:job_id>/photos')
@mobile_login_required
def job_photos(job_id):
    """Photo gallery for a job."""
    db = get_session()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            flash('Job not found.', 'error')
            return redirect(url_for('mobile.job_list'))

        tag_filter = request.args.get('tag', 'all')
        q = db.query(Document).filter_by(entity_type='job', entity_id=job_id)
        if tag_filter != 'all':
            q = q.filter(Document.category == tag_filter)

        photos = q.order_by(Document.created_at.desc()).all()

        return render_template('mobile/photos.html',
            active_nav='jobs', job=job, photos=photos,
            tag_filter=tag_filter,
            photo_tags=['before', 'during', 'after', 'issue', 'equipment', 'other'],
        )
    finally:
        db.close()


@mobile_bp.route('/jobs/<int:job_id>/photos/upload', methods=['POST'])
@mobile_login_required
def api_upload_photo(job_id):
    """Upload a photo to a job."""
    db = get_session()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            flash('Job not found.', 'error')
            return redirect(url_for('mobile.job_list'))

        if 'photo' not in request.files or request.files['photo'].filename == '':
            flash('No photo selected.', 'error')
            return redirect(url_for('mobile.job_photos', job_id=job_id))

        file = request.files['photo']
        tag = request.form.get('tag', 'other')
        caption = request.form.get('caption', '').strip()

        ext = os.path.splitext(file.filename)[1] or '.jpg'
        fname = f'job_{job_id}_{uuid.uuid4().hex[:8]}{ext}'
        upload_dir = os.path.join(current_app.config.get('UPLOAD_FOLDER', 'uploads'), 'job_photos')
        os.makedirs(upload_dir, exist_ok=True)
        file.save(os.path.join(upload_dir, fname))

        doc = Document(
            entity_type='job', entity_id=job_id,
            filename=fname, file_path=os.path.join(upload_dir, fname),
            file_type=file.content_type or 'image/jpeg',
            display_name=caption or f'{tag.title()} photo',
            category=tag,
            description=caption,
            uploaded_by=current_user.id,
        )
        db.add(doc)
        db.commit()
        flash('Photo saved!', 'success')
    except Exception as e:
        db.rollback()
        flash(f'Error: {e}', 'error')
    finally:
        db.close()
    return redirect(url_for('mobile.job_photos', job_id=job_id))


# ══════════════════════════════════════════════════════════════════════════════
# JSON API Endpoints — consumed by mobile JS for dynamic operations
# ══════════════════════════════════════════════════════════════════════════════

@mobile_bp.route('/api/today-jobs')
@mobile_login_required
def api_today_jobs():
    """JSON: today's jobs for offline caching."""
    db = get_session()
    try:
        tech = g.technician
        jobs = get_tech_jobs_today(db, tech)
        return jsonify([{
            'id': j.id, 'title': j.title or '',
            'job_number': j.job_number or str(j.id), 'status': j.status,
            'scheduled_date': j.scheduled_date.isoformat() if j.scheduled_date else None,
        } for j in jobs])
    finally:
        db.close()


@mobile_bp.route('/api/truck-stock')
@mobile_login_required
def api_truck_stock():
    """JSON: tech's truck stock."""
    db = get_session()
    try:
        tech = g.technician
        from models.inventory import InventoryLocation, InventoryTransaction
        truck_loc = db.query(InventoryLocation).filter_by(technician_id=tech.id).first()
        if not truck_loc:
            return jsonify([])
        txns = db.query(InventoryTransaction).filter_by(location_id=truck_loc.id).all()
        stock = {}
        for t in txns:
            stock.setdefault(t.part_id, 0)
            if t.transaction_type in ('received', 'transferred_in', 'returned'):
                stock[t.part_id] += (t.quantity or 0)
            elif t.transaction_type in ('issued', 'transferred_out', 'scrapped'):
                stock[t.part_id] -= (t.quantity or 0)
        pids = [pid for pid, qty in stock.items() if qty > 0]
        parts = {p.id: p for p in db.query(Part).filter(Part.id.in_(pids)).all()} if pids else {}
        return jsonify([{
            'part_id': pid, 'part_name': parts[pid].name if pid in parts else f'Part #{pid}',
            'part_number': parts[pid].part_number if pid in parts else '', 'qty': stock[pid],
        } for pid in pids if stock[pid] > 0])
    finally:
        db.close()


@mobile_bp.route('/api/clock-status')
@mobile_login_required
def api_clock_status():
    """JSON: current clock-in status."""
    db = get_session()
    try:
        tech = g.technician
        entry = db.query(TimeEntry).filter(
            TimeEntry.technician_id == tech.id, TimeEntry.end_time.is_(None),
        ).first()
        today_entries = db.query(TimeEntry).filter(
            TimeEntry.technician_id == tech.id, TimeEntry.date == date.today(),
            TimeEntry.end_time.isnot(None),
        ).all()
        today_secs = sum(int((e.duration_hours or 0) * 3600) for e in today_entries)
        if entry and entry.start_time:
            start_dt = datetime.combine(entry.date or date.today(), entry.start_time)
            today_secs += int((datetime.now() - start_dt).total_seconds())
        job_title = None
        if entry and entry.job_id:
            j = db.query(Job).filter_by(id=entry.job_id).first()
            job_title = j.title if j else None
        return jsonify({
            'clocked_in': entry is not None,
            'start_time': str(entry.start_time) if entry else None,
            'start_date': str(entry.date) if entry else None,
            'job_id': entry.job_id if entry else None,
            'job_title': job_title, 'today_seconds': today_secs,
        })
    finally:
        db.close()


@mobile_bp.route('/api/unread-count')
@mobile_login_required
def api_unread_count():
    """JSON: unread notification count."""
    db = get_session()
    try:
        count = db.query(Notification).filter_by(
            recipient_id=current_user.id, is_read=False,
        ).count()
        return jsonify({'count': count})
    finally:
        db.close()


@mobile_bp.route('/api/notifications/<int:nid>/read', methods=['POST'])
@mobile_login_required
def api_mark_notification_read(nid):
    """JSON: mark notification as read."""
    db = get_session()
    try:
        n = db.query(Notification).filter_by(id=nid).first()
        if n and n.recipient_id == current_user.id:
            n.is_read = True
            n.read_at = datetime.now()
            db.commit()
            return jsonify({'ok': True})
        return jsonify({'error': 'Not found'}), 404
    finally:
        db.close()


@mobile_bp.route('/api/notifications/mark-all-read', methods=['POST'])
@mobile_login_required
def api_mark_all_read():
    """JSON: mark all notifications read."""
    db = get_session()
    try:
        db.query(Notification).filter_by(
            recipient_id=current_user.id, is_read=False,
        ).update({'is_read': True, 'read_at': datetime.now()})
        db.commit()
        return jsonify({'ok': True})
    finally:
        db.close()


@mobile_bp.route('/api/jobs/<int:job_id>/status', methods=['POST'])
@mobile_login_required
def api_update_job_status(job_id):
    """JSON: update job status."""
    db = get_session()
    try:
        job = db.query(Job).filter_by(id=job_id).first()
        if not job:
            return jsonify({'error': 'Not found'}), 404
        data = request.get_json(silent=True) or {}
        new_status = data.get('status')
        if new_status not in ('in_progress', 'on_hold', 'scheduled'):
            return jsonify({'error': 'Invalid status'}), 400
        job.status = new_status
        if new_status == 'in_progress' and not job.started_at:
            job.started_at = datetime.now()
        db.commit()
        return jsonify({'ok': True, 'status': job.status})
    finally:
        db.close()
