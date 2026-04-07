"""tests/test_portal.py — Portal user model, auth, and permission tests."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import Base, engine, get_session
from models.portal_user import PortalUser
from models.portal_settings import PortalSettings
from models.user import Organization
from models.client import Client
from web.portal_auth import validate_password


def setup_module():
    Base.metadata.create_all(engine)


def _ensure_org(db):
    org = db.query(Organization).first()
    if not org:
        org = Organization(name='Test Org')
        db.add(org)
        db.flush()
    return org


def _ensure_client(db):
    org = _ensure_org(db)
    client = db.query(Client).filter_by(company_name='Portal Test Corp').first()
    if not client:
        client = Client(
            organization_id=org.id, company_name='Portal Test Corp',
            client_type='commercial', first_name='Test', last_name='Client',
        )
        db.add(client)
        db.flush()
    return client


def _create_portal_user(db, email, role='primary', password='Test1234'):
    client = _ensure_client(db)
    user = db.query(PortalUser).filter_by(email=email).first()
    if user:
        return user
    user = PortalUser(
        email=email, first_name='Test', last_name='User',
        client_id=client.id, role=role, invitation_accepted=True,
    )
    user.set_password(password)
    db.add(user)
    db.flush()
    return user


# ═══════════════════════════════════════════════════════════════════════════
#  PASSWORD VALIDATION
# ═══════════════════════════════════════════════════════════════════════════

class TestPasswordValidation:
    def test_too_short(self):
        valid, msg = validate_password('Ab1')
        assert not valid

    def test_no_number(self):
        valid, msg = validate_password('abcdefgh')
        assert not valid

    def test_no_letter(self):
        valid, msg = validate_password('12345678')
        assert not valid

    def test_valid(self):
        valid, msg = validate_password('Test1234')
        assert valid

    def test_valid_long(self):
        valid, msg = validate_password('MySecureP4ssword!')
        assert valid


# ═══════════════════════════════════════════════════════════════════════════
#  PORTAL USER MODEL
# ═══════════════════════════════════════════════════════════════════════════

class TestPortalUserModel:
    def test_set_and_check_password(self):
        db = get_session()
        try:
            user = _create_portal_user(db, 'pwd_test@test.com')
            user.set_password('NewPass123')
            db.commit()

            assert user.check_password('NewPass123')
            assert not user.check_password('wrong')
            assert not user.check_password('')
        finally:
            db.close()

    def test_full_name(self):
        db = get_session()
        try:
            user = _create_portal_user(db, 'name_test@test.com')
            assert user.full_name == 'Test User'
        finally:
            db.close()

    def test_role_label(self):
        db = get_session()
        try:
            user = _create_portal_user(db, 'role_test@test.com', role='primary')
            assert user.role_label == 'Primary Contact'
        finally:
            db.close()

    def test_reset_token(self):
        db = get_session()
        try:
            user = _create_portal_user(db, 'token_test@test.com')
            token = user.generate_reset_token()
            db.commit()

            assert token is not None
            assert user.validate_reset_token(token)
            assert not user.validate_reset_token('invalid_token')
        finally:
            db.close()

    def test_invitation_token(self):
        db = get_session()
        try:
            user = _create_portal_user(db, 'invite_test@test.com')
            token = user.generate_invitation_token()
            db.commit()

            assert token is not None
            assert user.validate_invitation_token(token)
            assert not user.validate_invitation_token('bad_token')
        finally:
            db.close()

    def test_lockout_after_failed_attempts(self):
        db = get_session()
        try:
            user = _create_portal_user(db, 'lockout_test@test.com')
            assert not user.is_locked

            for _ in range(5):
                user.record_failed_login()

            assert user.is_locked
            db.commit()
        finally:
            db.close()

    def test_login_resets_lockout(self):
        db = get_session()
        try:
            user = _create_portal_user(db, 'login_reset_test@test.com')
            for _ in range(5):
                user.record_failed_login()
            assert user.is_locked

            user.record_login()
            assert not user.is_locked
            assert user.login_attempts == 0
            assert user.last_login is not None
            db.commit()
        finally:
            db.close()


# ═══════════════════════════════════════════════════════════════════════════
#  ROLE PERMISSIONS
# ═══════════════════════════════════════════════════════════════════════════

class TestRolePermissions:
    def test_primary_has_all_permissions(self):
        db = get_session()
        try:
            user = _create_portal_user(db, 'perm_primary@test.com', role='primary')
            assert user.can_view_dashboard()
            assert user.can_view_properties()
            assert user.can_create_service_requests()
            assert user.can_view_jobs()
            assert user.can_view_quotes()
            assert user.can_approve_quotes()
            assert user.can_approve_change_orders()
            assert user.can_view_invoices()
            assert user.can_view_documents()
            assert user.can_upload_documents()
            assert user.can_view_reports()
            assert user.can_send_messages()
            assert user.can_manage_portal_users()
            assert user.can_view_financials()
        finally:
            db.close()

    def test_manager_permissions(self):
        db = get_session()
        try:
            user = _create_portal_user(db, 'perm_manager@test.com', role='manager')
            assert user.can_view_dashboard()
            assert user.can_view_quotes()
            assert user.can_approve_quotes()
            assert user.can_view_invoices()
            assert user.can_view_reports()
            assert not user.can_manage_portal_users()
        finally:
            db.close()

    def test_standard_permissions(self):
        db = get_session()
        try:
            user = _create_portal_user(db, 'perm_standard@test.com', role='standard')
            assert user.can_view_dashboard()
            assert user.can_create_service_requests()
            assert user.can_view_jobs()
            assert user.can_view_documents()
            assert user.can_upload_documents()
            assert user.can_send_messages()
            assert not user.can_view_quotes()
            assert not user.can_approve_quotes()
            assert not user.can_view_invoices()
            assert not user.can_view_reports()
            assert not user.can_manage_portal_users()
        finally:
            db.close()

    def test_billing_only_permissions(self):
        db = get_session()
        try:
            user = _create_portal_user(db, 'perm_billing@test.com', role='billing_only')
            assert user.can_view_invoices()
            assert user.can_view_financials()
            assert not user.can_view_dashboard()
            assert not user.can_view_jobs()
            assert not user.can_view_quotes()
            assert not user.can_create_service_requests()
            assert not user.can_view_reports()
            assert not user.can_send_messages()
        finally:
            db.close()

    def test_view_only_permissions(self):
        db = get_session()
        try:
            user = _create_portal_user(db, 'perm_viewonly@test.com', role='view_only')
            assert user.can_view_properties()
            assert user.can_view_jobs()
            assert user.can_view_documents()
            assert not user.can_view_dashboard()
            assert not user.can_create_service_requests()
            assert not user.can_view_quotes()
            assert not user.can_approve_quotes()
            assert not user.can_view_invoices()
            assert not user.can_upload_documents()
            assert not user.can_send_messages()
            assert not user.can_manage_portal_users()
        finally:
            db.close()


# ═══════════════════════════════════════════════════════════════════════════
#  PROPERTY ACCESS
# ═══════════════════════════════════════════════════════════════════════════

class TestPropertyAccess:
    def test_no_restrictions_returns_none(self):
        db = get_session()
        try:
            user = _create_portal_user(db, 'prop_all@test.com')
            assert user.get_property_ids() is None  # None = all properties
        finally:
            db.close()

    def test_restricted_returns_ids(self):
        from models.client import Property
        db = get_session()
        try:
            user = _create_portal_user(db, 'prop_restricted@test.com')
            client = user.client

            prop = db.query(Property).filter_by(client_id=client.id).first()
            if not prop:
                prop = Property(client_id=client.id, name='Test Prop', address='123 Test St')
                db.add(prop)
                db.flush()

            user.accessible_properties.append(prop)
            db.commit()

            ids = user.get_property_ids()
            assert ids is not None
            assert prop.id in ids
        finally:
            db.close()


# ═══════════════════════════════════════════════════════════════════════════
#  PORTAL SETTINGS
# ═══════════════════════════════════════════════════════════════════════════

class TestPortalSettings:
    def test_get_or_create(self):
        db = get_session()
        try:
            settings = PortalSettings.get_settings(db)
            assert settings is not None
            assert isinstance(settings.session_timeout_minutes, int)
        finally:
            db.close()

    def test_defaults(self):
        db = get_session()
        try:
            settings = PortalSettings.get_settings(db)
            assert settings.session_timeout_minutes == 30
            assert settings.allow_service_requests == True
        finally:
            db.close()


# ═══════════════════════════════════════════════════════════════════════════
#  IP RATE LIMITING
# ═══════════════════════════════════════════════════════════════════════════

class TestIPRateLimit:
    def test_allows_normal_traffic(self):
        from web.portal_auth import check_ip_rate_limit, _login_attempts
        _login_attempts.clear()
        for _ in range(5):
            assert check_ip_rate_limit('192.168.1.100')

    def test_blocks_excessive_traffic(self):
        from web.portal_auth import check_ip_rate_limit, _login_attempts
        _login_attempts.clear()
        for _ in range(10):
            check_ip_rate_limit('192.168.1.200')
        assert not check_ip_rate_limit('192.168.1.200')

    def test_different_ips_independent(self):
        from web.portal_auth import check_ip_rate_limit, _login_attempts
        _login_attempts.clear()
        for _ in range(10):
            check_ip_rate_limit('10.0.0.1')
        assert not check_ip_rate_limit('10.0.0.1')
        assert check_ip_rate_limit('10.0.0.2')  # Different IP is fine
