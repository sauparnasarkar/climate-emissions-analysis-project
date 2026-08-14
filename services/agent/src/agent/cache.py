"""Thread-scoped tool-call cache key -- SPEC.md §9.

Sorting list-valued args before hashing matters: `["China","India"]` and `["India","China"]`
should hit the same key.
"""

import json


def cache_key(tool_name: str, args: dict) -> str:
    normalized = {k: sorted(v) if isinstance(v, list) else v for k, v in args.items()}
    return f"{tool_name}:{json.dumps(normalized, sort_keys=True)}"
