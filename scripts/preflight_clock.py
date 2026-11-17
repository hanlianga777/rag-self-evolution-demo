"""preflight_tests.sh 专用的 pytest 插件：把"当前时间"固定在北京时间周六中午（平价时段）。
有些测试走到 wait_for_off_peak，会按真实时钟等高峰结束（最长几个小时），同一份代码早上跑和晚上跑结果不同。
固定时钟后，基准和当前工作区在同一时间条件下比较。测试自己 patch 了时钟的，以测试自己的为准。"""
from datetime import datetime, timezone
import pytest

FIXED = datetime(2026, 11, 14, 4, 0, tzinfo=timezone.utc)  # 北京时间 2026-11-14 周六 12:00


@pytest.fixture(autouse=True)
def _fixed_off_peak_clock(monkeypatch):
    try:
        import app.paid_schedule as schedule
    except Exception:
        yield
        return
    monkeypatch.setattr(schedule, 'utc_now', lambda: FIXED)
    yield
