"""Booking utilities: client matching, email, notifications."""
import secrets
import json
from datetime import datetime


def get_org_context():
    """Return organization info for booking templates."""
    from models.app_settings import AppSettings
    return {
        'name': AppSettings.get('company_name', 'FieldServicePro'),
        'phone': AppSettings.get('company_phone', ''),
        'email': AppSettings.get('company_email', ''),
        'logo_url': AppSettings.get('company_logo_url', ''),
        'favicon_url': '',
        'address': AppSettings.get('company_address', ''),
    }


def get_booking_settings():
    """Return booking-specific settings as a dict-like object."""
    from models.app_settings import AppSettings

    class Settings:
        pass

    s = Settings()
    s.booking_enabled_services = json.loads(
        AppSettings.get('booking_enabled_services', '["plumbing","hvac","electrical","general"]')
    )
    s.booking_max_photos = int(AppSettings.get('booking_max_photos', '5'))
    s.booking_available_days = int(AppSettings.get('booking_available_days', '14'))
    s.booking_confirmation_hours = int(AppSettings.get('booking_confirmation_hours', '4'))
    s.booking_require_photos = AppSettings.get('booking_require_photos', 'false') == 'true'
    s.booking_terms_url = AppSettings.get('booking_terms_url', '')
    s.booking_custom_message = AppSettings.get('booking_custom_message', '')
    s.booking_emergency_alert = AppSettings.get('booking_emergency_alert', 'true') == 'true'
    s.google_review_url = AppSettings.get('google_review_url', '')
    s.google_review_prompt_threshold = int(AppSettings.get('google_review_prompt_threshold', '4'))
    s.feedback_notification_threshold = int(AppSettings.get('feedback_notification_threshold', '2'))
    s.auto_send_survey = AppSettings.get('auto_send_survey', 'true') == 'true'
    s.survey_delay_hours = int(AppSettings.get('survey_delay_hours', '2'))
    s.survey_expiry_days = int(AppSettings.get('survey_expiry_days', '30'))
    s.survey_reminder_days = int(AppSettings.get('survey_reminder_days', '5'))
    s.survey_max_reminders = int(AppSettings.get('survey_max_reminders', '1'))
    return s


def match_existing_client(db, email=None, phone=None, ref=None):
    """Try to find an existing client by email or phone."""
    from models.client import Client

    if email:
        match = db.query(Client).filter(
            Client.email.ilike(email.strip())
        ).first()
        if match:
            return match

    if phone:
        clean = ''.join(c for c in phone if c.isdigit())
        if clean and len(clean) >= 7:
            clients = db.query(Client).filter(Client.phone.isnot(None)).limit(500).all()
            for c in clients:
                if c.phone:
                    c_clean = ''.join(d for d in c.phone if d.isdigit())
                    if clean and c_clean and (clean[-7:] == c_clean[-7:]):
                        return c

    if ref:
        return match_existing_client(db, email=ref, phone=ref)
    return None


def generate_booking_token():
    """Generate a unique booking token."""
    return secrets.token_urlsafe(16)


def build_confirmation_email(sr, org):
    """Return (subject, html_body) for customer confirmation email."""
    subject = f"Service Request Received — {org.get('name', 'FieldServicePro')}"
    urgency_labels = {
        'emergency': 'Emergency (same day)', 'high': 'Urgent (1-2 days)',
        'medium': 'Routine (this week)', 'low': 'Flexible (anytime)',
    }
    urgency_text = urgency_labels.get(sr.priority or 'medium', 'Routine')
    name = org.get('name', 'FieldServicePro')
    phone = org.get('phone', '')

    html = f"""
    <div style="font-family:sans-serif;max-width:560px;margin:0 auto;">
      <div style="background:#1a56db;padding:20px 24px;border-radius:8px 8px 0 0;">
        <h2 style="color:#fff;margin:0;">{name}</h2>
      </div>
      <div style="background:#fff;padding:24px;border:1px solid #e2e8f0;border-radius:0 0 8px 8px;">
        <h3 style="color:#1e293b;">Your request has been received!</h3>
        <p style="color:#475569;">Hi {sr.contact_name or 'there'},</p>
        <p style="color:#475569;">We've received your service request and will contact you shortly.</p>
        <div style="background:#f8fafc;border-radius:8px;padding:16px;margin:16px 0;">
          <p style="margin:4px 0;"><strong>Reference:</strong>
            <span style="color:#1a56db;font-weight:700;">{sr.request_number}</span></p>
          <p style="margin:4px 0;"><strong>Service:</strong> {(sr.request_type or '').title()}</p>
          <p style="margin:4px 0;"><strong>Urgency:</strong> {urgency_text}</p>
          <p style="margin:4px 0;"><strong>Location:</strong> {sr.customer_address or ''}</p>
        </div>
        <p style="color:#64748b;font-size:.9rem;margin-top:20px;">
          Thank you for choosing <strong>{name}</strong>!
        </p>
        {'<p style="color:#64748b;font-size:.85rem;">' + name + ' &middot; ' + phone + '</p>' if phone else ''}
      </div>
    </div>
    """
    return subject, html


def send_booking_notifications(db, sr, org):
    """Create in-app notifications for dispatchers about a new booking."""
    try:
        from web.utils.notification_service import NotificationService
        urgency_tag = ' 🚨 EMERGENCY' if sr.priority == 'emergency' else ''
        NotificationService.notify(
            event='booking_received',
            entity=sr,
            title=f'New Online Booking{urgency_tag}',
            message=f'From: {sr.contact_name} - {(sr.request_type or "").title()} - {(sr.priority or "").title()}',
        )
    except Exception:
        pass


def validate_booking_submission(form):
    """Validate booking form data. Returns (errors_list, is_valid)."""
    errors = []
    if not form.get('service_type', '').strip():
        errors.append('Please select a service type.')
    if not form.get('description', '').strip():
        errors.append('Please describe your issue.')
    if not form.get('street_address', '').strip():
        errors.append('Street address is required.')
    if not form.get('city', '').strip():
        errors.append('City is required.')
    if not form.get('first_name', '').strip():
        errors.append('First name is required.')
    if not form.get('last_name', '').strip():
        errors.append('Last name is required.')
    if not form.get('phone', '').strip():
        errors.append('Phone number is required.')
    if not form.get('email', '').strip():
        errors.append('Email is required.')
    if form.get('website', '').strip():
        errors.append('Spam detected.')
    return errors, len(errors) == 0
