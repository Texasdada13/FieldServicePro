"""Tests for Phase 20 Advanced Reports."""
import pytest
import sys
import os
from datetime import date, timedelta
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def test_clamp():
    from web.utils.performance_engine import _clamp
    assert _clamp(50) == 50
    assert _clamp(-10) == 0
    assert _clamp(150) == 100
    assert _clamp(0) == 0
    assert _clamp(100) == 100


def test_period_bounds_monthly():
    from web.utils.performance_engine import get_period_bounds
    s, e = get_period_bounds('monthly', date(2024, 3, 15))
    assert s == date(2024, 3, 1)
    assert e == date(2024, 3, 31)


def test_period_bounds_weekly():
    from web.utils.performance_engine import get_period_bounds
    s, e = get_period_bounds('weekly', date(2024, 3, 15))
    assert s.weekday() == 0
    assert e.weekday() == 6
    assert (e - s).days == 6


def test_period_bounds_quarterly():
    from web.utils.performance_engine import get_period_bounds
    s, e = get_period_bounds('quarterly', date(2024, 5, 15))
    assert s == date(2024, 4, 1)
    assert e == date(2024, 6, 30)


def test_previous_period():
    from web.utils.performance_engine import _get_previous_period
    ps, pe = _get_previous_period('monthly', date(2024, 3, 1))
    assert ps == date(2024, 2, 1)
    assert pe == date(2024, 2, 29)


def test_default_weights_sum():
    from web.utils.performance_engine import DEFAULT_WEIGHTS
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 0.001


def test_default_weights_positive():
    from web.utils.performance_engine import DEFAULT_WEIGHTS
    for k, v in DEFAULT_WEIGHTS.items():
        assert v > 0, f'{k} must be positive'


def test_score_completion_rate():
    from models.tech_performance import TechPerformanceScore
    s = TechPerformanceScore(jobs_completed=9, jobs_total=10)
    assert s.completion_rate == 90.0


def test_score_callback_rate():
    from models.tech_performance import TechPerformanceScore
    s = TechPerformanceScore(total_callbacks=2, jobs_completed=20)
    assert s.callback_rate == 10.0


def test_score_utilization_rate():
    from models.tech_performance import TechPerformanceScore
    s = TechPerformanceScore(billable_hours=32, total_hours=40)
    assert s.utilization_rate == 80.0


def test_score_zero_division():
    from models.tech_performance import TechPerformanceScore
    s = TechPerformanceScore(jobs_completed=0, jobs_total=0, total_callbacks=0, total_hours=0, billable_hours=0)
    assert s.completion_rate == 0
    assert s.callback_rate == 0
    assert s.utilization_rate == 0


def test_achievement_definitions():
    from models.tech_performance import ACHIEVEMENT_DEFINITIONS
    for atype, defn in ACHIEVEMENT_DEFINITIONS.items():
        assert 'name' in defn
        assert 'description' in defn
        assert 'icon' in defn


def test_achievement_types():
    from models.tech_performance import ACHIEVEMENT_DEFINITIONS
    expected = {'perfect_stars', 'zero_callbacks', 'revenue_king', 'iron_horse',
                'speed_demon', 'customer_favorite', 'most_improved', 'consistency_streak'}
    assert set(ACHIEVEMENT_DEFINITIONS.keys()) == expected


def test_working_days():
    from web.utils.capacity_engine import get_working_days
    s = date(2024, 3, 11)  # Monday
    e = date(2024, 3, 15)  # Friday
    assert len(get_working_days(s, e, [0, 1, 2, 3, 4])) == 5


def test_working_days_excludes_weekends():
    from web.utils.capacity_engine import get_working_days
    s = date(2024, 3, 11)  # Monday
    e = date(2024, 3, 17)  # Sunday
    assert len(get_working_days(s, e, [0, 1, 2, 3, 4])) == 5


def test_capacity_alerts_overbooked():
    from web.utils.capacity_engine import generate_capacity_alerts
    data = {
        'overbooked_count': 2, 'overbooked_techs': ['A', 'B'],
        'underutil_count': 0, 'underutil_techs': [],
        'overall_utilization': 110,
        'settings': {'overbook_threshold': 100, 'underutil_threshold': 50},
    }
    alerts = generate_capacity_alerts(None, 1, data)
    assert any('over-booked' in a['message'].lower() for a in alerts)


def test_capacity_alerts_low_util():
    from web.utils.capacity_engine import generate_capacity_alerts
    data = {
        'overbooked_count': 0, 'overbooked_techs': [],
        'underutil_count': 3, 'underutil_techs': ['X', 'Y', 'Z'],
        'overall_utilization': 20,
        'settings': {'overbook_threshold': 100, 'underutil_threshold': 50},
    }
    alerts = generate_capacity_alerts(None, 1, data)
    assert any('low bookings' in a['message'].lower() for a in alerts)


def test_capacity_no_alerts_healthy():
    from web.utils.capacity_engine import generate_capacity_alerts
    data = {
        'overbooked_count': 0, 'overbooked_techs': [],
        'underutil_count': 0, 'underutil_techs': [],
        'overall_utilization': 75,
        'settings': {'overbook_threshold': 100, 'underutil_threshold': 50},
    }
    alerts = generate_capacity_alerts(None, 1, data)
    danger = [a for a in alerts if a['level'] == 'danger']
    assert len(danger) == 0


def test_pipeline_stages():
    from web.utils.pipeline_engine import PIPELINE_STAGES
    keys = [s[0] for s in PIPELINE_STAGES]
    assert 'draft' in keys
    assert 'sent' in keys
    assert 'approved' in keys
    assert 'converted' in keys
    for _, _, prob in PIPELINE_STAGES:
        assert 0 <= prob <= 1


def test_blueprints_registered():
    from web.app import app
    assert 'advanced_reports' in app.blueprints


def test_routes_exist():
    from web.app import app
    rules = [r.rule for r in app.url_map.iter_rules()]
    assert '/reports/tech-leaderboard' in rules
    assert '/reports/sales-pipeline-dashboard' in rules
    assert '/reports/capacity-planner' in rules


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
