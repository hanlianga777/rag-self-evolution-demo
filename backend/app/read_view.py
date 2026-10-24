"""Memoize pure presentation work only during one synchronous read response."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from functools import wraps
import json

_view = ContextVar('read_view', default=None)


@contextmanager
def read_view():
    token = _view.set({})
    try:yield
    finally:_view.reset(token)


def memoized_view(function):
    @wraps(function)
    def read(*args,**kwargs):
        cache = _view.get()
        if cache is None:return function(*args,**kwargs)
        key=(function.__module__,function.__qualname__,json.dumps([args,kwargs],sort_keys=True,ensure_ascii=False))
        if key not in cache:cache[key]=function(*args,**kwargs)
        return deepcopy(cache[key])
    return read
