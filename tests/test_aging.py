"""tests/test_aging.py — Invoice aging bucket tests."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta


class FakeInvoice:
    """Minimal invoice-like object for testing aging logic."""
    def __init__(self, due_date):
        self.due_date = due_date

    @property
    def days_overdue(self):
        if not self.due_date:
            return 0
        return (date.today() - self.due_date).days

    @property
    def aging_bucket(self):
        d = self.days_overdue
        if d <= 0:
            return 'current'
        elif d <= 30:
            return '1_30'
        elif d <= 60:
            return '31_60'
        elif d <= 90:
            return '61_90'
        return '90_plus'


class TestAgingBuckets:
    def test_future_due_date_is_current(self):
        inv = FakeInvoice(date.today() + timedelta(days=10))
        assert inv.aging_bucket == 'current'

    def test_due_today_is_current(self):
        inv = FakeInvoice(date.today())
        assert inv.aging_bucket == 'current'

    def test_15_days_overdue_is_1_30(self):
        inv = FakeInvoice(date.today() - timedelta(days=15))
        assert inv.aging_bucket == '1_30'

    def test_30_days_overdue_is_1_30(self):
        inv = FakeInvoice(date.today() - timedelta(days=30))
        assert inv.aging_bucket == '1_30'

    def test_31_days_overdue_is_31_60(self):
        inv = FakeInvoice(date.today() - timedelta(days=31))
        assert inv.aging_bucket == '31_60'

    def test_45_days_overdue_is_31_60(self):
        inv = FakeInvoice(date.today() - timedelta(days=45))
        assert inv.aging_bucket == '31_60'

    def test_75_days_overdue_is_61_90(self):
        inv = FakeInvoice(date.today() - timedelta(days=75))
        assert inv.aging_bucket == '61_90'

    def test_100_days_overdue_is_90_plus(self):
        inv = FakeInvoice(date.today() - timedelta(days=100))
        assert inv.aging_bucket == '90_plus'

    def test_none_due_date_is_current(self):
        inv = FakeInvoice(None)
        assert inv.aging_bucket == 'current'


class TestPaymentTermsDueDate:
    """Test the payment terms due date calculation utility."""

    def test_net_30(self):
        from web.utils.payment_terms import calculate_due_date
        result = calculate_due_date(date(2025, 1, 1), 'net_30')
        assert result == date(2025, 1, 31)

    def test_due_on_receipt(self):
        from web.utils.payment_terms import calculate_due_date
        result = calculate_due_date(date(2025, 1, 1), 'due_on_receipt')
        assert result == date(2025, 1, 1)

    def test_net_45(self):
        from web.utils.payment_terms import calculate_due_date
        result = calculate_due_date(date(2025, 6, 1), 'net_45')
        assert result == date(2025, 7, 16)

    def test_custom_days(self):
        from web.utils.payment_terms import calculate_due_date
        result = calculate_due_date(date(2025, 3, 1), 'custom', custom_days=60)
        assert result == date(2025, 4, 30)

    def test_none_date_uses_today(self):
        from web.utils.payment_terms import calculate_due_date
        result = calculate_due_date(None, 'net_30')
        assert result == date.today() + timedelta(days=30)
