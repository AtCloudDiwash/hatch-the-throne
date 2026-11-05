"""Plant the bug the failing test exposes: the early-pay window is off by one."""
from pathlib import Path

path = Path("billing/discounts.py")
text = path.read_text()
assert "< window_days" in text
path.write_text(text.replace("< window_days", "<= window_days"))
