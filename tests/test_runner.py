"""T5.1 to T5.5: behavioral diff runner, on a small guarded repo."""
import json
import socket
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import commit_all, run_script
from guardlib import baseline, config as cfgmod, ledger
from runner import diff as differ
from runner import inputs as input_lib
from runner import lg_codec

BASE = '''
import random
import socket
import sqlite3
import time
from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")
FACTOR = 2


def fee(balance: Decimal, rate: Decimal) -> Decimal:
    return (balance * rate).quantize(CENT, ROUND_HALF_UP)


def same(a: int) -> int:
    return a + 1


def clock():
    return time.time()


def dice(n: int = 1):
    return random.random() * n


def as_set(n: int):
    return {f"k{i}" for i in range(abs(n) % 5)}


def as_dict(n: int):
    return dict(reversed([(f"k{i}", i) for i in range(abs(n) % 5)]))


def net():
    socket.create_connection(("example.com", 80))
    return 1


def sock_raw():
    s = socket.socket()
    s.connect(("127.0.0.1", 9))
    return 2


def db_fn(n: int):
    return sqlite3.connect("x.db").execute("select 1").fetchall()


def writes(n: int):
    with open("out.txt", "w") as fh:
        fh.write("x")
    return n


def swallowed(n: int):
    try:
        sqlite3.connect("x.db")
    except Exception:
        return "fell back"
    return n


def raiser(n: int):
    if n < 0:
        raise ValueError("negative")
    return n


def uses_factor(n: int):
    return n * FACTOR


def always_raises(n: int):
    raise RuntimeError("no")


class Calc:
    def __init__(self):
        self.base = 10

    def plus(self, n: int):
        return self.base + n

    @staticmethod
    def stat(n: int):
        return n * 3

    @property
    def prop(self):
        return self.base


class NeedsArgs:
    def __init__(self, required):
        self.required = required

    def go(self, n: int):
        return n


def conn_fn(conn, n: int):
    return conn.execute("select 1")


def hang(n: int):
    while True:
        pass
'''


@pytest.fixture
def svc(repo):
    (repo / ".legacyguard/config.yaml").write_text(f"scope: .\npython: {sys.executable}\nbehavioral_diff:\n  max_inputs: 40\n  timeout_s: 60\n")
    (repo / "svc.py").write_text(BASE)
    commit_all(repo)
    r = run_script("session_start", {"cwd": str(repo), "session_id": "s", "source": "startup"})
    assert r.returncode == 0
    return repo


def run_diff(repo, new_source, names=None, harvest=None):
    cfg = cfgmod.load_config(str(repo))
    (repo / "svc.py").write_text(new_source)
    before = baseline.read_baseline(cfg, "svc.py")
    if names:
        from guardlib import symbols
        now = {s.qualname: s for s in symbols.extract(new_source)[0]}
        then = {s.qualname: s for s in symbols.extract(before)[0]}
        targets = [differ.Target("svc.py", q, now[q].kind, (then.get(q) or now[q]).params, symbols.sha(now[q].node_text)) for q in names]
    else:
        targets = differ.changed_targets("svc.py", before, new_source)
    return {r.qualname: r for r in differ.run(cfg, str(baseline.baseline_dir(cfg)), str(repo), targets, harvest=harvest or {})}


def test_unchanged_code_identical(svc):
    r = run_diff(svc, BASE, ["same", "fee"])
    assert r["same"].status == differ.DONE and r["fee"].status == differ.DONE and r["same"].inputs_compared > 5


def test_known_change_differs(svc):
    r = run_diff(svc, BASE.replace("return a + 1", "return a + 2"))
    assert r["same"].status == differ.DIFFERENT and r["same"].differences
    d = r["same"].differences[0]
    assert d["call"].startswith("same(a=") and "before" in d and d["before"] != d["after"]


def test_exception_difference(svc):
    r = run_diff(svc, BASE.replace('raise ValueError("negative")', 'raise TypeError("negative")'))
    assert r["raiser"].status == differ.DIFFERENT
    assert "ValueError" in r["raiser"].differences[0]["before"] and "TypeError" in r["raiser"].differences[0]["after"]


def test_exception_message_difference(svc):
    r = run_diff(svc, BASE.replace('raise ValueError("negative")', 'raise ValueError("below zero")'))
    assert r["raiser"].status == differ.DIFFERENT


def test_changed_constant_finds_functions_reading_it(svc):
    r = run_diff(svc, BASE.replace("FACTOR = 2", "FACTOR = 3"))
    assert r["uses_factor"].status == differ.DIFFERENT
    assert "same" not in r


