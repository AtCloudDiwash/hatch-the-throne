"""T3.1, T3.5: names table and incremental re-index."""
import json

from conftest import commit_all
from guardlib import symbols
from indexer import db, names

SRC = '''
import functools

def top(a, b=1):
    return helper(a) + other.helper2(b)

def helper(x):
    return x

@functools.lru_cache
def cached(n: int) -> int:
    def nested(m):
        return top(m)
    return nested(n)

class Svc:
    def run(self, x):
        return self.step(x)

    @staticmethod
    def step(y):
        return top(y)
'''


def test_extract_defs_and_decorators():
    defs, _ = symbols.extract(SRC)
    by = {d.qualname: d for d in defs}
    assert set(by) >= {"top", "helper", "cached", "cached.nested", "Svc", "Svc.run", "Svc.step"}
    assert by["top"].kind == "function" and by["Svc.run"].kind == "method" and by["Svc"].kind == "class"
    assert by["cached"].decorators == ["functools.lru_cache"]
    assert by["Svc.step"].decorators == ["staticmethod"]
    assert by["cached"].params == [{"name": "n", "annotation": "int", "default": None}]
    assert by["top"].params[1] == {"name": "b", "annotation": None, "default": "1"}
    assert "def top(a, b=1)" in by["top"].signature


def test_extract_calls_with_attribute_and_caller():
    _, calls = symbols.extract(SRC)
    got = {(c.caller, c.called_name) for c in calls}
    assert ("top", "helper") in got and ("top", "helper2") in got
    assert ("cached.nested", "top") in got and ("Svc.run", "step") in got and ("Svc.step", "top") in got


def test_works_on_broken_code():
    defs, _ = symbols.extract("def ok(a):\n    return a\n\ndef broken(:\n")
    assert any(d.qualname == "ok" for d in defs)
    assert symbols.has_errors("def broken(:\n")


def test_same_named_functions_all_stored(repo):
    (repo / "a.py").write_text("def run():\n    pass\n")
    (repo / "b.py").write_text("def run():\n    pass\n")
    conn = db.connect(str(repo))
    names.update(conn, str(repo), ".")
    assert len(conn.execute("SELECT * FROM symbols WHERE name = 'run'").fetchall()) == 2


def test_incremental_touches_one_file(repo):
    (repo / "a.py").write_text("def a():\n    pass\n")
    (repo / "b.py").write_text("def b():\n    pass\n")
    conn = db.connect(str(repo))
    assert names.update(conn, str(repo), ".")["parsed"] == 3
    assert names.update(conn, str(repo), ".")["parsed"] == 0
    (repo / "a.py").write_text("def a2():\n    pass\n")
    r = names.update(conn, str(repo), ".")
    assert r["parsed"] == 1 and r["removed"] == 0
    assert conn.execute("SELECT COUNT(*) FROM symbols WHERE name='a2'").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM symbols WHERE name='a'").fetchone()[0] == 0
    (repo / "b.py").unlink()
    assert names.update(conn, str(repo), ".")["removed"] == 1


def test_scope_limits_files(repo):
    (repo / "sub").mkdir()
    (repo / "sub" / "x.py").write_text("def x():\n    pass\n")
    assert names.list_python_files(str(repo), "sub/") == ["sub/x.py"]
