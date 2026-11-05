"""Behavioral diff (FR-14): the same inputs through old and new code, in separate processes, compared by execution."""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import subprocess
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

from guardlib import config as cfgmod
from guardlib import symbol_diff, symbols
from indexer.coverage_map import clean_env, load_harvest
from runner import inputs as input_lib
from runner import lg_codec

WORKER = Path(__file__).resolve().parent / "lg_worker.py"
MAX_FUNCTIONS = 12
MAX_SHOWN = 3
DONE, DIFFERENT, BROKEN, UNTESTED = "verified", "different", "broken", "untested"
BLOCK_REASON = {"database": "needs a database", "network": "needs the network", "file write": "writes files", "subprocess": "starts a subprocess"}


@dataclass
class Target:
    file: str
    qualname: str
    kind: str
    params: list[dict]
    code_hash: str


@dataclass
class Result:
    file: str
    qualname: str
    status: str
    code_hash: str
    reason: str = ""
    inputs_tried: int = 0
    inputs_compared: int = 0
    inputs_completed: int = 0
    dropped_nondeterministic: int = 0
    dropped_invalid: int = 0
    differences: list[dict] = field(default_factory=list)

    @property
    def subject(self) -> str:
        return f"{self.file}::{self.qualname}"


def module_for(rel: str, root: str) -> tuple[str, str]:
    """(dotted module, folder that must be on sys.path), found by walking up through __init__.py files."""
    parts = rel[:-3].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    i = len(rel.split("/")) - 1  # index of the file name
    pkg_start = i
    while pkg_start > 0 and (Path(root) / "/".join(rel.split("/")[:pkg_start]) / "__init__.py").exists():
        pkg_start -= 1
    module = ".".join(parts[pkg_start:])
    return module, "/".join(rel.split("/")[:pkg_start])


def changed_targets(rel: str, before: str | None, after: str | None) -> list[Target]:
    """Functions whose code changed, plus functions in the file that read a changed module-level constant."""
    if after is None or before is None:
        return []
    now = {s.qualname: s for s in symbols.extract(after)[0]}
    out: dict[str, Target] = {}
    for c in symbol_diff.diff(before, after):
        if c.kind in ("body_changed", "signature_changed") and c.after.kind != "class":
            old = c.before
            out[c.qualname] = Target(rel, c.qualname, c.after.kind, old.params, symbols.sha(c.after.node_text))
        elif c.kind in ("renamed", "visibility_changed") and c.before.kind != "class":
            pass  # the old name is gone; static checks report it, and callers show up at Stop
    changed_names = _changed_constants(before, after)
    if changed_names:
        for q, s in now.items():
            if s.kind == "class" or q in out:
                continue
            if _reads_any(s.node_text, changed_names):
                before_sym = next((b for b in symbols.extract(before)[0] if b.qualname == q), None)
                if before_sym is not None:
                    out[q] = Target(rel, q, s.kind, before_sym.params, symbols.sha(s.node_text + "|".join(sorted(changed_names))))
    return sorted(out.values(), key=lambda t: t.qualname)


def _module_assignments(source: str) -> dict[str, str]:
    out = {}
    for stmt in symbols.parse(source).root_node.children:
        if stmt.type == "expression_statement" and stmt.named_children and stmt.named_children[0].type == "assignment":
            left = stmt.named_children[0].child_by_field_name("left")
            if left is not None and left.type == "identifier":
                out[symbols.text(left)] = symbols.text(stmt)
    return out


def _changed_constants(before: str, after: str) -> set[str]:
    a, b = _module_assignments(before), _module_assignments(after)
    return {k for k in a.keys() & b.keys() if a[k] != b[k]}


def _reads_any(source: str, names: set[str]) -> bool:
    found = False

    def walk(node):
        nonlocal found
        if node.type == "identifier" and symbols.text(node) in names:
            found = True
        if not found:
            for c in node.children:
                walk(c)
    walk(symbols.parse(source).root_node)
    return found


