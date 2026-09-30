"""Actual execution spans and provider usage; historical rows remain untouched."""
import json
import math
import hashlib
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

_usage = ContextVar('rag_usage', default=None)

@contextmanager
def measure(stages, name, parent=None):
    start = datetime.now(timezone.utc).isoformat()
    tick = time.perf_counter()
    try:
        yield
    finally:
        if stages is not None:
            stages.append({'stage_name': name, 'start_time': start, 'end_time': datetime.now(timezone.utc).isoformat(), 'duration_ms': round((time.perf_counter() - tick) * 1000, 3), 'parent': parent})

@contextmanager
def collect_usage():
    calls = []
    token = _usage.set(calls)
    try:
        yield calls
    finally:
        _usage.reset(token)

def record_usage(usage):
    calls = _usage.get()
    if calls is not None:
        calls.append(dict(usage))

def price_config():
    path = Path(os.getenv('RAG_PRICE_CONFIG') or Path(__file__).resolve().parents[1] / 'config' / 'deepseek-prices.json')
    try:
        prices = json.loads(path.read_text())
        prices.setdefault('source_url', prices.get('source'))
        prices.setdefault('billing_mode', prices.get('cache_billing'))
        prices.setdefault('unit', 1_000_000)
        prices.setdefault('price_config_version', 'legacy-' + hashlib.sha256(path.read_bytes()).hexdigest()[:16])
        prices.setdefault('cost_config_version', prices['price_config_version'])
        if prices['billing_mode'] not in ('provider_hit_counter', 'uniform_input'):
            return None
        rates = [prices] if 'periods' not in prices else list(prices['periods'].values())
        if 'periods' in prices:
            windows, weekdays = prices.get('peak_hours_utc'), prices.get('peak_weekdays')
            if set(prices['periods']) != {'peak', 'off_peak'} or not isinstance(windows, list) or not windows or not isinstance(weekdays, list) or not weekdays:
                return None
            if any(type(day) is not int or not 0 <= day <= 6 for day in weekdays) or any(not isinstance(window, list) or len(window) != 2 or any(type(hour) is not int for hour in window) or not 0 <= window[0] < window[1] <= 24 for window in windows):
                return None
        if not all(prices.get(key) for key in ('model', 'currency', 'source_url', 'effective_date', 'billing_mode')):
            return None
        if type(prices['unit']) not in (int, float) or not math.isfinite(prices['unit']) or prices['unit'] <= 0:
            return None
        if not rates or not all(type(rate.get(key)) in (int, float) and math.isfinite(rate[key]) and rate[key] >= 0 for rate in rates for key in ('input_per_million', 'cached_input_per_million', 'output_per_million')):
            return None
        return prices
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def cost_report(model, calls):
    """Freeze the pricing basis, including explicit reasons when an estimate is unavailable."""
    prices = price_config()
    report = {'status': 'unavailable', 'amount': None, 'reason': None, 'requested_model': model,
              'cost_config_version': prices.get('cost_config_version') if prices else None,
              'price_snapshot': prices, 'calculated_at': datetime.now(timezone.utc).isoformat()}
    def unavailable(reason):
        return {**report, 'reason': reason}
    if prices is None:
        return unavailable('price_unavailable')
    if model not in [prices['model'], *prices.get('aliases', [])]:
        return unavailable('model_mismatch')
    if not calls:
        return unavailable('usage_missing')
    total, per_call = 0, []
    for usage in calls:
        if usage.get('requested_model', model) != model:
            return unavailable('model_mismatch')
        rate, period = prices, 'fixed'
        if 'periods' in prices:
            try:
                timestamp = datetime.fromisoformat(usage['call_started_at'].replace('Z', '+00:00'))
                if timestamp.tzinfo is None:
                    raise ValueError('timezone required')
                timestamp = timestamp.astimezone(timezone.utc)
            except (KeyError, ValueError, TypeError, AttributeError):
                return unavailable('call_timestamp_missing')
            in_peak_window = timestamp.weekday() in prices['peak_weekdays'] and any(start <= timestamp.hour < end for start, end in prices['peak_hours_utc'])
            if in_peak_window:
                calendar = prices.get('verified_holiday_calendar', {})
                local_date = timestamp.astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()
                if not calendar.get('source_url') or not calendar.get('checked_at') or type(calendar.get('dates', {}).get(local_date)) is not bool:
                    return unavailable('billing_period_ambiguous')
                period = 'off_peak' if calendar['dates'][local_date] else 'peak'
            else:
                period = 'off_peak'
            rate = prices['periods'][period]
        prompt, output = usage.get('prompt_tokens'), usage.get('completion_tokens')
        cached, missed = usage.get('prompt_cache_hit_tokens'), usage.get('prompt_cache_miss_tokens')
        if prompt is None and type(cached) is int and type(missed) is int:
            prompt = cached + missed
        if not all(type(value) is int and value >= 0 for value in (prompt, output)):
            return unavailable('usage_missing_or_invalid')
        uniform = prices['billing_mode'] == 'uniform_input' or rate['input_per_million'] == rate['cached_input_per_million']
        if cached is None and missed is not None and type(missed) is int:
            cached = prompt - missed
        if cached is None and uniform:
            cached = 0
        if type(cached) is not int or not 0 <= cached <= prompt:
            return unavailable('cache_usage_missing_or_invalid')
        if missed is not None and (type(missed) is not int or missed < 0 or missed + cached != prompt):
            return unavailable('cache_usage_inconsistent')
        amount = ((prompt - cached) * rate['input_per_million'] + cached * (rate['input_per_million'] if prices['billing_mode'] == 'uniform_input' else rate['cached_input_per_million']) + output * rate['output_per_million']) / prices['unit']
        total += amount
        per_call.append({'call_started_at': usage.get('call_started_at'), 'billing_period': period, 'amount': amount, 'rates': rate})
    return {**prices, **report, 'status': 'estimated', 'amount': round(total, 8), 'calls': per_call}


def estimate_cost(model, calls):
    # Compatibility for historical callers expecting None, never recompute stored rows.
    report = cost_report(model, calls)
    return report if report['status'] == 'estimated' else None


def cost_fields(model, calls):
    report = cost_report(model, calls)
    return {'cost_estimation': report, 'estimated_cost': report if report['status'] == 'estimated' else None}
