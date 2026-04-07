"""tests/test_phases.py — Phase creation, status, reorder, delete tests."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.database import Base, engine, get_session
from models.job import Job
from models.job_phase import JobPhase
from models.user import Organization
from web.utils.phase_utils import create_phase, delete_phase, reorder_phases
from web.utils.phase_status import can_transition, transition_phase_status


def setup_module():
    Base.metadata.create_all(engine)


def _create_job(db):
    org = db.query(Organization).first()
    if not org:
        org = Organization(name='Test Org')
        db.add(org)
        db.flush()
    job = Job(
        organization_id=org.id, division_id=1,
        client_id=1, title='Test Multi-Phase Job',
        status='scheduled', job_number='JOB-TEST-PHASE',
        estimated_amount=10000.0,
    )
    db.add(job)
    db.flush()
    return job


class TestPhaseCreation:
    def test_create_phase_sets_multi_phase_flag(self):
        db = get_session()
        try:
            job = _create_job(db)
            assert not job.is_multi_phase
            phase = create_phase(db, job, {'title': 'Phase 1: Demo', 'estimated_cost': 2500})
            db.flush()
            assert job.is_multi_phase
            assert phase.phase_number == 1
        finally:
            db.rollback()
            db.close()

    def test_create_multiple_phases_increments(self):
        db = get_session()
        try:
            job = _create_job(db)
            p1 = create_phase(db, job, {'title': 'Phase 1'})
            p2 = create_phase(db, job, {'title': 'Phase 2'})
            p3 = create_phase(db, job, {'title': 'Phase 3'})
            db.flush()
            assert p1.phase_number == 1
            assert p2.phase_number == 2
            assert p3.phase_number == 3
        finally:
            db.rollback()
            db.close()

    def test_original_cost_snapshot(self):
        db = get_session()
        try:
            job = _create_job(db)
            assert job.original_estimated_cost is None
            create_phase(db, job, {'title': 'P1', 'estimated_cost': 1000})
            db.flush()
            assert job.original_estimated_cost == 10000.0
        finally:
            db.rollback()
            db.close()


class TestPhaseTransitions:
    def test_valid_not_started_to_scheduled(self):
        db = get_session()
        try:
            job = _create_job(db)
            phase = create_phase(db, job, {'title': 'P1'})
            db.flush()
            ok, msg = can_transition(phase, 'scheduled')
            assert ok
        finally:
            db.rollback()
            db.close()

    def test_invalid_not_started_to_completed(self):
        db = get_session()
        try:
            job = _create_job(db)
            phase = create_phase(db, job, {'title': 'P1'})
            db.flush()
            ok, msg = can_transition(phase, 'completed')
            assert not ok
        finally:
            db.rollback()
            db.close()

    def test_complete_blocked_without_inspection(self):
        db = get_session()
        try:
            job = _create_job(db)
            phase = create_phase(db, job, {'title': 'P1', 'requires_inspection': True})
            phase.status = 'in_progress'
            db.flush()
            ok, msg = can_transition(phase, 'completed')
            assert not ok
            assert 'inspection' in msg.lower()
        finally:
            db.rollback()
            db.close()

    def test_complete_allowed_with_passed_inspection(self):
        db = get_session()
        try:
            job = _create_job(db)
            phase = create_phase(db, job, {'title': 'P1', 'requires_inspection': True})
            phase.status = 'in_progress'
            phase.inspection_status = 'passed'
            db.flush()
            ok, _ = can_transition(phase, 'completed')
            assert ok
        finally:
            db.rollback()
            db.close()


class TestJobStatusDerivation:
    def test_all_not_started_is_scheduled(self):
        db = get_session()
        try:
            job = _create_job(db)
            job.is_multi_phase = True
            create_phase(db, job, {'title': 'P1'})
            create_phase(db, job, {'title': 'P2'})
            db.flush()
            assert job.derived_status_from_phases == 'scheduled'
        finally:
            db.rollback()
            db.close()

    def test_one_in_progress(self):
        db = get_session()
        try:
            job = _create_job(db)
            job.is_multi_phase = True
            p1 = create_phase(db, job, {'title': 'P1'})
            p1.status = 'in_progress'
            db.flush()
            assert job.derived_status_from_phases == 'in_progress'
        finally:
            db.rollback()
            db.close()

    def test_all_complete(self):
        db = get_session()
        try:
            job = _create_job(db)
            job.is_multi_phase = True
            p1 = create_phase(db, job, {'title': 'P1'})
            p2 = create_phase(db, job, {'title': 'P2'})
            p1.status = 'completed'
            p2.status = 'skipped'
            db.flush()
            assert job.derived_status_from_phases == 'completed'
        finally:
            db.rollback()
            db.close()


class TestPhaseReorder:
    def test_reorder(self):
        db = get_session()
        try:
            job = _create_job(db)
            p1 = create_phase(db, job, {'title': 'P1'})
            p2 = create_phase(db, job, {'title': 'P2'})
            p3 = create_phase(db, job, {'title': 'P3'})
            db.flush()
            reorder_phases(db, job.id, [p3.id, p2.id, p1.id])
            db.flush()
            assert p3.sort_order < p2.sort_order < p1.sort_order
        finally:
            db.rollback()
            db.close()


class TestPhaseDelete:
    def test_delete_without_activity(self):
        db = get_session()
        try:
            job = _create_job(db)
            phase = create_phase(db, job, {'title': 'P1'})
            db.flush()
            pid = phase.id
            delete_phase(db, phase)
            db.flush()
            assert db.query(JobPhase).filter_by(id=pid).first() is None
        finally:
            db.rollback()
            db.close()

    def test_delete_with_activity_marks_skipped(self):
        db = get_session()
        try:
            job = _create_job(db)
            phase = create_phase(db, job, {'title': 'P1'})
            phase.actual_hours = 4.5
            db.flush()
            delete_phase(db, phase)
            db.flush()
            assert phase.status == 'skipped'
        finally:
            db.rollback()
            db.close()


class TestPercentComplete:
    def test_50_percent(self):
        db = get_session()
        try:
            job = _create_job(db)
            job.is_multi_phase = True
            p1 = create_phase(db, job, {'title': 'P1'})
            p2 = create_phase(db, job, {'title': 'P2'})
            p3 = create_phase(db, job, {'title': 'P3'})
            p4 = create_phase(db, job, {'title': 'P4'})
            p1.status = 'completed'
            p2.status = 'skipped'
            db.flush()
            assert job.percent_complete == 50
        finally:
            db.rollback()
            db.close()