def _run_worker(cfg, py: str, root: str, sys_path: list[str], functions: list[dict], timeout: float) -> dict | None:
    with tempfile.TemporaryDirectory(prefix="lgrun") as tmp:
        req, res = Path(tmp) / "req.json", Path(tmp) / "res.json"
        req.write_text(json.dumps({"root": root, "sys_path": sys_path, "functions": functions, "django_settings": cfg.raw.get("django_settings")}))
        env = clean_env(cfg)
        env.pop("PYTHONPATH", None)
        try:
            subprocess.run([py, "-B", str(WORKER), str(req), str(res)], cwd=root, env=env, capture_output=True, text=True, timeout=timeout)
        except (subprocess.TimeoutExpired, OSError):
            return None
        try:
            return json.loads(res.read_text())
        except (OSError, ValueError):
            return None


def _key(o: dict) -> str:
    return json.dumps(o, sort_keys=True)


def _comparable(o: dict) -> dict | None:
    """What gets compared for one input: return value, or exception type and message. None if not comparable."""
    if o["outcome"] == "return":
        return {"k": "return", "v": o["value"]}
    if o["outcome"] == "raise":
        return {"k": "raise", "type": o["type"], "message": o["message"]}
    return None


def _show_outcome(o: dict) -> str:
    return lg_codec.display(o["v"], plain_decimal=True) if o["k"] == "return" else f"raises {o['type']}: {o['message']}"


def show_call(target: Target, item: dict) -> str:
    name = target.qualname.rsplit(".", 1)[-1]
    parts = []
    for a in item["args"]:
        if a["name"] == "self":
            continue
        if a.get("kind") == "varargs":
            parts += [lg_codec.display(v) for v in a["value"]["v"]]
        elif a.get("kind") == "varkw":
            parts += [f"{lg_codec.display(k).strip(chr(39))}={lg_codec.display(v)}" for k, v in a["value"]["v"]]
        else:
            parts.append(f"{a['name']}={lg_codec.display(a['value'])}")
    return f"{name}({', '.join(parts)})"


def compare_one(target: Target, items: list[dict], a: dict | None, b: dict | None, n: dict | None, use_self_diff: bool) -> Result:
    r = Result(target.file, target.qualname, UNTESTED, target.code_hash, inputs_tried=len(items))
    if a is None or n is None or (use_self_diff and b is None):
        r.reason = "timed out"
        return r
    if n["status"] == "import_error" and a["status"] == "ran":
        r.status, r.reason = BROKEN, f"the module no longer imports after the edit: {n.get('reason')}"
        return r
    if a["status"] == "missing":
        r.reason = "new function, so there is no old version to compare"
        return r
    if n["status"] == "missing":
        r.reason = "the function no longer exists under this name"
        return r
    if a["status"] != "ran" or n["status"] != "ran":
        bad = a if a["status"] != "ran" else n
        r.reason = {"uncallable": "a nested function cannot be called directly", "import_blocked": f"importing the module {bad.get('reason')}"}.get(
            bad["status"], f"could not run: {bad.get('reason') or bad['status']}")
        return r
    blocked: set[str] = set()
    setup_failures = 0
    setup_detail = ""
    for item, oa, on, ob in zip(items, a["results"], n["results"], (b or {"results": a["results"]})["results"]):
        blocked.update(oa.get("blocked_kinds", []))
        blocked.update(on.get("blocked_kinds", []))
        if oa["outcome"] == "setup_failed" or on["outcome"] == "setup_failed":
            setup_failures += 1
            setup_detail = setup_detail or oa.get("detail") or on.get("detail") or ""
            continue
        ca, cn = _comparable(oa), _comparable(on)
        if ca is None or cn is None:
            continue
        if item.get("weak") and ca["k"] == "raise" and cn["k"] == "raise":
            # Both versions reject a guessed value: it was never a valid call, so two different rejections prove nothing.
            # If new code accepts what old code rejected, that is a real change and stays.
            r.dropped_invalid += 1
            continue
        if use_self_diff:
            cb = _comparable(ob)
            if cb is None or _key(ca) != _key(cb):
                r.dropped_nondeterministic += 1
                continue
        r.inputs_compared += 1
        if ca["k"] == "return":
            r.inputs_completed += 1
        if _key(ca) != _key(cn):
            r.differences.append({"call": show_call(target, item), "before": _show_outcome(ca), "after": _show_outcome(cn), "source": item["source"],
                                  "args": item["args"], "has_self": item.get("has_self", False), "before_raw": ca, "after_raw": cn})
    if r.differences:
        r.status = DIFFERENT
        r.differences.sort(key=lambda d: (d["source"] != "tests", len(d["call"])))
        return r
    if blocked:
        r.reason = " and ".join(sorted(BLOCK_REASON.get(k, k) for k in blocked))
        return r
    if r.dropped_nondeterministic and r.dropped_nondeterministic >= r.inputs_compared:
        # One input like dice(0) agreeing with itself must not turn a random function into a Verified pass.
        r.reason = f"non-deterministic: old code disagreed with itself on {r.dropped_nondeterministic} of {r.dropped_nondeterministic + r.inputs_compared} inputs"
        return r
    if r.inputs_completed == 0:
        r.reason = "no input ran to completion" if not setup_failures else f"inputs could not be set up ({setup_detail[:120]})"
        return r
    r.status = DONE
    return r


