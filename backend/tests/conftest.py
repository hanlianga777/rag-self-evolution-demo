"""Bound offline tests and keep them independent of the billing window."""
from datetime import datetime, timezone
import signal

import pytest


class OfflineTestTimeout(KeyboardInterrupt):
    """Unwind unittest subtests before reporting a pytest failure."""


@pytest.hookimpl(wrapper=True)
def pytest_runtest_call(item):
    if not hasattr(signal, 'SIGALRM'):
        return (yield)

    def timeout(signum, frame):
        raise OfflineTestTimeout

    previous = signal.signal(signal.SIGALRM, timeout)
    signal.setitimer(signal.ITIMER_REAL, 60)
    try:
        return (yield)
    except OfflineTestTimeout:
        pytest.fail(f'Offline test exceeded 60 seconds: {item.nodeid}')
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


@pytest.fixture(autouse=True)
def off_peak_clock(monkeypatch):
    from app import paid_schedule

    # Tests of the schedule itself provide their own clock or pass an explicit timestamp.
    off_peak = datetime(2026, 11, 7, 12, tzinfo=timezone.utc)
    monkeypatch.setattr(paid_schedule, 'utc_now', lambda: off_peak)