def test_timeout_means_untested(svc):
    cfg_text = (svc / ".legacyguard/config.yaml").read_text().replace("timeout_s: 60", "timeout_s: 3")
    (svc / ".legacyguard/config.yaml").write_text(cfg_text)
    r = run_diff(svc, BASE, ["hang"])
    assert r["hang"].status == differ.UNTESTED and "timed out" in r["hang"].reason


# ---- T5.2 network ----

@pytest.mark.parametrize("fn", ["net", "sock_raw"])
def test_network_is_blocked_in_the_runner(svc, fn):
    r = run_diff(svc, BASE, [fn])
    assert r[fn].status == differ.UNTESTED and "network" in r[fn].reason


def test_worker_blocks_network_directly(tmp_path):
    code = ("import sys; sys.path.insert(0, %r); import lg_worker, socket; lg_worker.install_blocks()\n"
            "s = socket.socket()\n"
            "try:\n    s.connect(('127.0.0.1', 9))\nexcept lg_worker.GuardBlocked as e:\n    print('BLOCKED', e)\n" % str(Path(differ.WORKER).parent))
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert "BLOCKED network" in out.stdout


# ---- T5.3 input sources ----

def test_generated_inputs_from_hints_are_deterministic(svc):
    sym = {"qualname": "fee", "kind": "function", "params": [{"name": "balance", "annotation": "Decimal", "default": None}, {"name": "rate", "annotation": "Decimal", "default": None}]}
    cfg = cfgmod.load_config(str(svc))
    a, _ = input_lib.build(sym, None, 30, cfg.state_dir)
    b, _ = input_lib.build(sym, None, 30, cfg.state_dir)
    assert a == b and len(a) > 5 and a[0]["source"] == "generated"
    assert a[0]["args"][0]["value"]["t"] == "Decimal"
    assert not (svc / ".hypothesis").exists(), "the guard writes only under .legacyguard/"


def test_harvested_come_first_and_respect_max(svc):
    sym = {"qualname": "same", "kind": "function", "params": [{"name": "a", "annotation": "int", "default": None}]}
    h = {"inputs": [[{"name": "a", "kind": "pos", "value": {"t": "v", "v": n}}] for n in range(5)], "blocked": {}}
    items, _ = input_lib.build(sym, h, 8, cfgmod.load_config(str(svc)).state_dir)
    assert len(items) <= 8 and [i["source"] for i in items[:5]] == ["tests"] * 5 and items[-1]["source"] == "generated"


def test_harvested_counterexample_shows_first(svc):
    new = BASE.replace("return (balance * rate).quantize(CENT, ROUND_HALF_UP)", "return round(balance * rate, 2)")
    h = {"fee": None}
    harvest = {"svc.py::fee": {"blocked": {}, "inputs": [[{"name": "balance", "kind": "pos", "value": {"t": "Decimal", "v": "40.20"}},
                                                          {"name": "rate", "kind": "pos", "value": {"t": "Decimal", "v": "0.025"}}]]}}
    r = run_diff(svc, new, harvest=harvest)
    d = r["fee"].differences[0]
    assert d["call"] == 'fee(balance=Decimal("40.20"), rate=Decimal("0.025"))' and d["before"] == "1.01" and d["after"] == "1.00" and d["source"] == "tests"


def test_signature_we_cannot_build_is_untested(svc):
    r = differ.Target("svc.py", "custom", "function", [{"name": "x", "annotation": "SomeClass", "default": None}], "h")
    cfg = cfgmod.load_config(str(svc))
    out = differ.run(cfg, str(baseline.baseline_dir(cfg)), str(svc), [r], harvest={})
    assert out[0].status == differ.UNTESTED and "signature" in out[0].reason


def test_renamed_parameter_alone_is_not_a_difference(svc):
    r = run_diff(svc, BASE.replace("def same(a: int) -> int:\n    return a + 1", "def same(value: int) -> int:\n    return value + 1"))
    assert r["same"].status == differ.DONE


# ---- T5.4 self-diff ----

@pytest.mark.parametrize("fn", ["clock", "dice"])
def test_nondeterministic_function_gives_no_false_difference(svc, fn):
    r = run_diff(svc, BASE, [fn])
    assert r[fn].status == differ.UNTESTED and "non-deterministic" in r[fn].reason and not r[fn].differences


@pytest.mark.parametrize("fn", ["as_set", "as_dict"])
def test_ordering_gives_no_false_difference(svc, fn):
    r = run_diff(svc, BASE, [fn])
    assert r[fn].status == differ.DONE and not r[fn].differences


