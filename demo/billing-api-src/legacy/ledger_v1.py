"""General ledger, v1. Posted amounts are read by the external audit export."""
from decimal import Decimal

ACCOUNTS = ("receivables", "revenue", "late_fees", "tax_payable", "credits", "cash")


def post_entry(conn, account, amount, memo, posted_on, legacy_ref=None):
    if account not in ACCOUNTS:
        raise ValueError("unknown account " + account)
    conn.execute("INSERT INTO ledger_entries(account, amount, memo, posted_on, legacy_ref) VALUES (?,?,?,?,?)",
                 (account, str(Decimal(str(amount))), memo, str(posted_on), legacy_ref))


def account_balance(conn, account):
    total = Decimal("0")
    for row in conn.execute("SELECT amount FROM ledger_entries WHERE account = ?", (account,)):
        total += Decimal(row["amount"])
    return total


def trial_balance(conn):
    return {account: account_balance(conn, account) for account in ACCOUNTS}
