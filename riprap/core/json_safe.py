"""JSON-safe coercion — strip numpy types, datacasses, datetimes out of values
so they can be serialized by stdlib `json`.

Used by:
  - python_call pebble adapter (so legacy probes returning numpy dataclasses
    produce clean dicts)
  - web/main.py endpoints (defensive — until every probe is pebble-driven,
    state can still contain raw numpy values from un-ported FSM steps)
"""
from __future__ import annotations

from typing import Any


def to_json_safe(value: Any) -> Any:
    """Recursively coerce a value to JSON-safe forms.

    Handles: dataclasses (unwrap), numpy scalars (.item()), numpy arrays
    (.tolist()), dicts / lists / tuples / sets (recurse), pandas / datetime
    Timestamps (.isoformat()). Pass-through for native JSON types and
    anything that isn't otherwise recognized.
    """
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if hasattr(value, "__dataclass_fields__"):
        return {k: to_json_safe(getattr(value, k))
                for k in value.__dataclass_fields__}
    if hasattr(value, "tolist"):           # numpy ndarray
        return to_json_safe(value.tolist())
    if hasattr(value, "item") and not isinstance(value, (list, dict, tuple, set)):
        try:
            return value.item()
        except (AttributeError, ValueError):
            pass
    if isinstance(value, dict):
        return {k: to_json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [to_json_safe(v) for v in value]
    if hasattr(value, "isoformat"):        # datetime / date / Timestamp
        return value.isoformat()
    return value
