"""tests/test_approval_workflow.py — Approval threshold and workflow tests."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import Base, engine, get_session
from models.settings import OrganizationSettings
from models.user import Organization


def setup_module():
    Base.metadata.create_all(engine)


def _create_settings(db):
    org = db.query(Organization).first()
    if not org:
        org = Organization(name='Test Org')
        db.add(org)
        db.flush()

    settings = OrganizationSettings.get_or_create(db, org.id)
    settings.invoice_approval_enabled = True
    settings.invoice_approval_threshold = 500.0
    settings.invoice_approval_roles = 'owner,admin'
    db.flush()
    return settings


class TestApprovalThreshold:
    def test_below_threshold_not_required(self):
        db = get_session()
        try:
            settings = _create_settings(db)
            assert not settings.requires_approval(400.0, 'commercial')
        finally:
            db.rollback()
            db.close()

    def test_above_threshold_required(self):
        db = get_session()
        try:
            settings = _create_settings(db)
            assert settings.requires_approval(600.0, 'commercial')
        finally:
            db.rollback()
            db.close()

    def test_residential_never_required(self):
        db = get_session()
        try:
            settings = _create_settings(db)
            assert not settings.requires_approval(9999.0, 'residential')
        finally:
            db.rollback()
            db.close()

    def test_approval_disabled_skips_all(self):
        db = get_session()
        try:
            settings = _create_settings(db)
            settings.invoice_approval_enabled = False
            db.flush()
            assert not settings.requires_approval(99999.0, 'commercial')
        finally:
            db.rollback()
            db.close()

    def test_none_threshold_requires_all(self):
        db = get_session()
        try:
            settings = _create_settings(db)
            settings.invoice_approval_threshold = None
            db.flush()
            assert settings.requires_approval(1.0, 'commercial')
        finally:
            db.rollback()
            db.close()

    def test_approval_role_list(self):
        db = get_session()
        try:
            settings = _create_settings(db)
            assert 'owner' in settings.approval_role_list
            assert 'admin' in settings.approval_role_list
            assert 'technician' not in settings.approval_role_list
        finally:
            db.rollback()
            db.close()