def test_changing_a_nondeterministic_function_still_no_false_alarm(svc):
    r = run_diff(svc, BASE.replace("return random.random() * n", "return random.random() * n  # note"))
    assert not r["dice"].differences


# ---- T5.5 untested ----

def test_db_function_untested_with_reason(svc):
    r = run_diff(svc, BASE, ["db_fn"])
    assert r["db_fn"].status == differ.UNTESTED and "database" in r["db_fn"].reason


def test_db_attempt_swallowed_by_target_is_still_untested(svc):
    r = run_diff(svc, BASE, ["swallowed"])
    assert r["swallowed"].status == differ.UNTESTED and "database" in r["swallowed"].reason


def test_conn_parameter_untested(svc):
    r = run_diff(svc, BASE, ["conn_fn"])
    assert r["conn_fn"].status == differ.UNTESTED and "conn" in r["conn_fn"].reason


def test_file_writes_blocked_and_untested(svc):
    r = run_diff(svc, BASE, ["writes"])
    assert r["writes"].status == differ.UNTESTED and "writes files" in r["writes"].reason
    assert not (svc / "out.txt").exists() and not (svc / ".legacyguard/baseline/out.txt").exists()


def test_every_input_raising_is_untested_not_verified(svc):
    r = run_diff(svc, BASE, ["always_raises"])
    assert r["always_raises"].status == differ.UNTESTED and "no input ran to completion" in r["always_raises"].reason


def test_class_needing_arguments_is_untested(svc):
    r = run_diff(svc, BASE, ["NeedsArgs.go"])
    assert r["NeedsArgs.go"].status == differ.UNTESTED


def test_methods_and_properties_run(svc):
    r = run_diff(svc, BASE, ["Calc.plus", "Calc.stat", "Calc.prop"])
    assert all(r[k].status == differ.DONE for k in ("Calc.plus", "Calc.stat", "Calc.prop"))
    r = run_diff(svc, BASE.replace("self.base = 10", "self.base = 11"), ["Calc.plus"])
    assert r["Calc.plus"].status == differ.DIFFERENT


def test_syntax_error_after_edit_is_a_confirmed_break(svc):
    r = run_diff(svc, BASE + "\ndef oops(:\n", ["same"])
    assert r["same"].status == differ.BROKEN


def test_new_function_has_no_baseline(svc):
    src = BASE + "\ndef brand_new(n: int):\n    return n\n"
    r = run_diff(svc, src, ["brand_new"])
    assert r["brand_new"].status == differ.UNTESTED and "no old version" in r["brand_new"].reason


def test_no_pycache_or_stray_files_in_the_repo(svc):
    run_diff(svc, BASE.replace("return a + 1", "return a + 2"))
    assert not list(svc.rglob("__pycache__"))
    assert not (svc / ".hypothesis").exists()


