"""SMSService — placeholder. Replace with Twilio/Vonage when ready."""
import logging
from datetime import datetime

log = logging.getLogger(__name__)


class SMSService:
    @staticmethod
    def send(to_number, message, db=None, entity_type=None, entity_id=None):
        log.info("SMS (placeholder): To=%s Message=%s", to_number, message[:80])
        if db:
            try:
                from models.notification import NotificationLog
                db.add(NotificationLog(
                    channel='sms', recipient_type='client',
                    recipient_phone=to_number, body=message,
                    status='logged_not_sent', error_message='SMS provider not configured',
                    entity_type=entity_type, entity_id=entity_id,
                ))
            except Exception:
                pass
        return False

    @staticmethod
    def is_configured():
        return False
