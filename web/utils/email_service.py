"""EmailService — wraps Flask-Mail with console fallback for dev."""
import logging
import os
import re

log = logging.getLogger(__name__)


class EmailService:

    @staticmethod
    def _is_configured():
        return bool(os.environ.get('MAIL_SERVER') or os.environ.get('MAIL_USERNAME'))

    @staticmethod
    def send_internal_notification_email(to_email, to_name, title, message, action_url=None, category='system', notif_type='info'):
        subject = f'[FieldServicePro] {title}'
        body = f"{title}\n\n{message}"
        if action_url:
            body += f"\n\nView: {action_url}"
        return EmailService._send(to_email, subject, body)

    @staticmethod
    def send_client_email(to_email, subject, body_html, entity_type=None, entity_id=None):
        text = re.sub(r'<[^>]+>', ' ', body_html).strip()
        text = re.sub(r'\s+', ' ', text)
        return EmailService._send(to_email, subject, text)

    @staticmethod
    def _send(to_email, subject, text):
        if not EmailService._is_configured():
            log.info("EMAIL (console): To=%s Subject=%s", to_email, subject)
            return True

        try:
            from flask_mail import Message
            from flask import current_app
            mail = current_app.extensions.get('mail')
            if not mail:
                log.warning("Flask-Mail not initialized")
                return False
            msg = Message(subject=subject, recipients=[to_email], body=text)
            mail.send(msg)
            return True
        except Exception as e:
            log.error("Email failed to %s: %s", to_email, e)
            return False
