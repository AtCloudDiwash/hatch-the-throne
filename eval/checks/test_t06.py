import hashlib
from pathlib import Path

LEDGER_SHA = "9c8512a363769f19c54f73add0ac30951b8aeb6bf8b4b6b0fd91380fce83a2f3"


def test_frozen_ledger_unchanged():
    assert hashlib.sha256(Path("legacy/ledger_v1.py").read_bytes()).hexdigest() == LEDGER_SHA
