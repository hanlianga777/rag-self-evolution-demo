"""Actual execution spans and provider usage; historical rows remain untouched."""
import json
import os
import time
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path

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
    path = os.getenv('RAG_PRICE_CONFIG')
    if not path:
        return None
    try:
        prices = json.loads(Path(path).read_text())
        if all(prices.get(key) for key in ('model', 'currency', 'source', 'effective_date', 'cache_billing')) and all(type(prices.get(key)) in (int, float) and prices[key] >= 0 for key in ('input_per_million', 'cached_input_per_million', 'output_per_million')):
            return prices
    except (OSError, ValueError, TypeError):
        pass
    return None

def estimate_cost(model, calls):
    prices = price_config()
    if not prices or prices['model'] != model or not calls:
        return None
    total = 0
    for usage in calls:
        # Cache-hit counters are mandatory: missing usage is never priced as zero.
        values = [usage.get(key) for key in ('prompt_tokens', 'completion_tokens', 'prompt_cache_hit_tokens')]
        if not all(type(value) is int and value >= 0 for value in values) or values[2] > values[0]:
            return None
        prompt, output, cached = values
        total += ((prompt-cached)*prices['input_per_million'] + cached*prices['cached_input_per_million'] + output*prices['output_per_million']) / 1_000_000
    return {'amount': round(total, 8), **prices, 'calculated_at': datetime.now(timezone.utc).isoformat()}