def run(cfg, baseline_root: str, work_root: str, targets: list[Target], harvest: dict | None = None) -> list[Result]:
    """Run old twice and new once, in parallel subprocesses, on the same inputs."""
    if harvest is None:
        harvest = load_harvest(cfg)
    bd = cfg.behavioral_diff
    py = cfgmod.target_python(cfg)
    results: dict[str, Result] = {}
    specs, runnable, shown = [], {}, []
    roots: set[str] = set()
    extra = cfg.raw.get("source_roots") or []
    for t in targets[:MAX_FUNCTIONS]:
        items, reason = input_lib.build({"qualname": t.qualname, "kind": t.kind, "params": t.params}, harvest.get(f"{t.file}::{t.qualname}"), int(bd["max_inputs"]), cfg.state_dir)
        if reason:
            results[t.qualname] = Result(t.file, t.qualname, UNTESTED, t.code_hash, reason=reason)
            continue
        if not items:
            results[t.qualname] = Result(t.file, t.qualname, UNTESTED, t.code_hash, reason="no inputs could be built for its signature")
            continue
        module, sys_rel = module_for(t.file, work_root)
        specs.append({"module": module, "qualname": t.qualname, "inputs": items})
        runnable[f"{module}:{t.qualname}"] = (t, items)
        roots.add(sys_rel)
    for t in targets[MAX_FUNCTIONS:]:
        results[t.qualname] = Result(t.file, t.qualname, UNTESTED, t.code_hash, reason=f"more than {MAX_FUNCTIONS} functions changed at once")
    if specs:
        def paths_for(base: str) -> list[str]:
            ordered = list(dict.fromkeys([*extra, *sorted(roots), ""]))
            return [str(Path(base) / p) if p else base for p in ordered]
        deadline = float(bd["timeout_s"])
        use_self = bool(bd.get("self_diff", True))
        with cf.ThreadPoolExecutor(3) as pool:
            fa = pool.submit(_run_worker, cfg, py, baseline_root, paths_for(baseline_root), specs, deadline)
            fn = pool.submit(_run_worker, cfg, py, work_root, paths_for(work_root), specs, deadline)
            fb = pool.submit(_run_worker, cfg, py, baseline_root, paths_for(baseline_root), specs, deadline) if use_self else None
            a, n = fa.result(), fn.result()
            b = fb.result() if fb else None
        for key, (t, items) in runnable.items():
            results[t.qualname] = compare_one(t, items, a.get(key) if a else None, b.get(key) if b else None, n.get(key) if n else None, use_self)
    return [results[t.qualname] for t in targets]


def format_wake(result: Result, finding_id: str) -> str:
    """The counterexample text Claude receives (FR-15). Factual, replayable, within the context limit."""
    total = result.inputs_compared
    lines = [f"LegacyGuard behavior difference [{finding_id}] in {result.subject}: {len(result.differences)} of {total} inputs differ between the session baseline and the current code."]
    for d in result.differences[:MAX_SHOWN]:
        lines.append(f"{d['call']}  before {d['before']}  after {d['after']}  [{d['source']}]")
    if result.reason:
        lines.append(f"Also: {result.reason}.")
    lines.append(f"Whether the request intended this is unknown. If it did not, revising the code clears this and the check re-runs by itself. "
                 f"If it did, say so in your reply; the developer can accept it with /legacyguard:waive {finding_id} \"<reason>\".")
    return "\n".join(lines)
