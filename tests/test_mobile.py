"""Tests for mobile technician view."""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_mobile_blueprint_registration():
    """Test that mobile blueprint is registered."""
    from web.app import app
    assert 'mobile' in app.blueprints, "Mobile blueprint not registered"


def test_mobile_routes_exist():
    """Test that key mobile routes are registered."""
    from web.app import app
    rules = [rule.rule for rule in app.url_map.iter_rules()]

    expected_routes = [
        '/mobile/',
        '/mobile/today',
        '/mobile/jobs',
        '/mobile/clock',
        '/mobile/truck',
        '/mobile/more',
        '/mobile/notifications',
        '/mobile/expense',
        '/mobile/mileage',
    ]

    for route in expected_routes:
        assert route in rules, f"Route {route} not found in URL map"


def test_mobile_user_agent_detection():
    """Test mobile user agent detection."""
    from web.routes.mobile.helpers import is_mobile_user_agent
    from web.app import app

    with app.test_request_context(headers={'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X)'}):
        assert is_mobile_user_agent() is True

    with app.test_request_context(headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}):
        assert is_mobile_user_agent() is False


def test_mobile_css_exists():
    """Test that mobile CSS file exists."""
    css_path = os.path.join('web', 'static', 'css', 'mobile.css')
    assert os.path.exists(css_path), f"Mobile CSS not found at {css_path}"


def test_mobile_js_exists():
    """Test that mobile JS file exists."""
    js_path = os.path.join('web', 'static', 'js', 'mobile.js')
    assert os.path.exists(js_path), f"Mobile JS not found at {js_path}"


def test_unread_notification_filter():
    """Test the unread_notification_count template filter."""
    from web.app import app
    assert 'unread_notification_count' in app.jinja_env.filters


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
