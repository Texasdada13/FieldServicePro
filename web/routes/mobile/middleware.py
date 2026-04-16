"""Mobile detection middleware."""
import re
from flask import request, session

MOBILE_UA_PATTERN = re.compile(
    r'(android|bb\d+|meego).+mobile|avantgo|bada\/|blackberry|blazer|compal|elaine|fennec'
    r'|hiptop|iemobile|ip(hone|od)|iris|kindle|lge |maemo|midp|mmp|mobile.+firefox|netfront'
    r'|opera m(ob|in)i|palm( os)?|phone|p(ixi|re)\/|plucker|pocket|psp|series(4|6)0|symbian'
    r'|treo|up\.(browser|link)|vodafone|wap|windows ce|xda|xiino',
    re.IGNORECASE
)


def is_mobile_ua():
    """Check if the User-Agent indicates a mobile device."""
    ua = request.headers.get('User-Agent', '')
    return bool(MOBILE_UA_PATTERN.search(ua))


def wants_mobile_view():
    """Return True if we should serve the mobile shell.
    Priority: explicit session preference > URL path > user-agent.
    """
    if session.get('force_desktop'):
        return False
    if request.path.startswith('/mobile'):
        return True
    if session.get('force_mobile'):
        return True
    return False


def should_show_mobile_banner():
    """Show the 'Switch to mobile' banner on desktop pages for mobile UA."""
    if request.path.startswith('/mobile'):
        return False
    if session.get('mobile_banner_dismissed'):
        return False
    if session.get('force_desktop'):
        return False
    return is_mobile_ua()