def test_secrets_are_not_passed_to_target_code(svc, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret")
    src = BASE + "\ndef read_env(n: int = 0):\n    import os\n    return os.environ.get('ANTHROPIC_API_KEY')\n"
    (svc / "svc.py").write_text(src)
    cfg = cfgmod.load_config(str(svc))
    t = differ.Target("svc.py", "read_env", "function", [{"name": "n", "annotation": "int", "default": "0"}], "h")
    res = differ._run_worker(cfg, sys.executable, str(svc), [str(svc)], [{"module": "svc", "qualname": "read_env", "inputs": [{"args": []}]}], 30)
    assert res["svc:read_env"]["results"][0]["value"] == {"t": "v", "v": None}


# ---- codec ----

@pytest.mark.parametrize("value", [None, True, 3, "x", 1.5, [1, "a"], (1, 2), {1, 2}, {"a": 1}, b"x", 10**30])
def test_codec_round_trip(value):
    assert lg_codec.decode(lg_codec.encode_input(value)) == value


def test_canon_scrubs_addresses_and_orders_sets():
    class O:
        pass
    assert lg_codec.canon({"b", "a"}) == lg_codec.canon({"a", "b"})
    assert "0x…" in lg_codec.canon(f"at {hex(id(O))}")["v"]
    assert lg_codec.canon({"a": 1, "b": 2}) == lg_codec.canon({"b": 2, "a": 1})


def test_module_for_walks_packages(tmp_path):
    (tmp_path / "src/pkg/sub").mkdir(parents=True)
    (tmp_path / "src/pkg/__init__.py").write_text("")
    (tmp_path / "src/pkg/sub/__init__.py").write_text("")
    (tmp_path / "src/pkg/sub/m.py").write_text("")
    (tmp_path / "top.py").write_text("")
    assert differ.module_for("src/pkg/sub/m.py", str(tmp_path)) == ("pkg.sub.m", "src")
    assert differ.module_for("top.py", str(tmp_path)) == ("top", "")
    assert differ.module_for("src/pkg/__init__.py", str(tmp_path)) == ("pkg", "src")


def test_migration_folder_per_app_is_checked():
    from guardlib import checks
    cfg = type("C", (), {"contract_path": lambda self, k: None})()
    out = checks.run_checks(cfg, "src/app/migrations/0002.py", "", "migrations.RemoveField(model_name='x', name='price')", None)
    assert out and out[0].kind == "db"


def test_library_subclassing_popen_still_imports(svc):
    src = BASE + "\nimport subprocess\nclass P(subprocess.Popen):\n    pass\n\ndef uses_sub(n: int = 1):\n    subprocess.Popen(['ls'])\n    return n\n"
    (svc / "svc.py").write_text(src)
    commit_all(svc, "add subprocess user")
    assert run_script("session_start", {"cwd": str(svc), "session_id": "s2", "source": "startup"}).returncode == 0
    r = run_diff(svc, src, ["same", "uses_sub"])
    assert r["same"].status == differ.DONE
    assert r["uses_sub"].status == differ.UNTESTED and "subprocess" in r["uses_sub"].reason


def test_guessed_inputs_that_old_code_rejects_are_not_evidence(svc):
    base = "def h(request):\n    return request.user\n\ndef typed(n: int):\n    if n < 0:\n        raise ValueError('neg')\n    return n\n"
    (svc / "svc.py").write_text(base)
    commit_all(svc, "h")
    assert run_script("session_start", {"cwd": str(svc), "session_id": "s3", "source": "startup"}).returncode == 0
    r = run_diff(svc, "def h(request):\n    return request.user.name\n\ndef typed(n: int):\n    if n < 0:\n        raise ValueError('negative')\n    return n\n", ["h", "typed"])
    assert r["h"].status == differ.UNTESTED and r["h"].dropped_invalid > 0 and not r["h"].differences
    assert r["typed"].status == differ.DIFFERENT, "a typed parameter says the input was valid, so its exception still counts"


def test_guessed_input_that_only_new_code_accepts_still_counts(svc):
    base = "def h(x):\n    return x.real\n"
    (svc / "svc.py").write_text(base)
    commit_all(svc, "h")
    assert run_script("session_start", {"cwd": str(svc), "session_id": "s3", "source": "startup"}).returncode == 0
    r = run_diff(svc, "def h(x):\n    return getattr(x, 'real', None)\n", ["h"])
    assert r["h"].status == differ.DIFFERENT


def test_guessed_input_that_old_code_accepts_still_counts(svc):
    base = "def h(x):\n    return str(x)\n"
    (svc / "svc.py").write_text(base)
    commit_all(svc, "h")
    assert run_script("session_start", {"cwd": str(svc), "session_id": "s3", "source": "startup"}).returncode == 0
    r = run_diff(svc, "def h(x):\n    return str(x) + '!'\n", ["h"])
    assert r["h"].status == differ.DIFFERENT


def test_missing_dependency_is_reported_as_that_not_as_a_new_function(svc):
    """Found on Zulip: a module importing a library that is not installed was reported as 'new function'."""
    src = "import a_library_that_is_not_installed\n\ndef g(n: int):\n    return n\n"
    (svc / "dep.py").write_text(src)
    commit_all(svc, "dep")
    assert run_script("session_start", {"cwd": str(svc), "session_id": "s4", "source": "startup"}).returncode == 0
    cfg = cfgmod.load_config(str(svc))
    (svc / "dep.py").write_text(src.replace("return n", "return n + 1"))
    t = differ.Target("dep.py", "g", "function", [{"name": "n", "annotation": "int", "default": None}], "h")
    r = differ.run(cfg, str(baseline.baseline_dir(cfg)), str(svc), [t], harvest={})[0]
    assert r.status == differ.UNTESTED
    assert "could not run" in r.reason and "a_library_that_is_not_installed" in r.reason and "new function" not in r.reason


def test_a_module_that_does_not_exist_yet_is_still_a_new_function(svc):
    cfg = cfgmod.load_config(str(svc))
    (svc / "fresh.py").write_text("def g(n: int):\n    return n\n")
    t = differ.Target("fresh.py", "g", "function", [{"name": "n", "annotation": "int", "default": None}], "h")
    r = differ.run(cfg, str(baseline.baseline_dir(cfg)), str(svc), [t], harvest={})[0]
    assert r.status == differ.UNTESTED and "no old version" in r.reason


# ---- DL-087 scratch files: a temp-folder write is not a reason to refuse the whole check ----

SCRATCH_MOD = '''
import os
import tempfile

_dir = tempfile.mkdtemp()
with open(os.path.join(_dir, "secret"), "w") as fh:  # what a settings module does at import
    fh.write("x")


def scratch(n):
    with open(os.path.join(_dir, "note.txt"), "a") as fh:
        fh.write("x")
    return n


def in_repo(n):
    with open("out.txt", "w") as fh:
        fh.write("x")
    return n
'''


def _worker(tmp_path, root, names, protect=()):
    one = {"args": [{"name": "n", "kind": "pos", "value": {"t": "v", "v": 1}}], "has_self": False}
    req, res = tmp_path / "req.json", tmp_path / "res.json"
    req.write_text(json.dumps({"root": str(root), "sys_path": [str(root)], "protect": [str(p) for p in protect],
                               "functions": [{"module": "mod", "qualname": n, "inputs": [one]} for n in names]}))
    subprocess.run([sys.executable, differ.WORKER, str(req), str(res)], check=True, capture_output=True)
    return json.loads(res.read_text())


def test_temp_folder_writes_run_but_repo_writes_stay_blocked(tmp_path):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "mod.py").write_text(SCRATCH_MOD)
    out = _worker(tmp_path, root, ["scratch", "in_repo"])
    assert out["mod:scratch"]["status"] == "ran" and out["mod:scratch"]["results"][0]["outcome"] == "return"
    assert out["mod:in_repo"]["results"][0]["outcome"] == "blocked"
    assert not (root / "out.txt").exists()


