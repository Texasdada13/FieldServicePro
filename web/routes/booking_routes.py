"""Online Booking Blueprint — /book
Public-facing, no authentication required.
"""
import json
import os
import secrets
import time
from datetime import datetime
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, current_app, session as flask_session, abort)

from models.database import get_session
from models.service_request import ServiceRequest
from web.utils.booking_utils import (
    get_org_context, get_booking_settings, generate_booking_token,
    validate_booking_submission, match_existing_client,
    build_confirmation_email, send_booking_notifications,
)

booking_bp = Blueprint('booking', __name__, url_prefix='/book')

# Simple in-process rate limiter
_rate_store = {}


def _check_rate_limit(ip, limit=5, window=3600):
    now = time.time()
    bucket = _rate_store.get(ip, [])
    bucket = [t for t in bucket if now - t < window]
    if len(bucket) >= limit:
        return False
    bucket.append(now)
    _rate_store[ip] = bucket
    return True


@booking_bp.route('/')
def form():
    """Display the multi-step booking form."""
    org = get_org_context()
    settings = get_booking_settings()
    embed_mode = request.args.get('embed') == '1'

    csrf_token = secrets.token_hex(16)
    flask_session['booking_csrf'] = csrf_token

    return render_template('booking/form.html',
        org=org, booking_settings=settings,
        embed_mode=embed_mode, now=datetime.now(),
        csrf_token_field=f'<input type="hidden" name="_csrf_token" value="{csrf_token}">',
    )


@booking_bp.route('/embed')
def embed():
    """Embeddable version of the booking form."""
    org = get_org_context()
    settings = get_booking_settings()
    csrf_token = secrets.token_hex(16)
    flask_session['booking_csrf'] = csrf_token

    return render_template('booking/form.html',
        org=org, booking_settings=settings,
        embed_mode=True, now=datetime.now(),
        csrf_token_field=f'<input type="hidden" name="_csrf_token" value="{csrf_token}">',
    )


