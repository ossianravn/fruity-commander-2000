"""Reuse identical schemas only during the server's single-threaded construction.

The pinned MCP SDK regenerates shared result schemas for each tool registration.
Its generators are single-use, so cache their completed dictionaries instead.
Never retain this override or its cache while serving requests.
"""

from contextlib import contextmanager
from copy import deepcopy
from functools import wraps

from pydantic import BaseModel


@contextmanager
def reuse_startup_schemas():
    original = BaseModel.__dict__["model_json_schema"]
    cache = {}

    @wraps(original.__func__)
    def schema(model, *args, **kwargs):
        key = (model, args, tuple(sorted(kwargs.items())))
        core = model.__pydantic_core_schema__
        previous = cache.get(key)
        if previous is not None and previous[0] is core:
            return deepcopy(previous[1])
        result = original.__func__(model, *args, **kwargs)
        cache[key] = (core, deepcopy(result))
        return result

    BaseModel.model_json_schema = classmethod(schema)
    try:
        yield
    finally:
        BaseModel.model_json_schema = original
        cache.clear()
