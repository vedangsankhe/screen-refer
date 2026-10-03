"""Tiny rule language used by the form config AND the scoring rules.

A condition is one of:
  {"q": "age", "gte": 10}                     compare a value (ops: eq, neq, in, gt, gte, lt, lte)
  {"q": "age", "gte": 10, "lt": 55}           several ops on one value must all hold
  {"all": [cond, ...]}  {"any": [cond, ...]}  {"not": cond}
`q` is "age", "sex" or the id of an earlier question. The same logic exists in
frontend/src/app/core/visibility.ts; both are tested against tests/visibility_cases.json.
"""
from datetime import date

_OPS = {
    "eq": lambda v, x: v == x,
    "neq": lambda v, x: v is not None and v != x,   # an unanswered question is never "not equal"
    "in": lambda v, x: v in x,
    "gt": lambda v, x: v is not None and v > x,
    "gte": lambda v, x: v is not None and v >= x,
    "lt": lambda v, x: v is not None and v < x,
    "lte": lambda v, x: v is not None and v <= x,
}


def evaluate(cond, ctx: dict) -> bool:
    if not cond:
        return True
    if "all" in cond:
        return all(evaluate(c, ctx) for c in cond["all"])
    if "any" in cond:
        return any(evaluate(c, ctx) for c in cond["any"])
    if "not" in cond:
        return not evaluate(cond["not"], ctx)
    value = ctx.get(cond["q"])
    ops = [k for k in cond if k != "q"]
    if not ops:
        raise ValueError(f"Condition has no operator: {cond}")
    for op in ops:
        if op not in _OPS:
            raise ValueError(f"Unknown operator '{op}'")
    return all(_OPS[op](value, cond[op]) for op in ops)


def age_on(dob: date, on: date) -> int:
    return on.year - dob.year - ((on.month, on.day) < (dob.month, dob.day))