@booking_bp.route('/submit', methods=['POST'])
def submit():
    """Process booking form submission."""
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr or '').split(',')[0].strip()

    # Rate limit
    if not _check_rate_limit(client_ip):
        return render_template('booking/error.html',
            org=get_org_context(),
            message='Too many requests. Please try again later or call us directly.',
            now=datetime.now(),
        ), 429

    # Honeypot
    if request.form.get('website', '').strip():
        return redirect(url_for('booking.confirmation', token='ok'))

    f = request.form
    errors, is_valid = validate_booking_submission(f)
    if not is_valid:
        for err in errors:
            flash(err, 'error')
        return redirect(url_for('booking.form'))

    db = get_session()
    try:
        # Build address
        addr_parts = [f.get('street_address', '')]
        if f.get('unit_apt'):
            addr_parts.append(f.get('unit_apt'))
        addr_parts.extend([f.get('city', ''), f.get('state_province', ''), f.get('postal_code', '')])
        full_address = ', '.join(p for p in addr_parts if p)

        # Parse dates
        try:
            preferred_dates = json.loads(f.get('preferred_dates', '[]'))
        except Exception:
            preferred_dates = []

        # Map urgency to priority
        urgency_map = {'emergency': 'emergency', 'urgent': 'high', 'routine': 'medium', 'flexible': 'low'}
        priority = urgency_map.get(f.get('urgency', 'routine'), 'medium')

        # Match existing client
        matched_client = match_existing_client(
            db, email=f.get('email'), phone=f.get('phone'),
            ref=f.get('existing_customer_ref') if f.get('is_existing_customer') else None,
        )

        # Determine org_id
        from models.user import Organization
        org_record = db.query(Organization).first()
        org_id = org_record.id if org_record else 1

        token = generate_booking_token()
        req_number = ServiceRequest.generate_number(db, org_id)

        sr = ServiceRequest(
            request_number=req_number,
            organization_id=org_id,
            contact_name=f"{f.get('first_name', '')} {f.get('last_name', '')}".strip(),
            contact_phone=f.get('phone', '').strip()[:30],
            contact_email=f.get('email', '').strip()[:200],
            source='online_booking',
            request_type=f.get('service_type', 'general'),
            priority=priority,
            description=f.get('description', '').strip()[:5000],
            status='new',
            client_id=matched_client.id if matched_client else None,
            preferred_dates=json.dumps(preferred_dates) if preferred_dates else None,
            preferred_time_slot=f.get('preferred_time_slot', 'anytime'),
            referral_source=f.get('referral_source', ''),
            access_instructions=f.get('access_instructions', '').strip()[:1000],
            customer_address=full_address,
            street_address=f.get('street_address', '').strip()[:200],
            unit_apt=f.get('unit_apt', '').strip()[:50] or None,
            city=f.get('city', '').strip()[:100],
            state_province=f.get('state_province', '').strip()[:100],
            postal_code=f.get('postal_code', '').strip()[:20],
            is_existing_customer=bool(f.get('is_existing_customer')),
            existing_customer_ref=f.get('existing_customer_ref', '').strip()[:200] or None,
            booking_token=token,
            honeypot_check=True,
            submitter_ip=client_ip,
        )
        db.add(sr)
        db.flush()

        # Photo uploads
        photos = request.files.getlist('photos')
        saved_photos = []
        if photos:
            upload_dir = os.path.join(
                current_app.config.get('UPLOAD_FOLDER', 'uploads'), 'booking_photos',
            )
            os.makedirs(upload_dir, exist_ok=True)
            for photo in photos[:5]:
                if photo and photo.filename:
                    ext = os.path.splitext(photo.filename)[1] or '.jpg'
                    fname = f"booking_{sr.id}_{secrets.token_hex(4)}{ext}"
                    photo.save(os.path.join(upload_dir, fname))
                    saved_photos.append(fname)

        if saved_photos:
            existing_notes = sr.notes or ''
            sr.notes = f"{existing_notes}\n[Photos: {', '.join(saved_photos)}]".strip()

        # Confirmation email
        org = get_org_context()
        email = f.get('email', '').strip()
        if email:
            try:
                from web.utils.email_service import EmailService
                subject, html_body = build_confirmation_email(sr, org)
                EmailService.send_client_email(
                    to_email=email, subject=subject, body_html=html_body,
                )
                sr.confirmation_sent = True
                sr.confirmation_sent_at = datetime.now()
            except Exception as e:
                current_app.logger.warning(f'Booking email failed: {e}')

        # Dispatcher notifications
        try:
            send_booking_notifications(db, sr, org)
        except Exception:
            pass

        db.commit()
        return redirect(url_for('booking.confirmation', token=token))

    except Exception as e:
        db.rollback()
        flash(f'An error occurred. Please try again.', 'error')
        current_app.logger.error(f'Booking submit error: {e}')
        return redirect(url_for('booking.form'))
    finally:
        db.close()


@booking_bp.route('/confirmation/<token>')
def confirmation(token):
    """Show booking confirmation."""
    org = get_org_context()
    settings = get_booking_settings()

    if token == 'ok':
        return render_template('booking/confirmation.html',
            org=org, sr=None, booking_settings=settings, now=datetime.now())

    db = get_session()
    try:
        sr = db.query(ServiceRequest).filter_by(booking_token=token).first()
        dates_display = []
        if sr and sr.preferred_dates:
            try:
                dates_display = json.loads(sr.preferred_dates)
            except Exception:
                pass

        return render_template('booking/confirmation.html',
            org=org, sr=sr, booking_settings=settings,
            dates_display=dates_display, now=datetime.now(),
        )
    finally:
        db.close()


@booking_bp.route('/status/<token>')
def status(token):
    """Public booking status page."""
    db = get_session()
    try:
        sr = db.query(ServiceRequest).filter_by(booking_token=token).first()
        if not sr:
            flash('Booking not found.', 'error')
            return redirect(url_for('booking.form'))
        org = get_org_context()
        return render_template('booking/status.html',
            org=org, sr=sr, now=datetime.now())
    finally:
        db.close()
