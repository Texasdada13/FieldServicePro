"""tests/test_change_orders.py — CO creation, cost, approval tests."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import Base, engine, get_session
from models.job import Job
from models.change_order import ChangeOrder, ChangeOrderLineItem, ChangeOrderStatus
from models.user import Organization
from web.utils.change_order_utils import (
    create_change_order, generate_co_number,
    apply_approved_change_order, can_create_change_order,
)


def setup_module():
    Base.metadata.create_all(engine)


def _create_job(db, status='scheduled'):
    org = db.query(Organization).first()
    if not org:
        org = Organization(name='Test Org')
        db.add(org)
        db.flush()
    job = Job(
        organization_id=org.id, division_id=1, client_id=1,
        title='Test Job', status=status,
        job_number=f'JOB-TEST-CO-{status}',
        estimated_amount=50000.0,
        original_estimated_cost=50000.0,
    )
    db.add(job)
    db.flush()
    return job


class TestCONumberGeneration:
    def test_format(self):
        db = get_session()
        try:
            job = _create_job(db)
            number = generate_co_number(db, job)
            assert 'JOB-TEST-CO' in number
            assert number.endswith('-01')
        finally:
            db.rollback()
            db.close()

    def test_increments(self):
        db = get_session()
        try:
            job = _create_job(db)
            n1 = generate_co_number(db, job)
            co = ChangeOrder(
                change_order_number=n1, job_id=job.id,
                title='Test', description='Test CO',
                reason='client_request', status='draft',
                requested_by='client',
            )
            db.add(co)
            db.flush()
            n2 = generate_co_number(db, job)
            assert n2.endswith('-02')
        finally:
            db.rollback()
            db.close()


class TestCanCreateCO:
    def test_cannot_on_completed(self):
        db = get_session()
        try:
            job = _create_job(db, status='completed')
            allowed, reason = can_create_change_order(job)
            assert not allowed
        finally:
            db.rollback()
            db.close()

    def test_can_on_scheduled(self):
        db = get_session()
        try:
            job = _create_job(db, status='scheduled')
            allowed, reason = can_create_change_order(job)
            assert allowed
        finally:
            db.rollback()
            db.close()


class TestCostDifference:
    def test_addition(self):
        db = get_session()
        try:
            job = _create_job(db)
            co = create_change_order(db, job, {
                'title': 'Extra ductwork', 'description': 'More ducts',
                'reason': 'client_request', 'requested_by': 'client',
                'cost_type': 'addition',
                'original_amount': '50000', 'revised_amount': '53500',
            }, created_by_id=1)
            db.flush()
            assert co.cost_difference == 3500.0
        finally:
            db.rollback()
            db.close()

    def test_deduction(self):
        db = get_session()
        try:
            job = _create_job(db)
            co = create_change_order(db, job, {
                'title': 'Remove unit', 'description': 'Removed from scope',
                'reason': 'client_request', 'requested_by': 'client',
                'cost_type': 'deduction',
                'original_amount': '50000', 'revised_amount': '44000',
            }, created_by_id=1)
            db.flush()
            assert co.cost_difference == -6000.0
        finally:
            db.rollback()
            db.close()


class TestApproval:
    def test_approve_updates_job_cost(self):
        db = get_session()
        try:
            job = _create_job(db)
            co = create_change_order(db, job, {
                'title': 'Panel upgrade', 'description': '200A panel',
                'reason': 'unforeseen_condition', 'requested_by': 'field_tech',
                'cost_type': 'addition',
                'original_amount': '50000', 'revised_amount': '52000',
            }, created_by_id=1)
            co.status = 'approved'
            db.flush()
            apply_approved_change_order(db, co)
            db.flush()
            assert float(job.adjusted_estimated_cost) == 52000.0
        finally:
            db.rollback()
            db.close()


class TestLineItems:
    def test_signed_total(self):
        item = ChangeOrderLineItem(
            change_order_id=1, description='Extra wire',
            quantity=100, unit_price=2.50, is_addition=True,
        )
        assert item.line_total == 250.0
        assert item.signed_total == 250.0

        deduct = ChangeOrderLineItem(
            change_order_id=1, description='Remove unit',
            quantity=1, unit_price=500.0, is_addition=False,
        )
        assert deduct.signed_total == -500.0


class TestStatusWorkflow:
    def test_transitions(self):
        db = get_session()
        try:
            job = _create_job(db)
            co = create_change_order(db, job, {
                'title': 'Test', 'description': 'Test',
                'reason': 'other', 'requested_by': 'project_manager',
                'cost_type': 'no_change',
                'original_amount': '0', 'revised_amount': '0',
            }, created_by_id=1)
            db.flush()
            assert co.status == 'draft'
            assert co.is_editable

            co.status = 'submitted'
            assert co.awaiting_approval

            co.status = 'approved'
            assert not co.is_editable
            assert not co.awaiting_approval
        finally:
            db.rollback()
            db.close()
