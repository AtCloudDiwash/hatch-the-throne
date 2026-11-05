"""Inputs for the behavioral diff: harvested from real tests first, then Hypothesis from hints and defaults (FR-14 step 1)."""
from __future__ import annotations

import ast
import datetime as dt
import json
import os
import re
import warnings
from decimal import Decimal
from pathlib import Path

from runner import lg_codec

DB_PARAM_NAMES = {"conn", "connection", "cursor", "cur", "db", "session", "engine", "transaction", "tx"}
MAX_GENERATED = 150


def _hypothesis(state_dir: Path):
    os.environ.setdefault("HYPOTHESIS_STORAGE_DIRECTORY", str(Path(state_dir) / ".hypothesis"))
    import hypothesis
    from hypothesis import strategies as st
    return hypothesis, st


def _strategy_for(annotation: str | None, default: str | None, st):
    ann = (annotation or "").replace("typing.", "").replace("decimal.", "").replace("datetime.", "").replace(" ", "").strip("\"'")
    money = st.decimals(min_value=Decimal("-100000"), max_value=Decimal("100000"), places=2, allow_nan=False, allow_infinity=False)
    rate = st.decimals(min_value=Decimal("0"), max_value=Decimal("1"), places=3, allow_nan=False, allow_infinity=False)
    if ann:
        optional = False
        m = re.fullmatch(r"Optional\[(.+)\]", ann)
        if m:
            ann, optional = m.group(1), True
        if ann.endswith("|None") or ann.startswith("None|"):
            ann, optional = ann.replace("|None", "").replace("None|", ""), True
        base = None
        if ann == "Decimal":
            base = st.one_of(money, rate)
        elif ann == "int":
            base = st.integers(-1000, 1000)
        elif ann == "float":
            base = st.floats(-1e6, 1e6, allow_nan=False, allow_infinity=False)
        elif ann == "str":
            base = st.text("abcdefgh XYZ-_0123", max_size=12)
        elif ann == "bool":
            base = st.booleans()
        elif ann == "date":
            base = st.dates(dt.date(2000, 1, 1), dt.date(2040, 12, 31))
        elif ann == "datetime":
            base = st.datetimes(dt.datetime(2000, 1, 1), dt.datetime(2040, 12, 31))
        else:
            m = re.fullmatch(r"(?:list|List)\[(.+)\]", ann)
            if m:
                inner = _strategy_for(m.group(1), None, st)
                base = st.lists(inner, max_size=4) if inner is not None else None
            m = re.fullmatch(r"(?:dict|Dict)\[str,(.+)\]", ann)
            if m and base is None:
                inner = _strategy_for(m.group(1), None, st)
                base = st.dictionaries(st.text("abc", max_size=3), inner, max_size=3) if inner is not None else None
        if base is not None:
            return st.one_of(st.none(), base) if optional else base
    if default:
        m = re.fullmatch(r"""Decimal\(["']([^"']+)["']\)""", default)
        if m:
            return st.one_of(st.just(Decimal(m.group(1))), money)
        try:
            value = ast.literal_eval(default)
        except (ValueError, SyntaxError):
            value = "not-a-literal"
        if value is None:
            return st.one_of(st.none(), money, st.integers(-100, 100), st.text("abc", max_size=4))
        if isinstance(value, bool):
            return st.booleans()
        if isinstance(value, int):
            return st.integers(-1000, 1000)
        if isinstance(value, float):
            return st.floats(-1e6, 1e6, allow_nan=False, allow_infinity=False)
        if isinstance(value, str) and value != "not-a-literal":
            return st.one_of(st.just(value), st.text("abcdefgh", max_size=8))
    if ann:
        return None  # a type we cannot build
    return st.one_of(money, st.integers(-100, 100), st.text("abcxyz", max_size=4), st.none())


def _generated(sym, count: int, state_dir: Path) -> list[dict]:
    params = [p for p in sym["params"] if p["name"] not in ("self", "cls")]
    if any(p["name"].startswith("*") for p in params):
        params = [p for p in params if not p["name"].startswith("*")]
    if not params:
        return [{"args": [], "source": "generated"}]
    hypothesis, st = _hypothesis(state_dir)
    strategies = {}
    weak = False
    for p in params:
        if not p.get("annotation") and not p.get("default"):
            weak = True  # nothing says what this parameter accepts, so a value may simply be invalid
        strat = _strategy_for(p.get("annotation"), p.get("default"), st)
        if strat is None:
            if p.get("default") is not None:
                continue  # leave it to its default
            return []
        strategies[p["name"]] = strat
    if not strategies:
        return [{"args": [], "source": "generated"}]
    out: list[dict] = []
    seen: set[str] = set()

    @hypothesis.given(st.fixed_dictionaries(strategies))
    @hypothesis.settings(max_examples=count, database=None, derandomize=True, deadline=None, phases=[hypothesis.Phase.generate],
                         suppress_health_check=list(hypothesis.HealthCheck))
    def collect(values):
        args = []
        positional = True
        for p in params:
            if p["name"] in values:
                args.append({"name": p["name"], "kind": "pos" if positional else "kw", "value": lg_codec.encode_input(values[p["name"]])})
            else:
                positional = False
        sig = json.dumps(args, sort_keys=True)
        if sig not in seen:
            seen.add(sig)
            out.append({"args": args, "source": "generated", "weak": weak})

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            collect()
        except Exception:  # noqa: BLE001 - generation failure means harvested inputs only (TESTING.md §8)
            pass
    return out


def build(sym: dict, harvested: dict | None, max_inputs: int, state_dir: Path) -> tuple[list[dict], str | None]:
    """(inputs, reason it cannot be run). sym: {qualname, kind, params}."""
    names = [p["name"].lstrip("*") for p in sym["params"]]
    blocked = (harvested or {}).get("blocked", {})
    db_params = sorted(set(blocked) & DB_PARAM_NAMES) or sorted(set(names) & DB_PARAM_NAMES)
    if db_params:
        return [], f"needs a database connection (parameter {db_params[0]})"
    items = []
    for call in (harvested or {}).get("inputs", []):
        has_self = bool(call) and call[0]["name"] == "self"
        items.append({"args": call, "has_self": has_self, "source": "tests"})
    items = items[:max_inputs]
    remaining = min(max_inputs - len(items), MAX_GENERATED)
    if remaining > 0:
        items += _generated(sym, remaining, state_dir)
    return items, None