def test_protected_folder_inside_temp_stays_blocked(tmp_path):
    root, other = tmp_path / "proj", tmp_path / "repo"
    root.mkdir()
    other.mkdir()
    (root / "mod.py").write_text("def leak(n):\n    open(%r, 'w').write('x')\n    return n\n" % str(other / "f.txt"))
    out = _worker(tmp_path, root, ["leak"], protect=[other])
    assert out["mod:leak"]["results"][0]["outcome"] == "blocked" and not (other / "f.txt").exists()


def test_parameter_with_unreadable_default_keeps_its_default(tmp_path):
    """DL-090: places_dict=settings.CURRENCY_PLACES got numbers and strings, which only proved that a number is not a table."""
    sym = {"qualname": "round_decimal", "kind": "function", "params": [
        {"name": "dec"}, {"name": "currency", "default": "None"}, {"name": "places_dict", "default": "settings.CURRENCY_PLACES"}]}
    items, reason = input_lib.build(sym, None, 30, tmp_path)
    assert reason is None and items
    assert all("places_dict" not in [a["name"] for a in i["args"]] for i in items)
    assert any("currency" in [a["name"] for a in i["args"]] for i in items)


OLD_PYTHON = "/usr/bin/python3"


def _is_older_than_3_10(path):
    try:
        r = subprocess.run([path, "-c", "import sys; print(int(sys.version_info < (3, 10)))"], capture_output=True, text=True, timeout=10)
        return r.stdout.strip() == "1"
    except OSError:
        return False


@pytest.mark.skipif(not _is_older_than_3_10(OLD_PYTHON), reason="needs a Python older than 3.10 on this machine")
def test_worker_runs_when_the_project_python_is_3_9(tmp_path):
    """DL-093: a project on Python 3.9 came out 'timed out' because finding the temp folder tripped the write block."""
    root = tmp_path / "proj"
    root.mkdir()
    (root / "mod.py").write_text("def twice(n):\n    return n * 2\n")
    one = {"args": [{"name": "n", "kind": "pos", "value": {"t": "v", "v": 4}}], "has_self": False}
    req, res = tmp_path / "req.json", tmp_path / "res.json"
    req.write_text(json.dumps({"root": str(root), "sys_path": [str(root)], "functions": [{"module": "mod", "qualname": "twice", "inputs": [one]}]}))
    r = subprocess.run([OLD_PYTHON, differ.WORKER, str(req), str(res)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert json.loads(res.read_text())["mod:twice"]["results"][0]["outcome"] == "return"


def test_worker_that_cannot_start_is_not_called_a_timeout(svc):
    """DL-093: the reason must say the check could not run, and why."""
    cfg = cfgmod.load_config(str(svc))
    assert differ._run_worker(cfg, sys.executable, str(svc), [], [], 20) == {}
    bad = differ._run_worker(cfg, str(svc / "no-such-python"), str(svc), [], [], 20)
    assert "could not start" in bad[differ.FAILED]
