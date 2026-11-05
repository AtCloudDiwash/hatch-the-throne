"""Customer records."""
import datetime as dt


class CustomerNotFound(Exception):
    pass


class DuplicateEmail(Exception):
    pass


TIERS = ("standard", "plus", "premier", "government")


def create_customer(conn, name, email, tier="standard", region="NONE", payment_terms_days=30, created_on=None):
    if tier not in TIERS:
        raise ValueError(f"unknown tier {tier}")
    if conn.execute("SELECT 1 FROM customers WHERE email = ?", (email,)).fetchone():
        raise DuplicateEmail(email)
    cur = conn.execute(
        "INSERT INTO customers(name, email, tier, region, payment_terms_days, created_on) VALUES (?,?,?,?,?,?)",
        (name, email, tier, region, payment_terms_days, str(created_on or dt.date.today())),
    )
    conn.commit()
    return get_customer(conn, cur.lastrowid)


def get_customer(conn, customer_id):
    row = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,)).fetchone()
    if row is None:
        raise CustomerNotFound(customer_id)
    return dict(row)


def list_customers(conn, tier=None):
    if tier:
        rows = conn.execute("SELECT * FROM customers WHERE tier = ? ORDER BY id", (tier,))
    else:
        rows = conn.execute("SELECT * FROM customers ORDER BY id")
    return [dict(r) for r in rows]


def update_terms(conn, customer_id, payment_terms_days):
    if payment_terms_days < 0 or payment_terms_days > 120:
        raise ValueError("payment terms must be between 0 and 120 days")
    get_customer(conn, customer_id)
    conn.execute("UPDATE customers SET payment_terms_days = ? WHERE id = ?", (payment_terms_days, customer_id))
    conn.commit()
    return get_customer(conn, customer_id)
