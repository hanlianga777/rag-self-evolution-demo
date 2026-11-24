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


# These suites construct pre-E4 experiments from one-question or synthetic
# Baselines to exercise legacy execution, recovery, and read contracts.
# The E4 acceptance suite uses the production launch and all three saved samples.
LEGACY_LAUNCH_MODULES = frozenset({
    'test_agent_http_error', 'test_agent_response_recovery', 'test_api',
    'test_candidate_resume', 'test_cycle_manual_control', 'test_evaluation_context',
    'test_evaluation_stop', 'test_final_governance', 'test_governance',
    'test_manual_sandbox_resume', 'test_optimization_contract', 'test_page_performance',
    'test_sandbox_failure_contract', 'test_sandbox_inheritance', 'test_sandbox_stability',
    'test_task008b_agent_input', 'test_task010b_low_baseline', 'test_task013_cycle_recovery', 'test_task016a_agent',
    'test_task016a_schedule', 'test_task019a_cycle', 'test_task019a_reset',
    'test_task020b_composite', 'test_task021a_composite', 'test_task021h_composite',
    'test_task021j_import', 'test_task031d', 'test_task031e', 'test_task031f',
    'test_task031g', 'test_task032j_reads', 'test_task033c_reuse', 'test_task038_rulebook',
    'test_task109c_decision_contract', 'test_task113b_mechanism', 'test_task113c_contract',
    'test_v11_closure', 'test_v12_tuning', 'test_v14_final_fix', 'test_v14_identity',
})


@pytest.fixture
def legacy_launch(monkeypatch):
    from app.governance import GovernanceStore

    monkeypatch.setattr(GovernanceStore, 'new_verdict_experiment', staticmethod(lambda *_: {}))


@pytest.fixture(autouse=True)
def legacy_experiment_fixtures(request):
    if request.path.stem in LEGACY_LAUNCH_MODULES:
        request.getfixturevalue('legacy_launch')
