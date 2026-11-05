"""Invoice numbers: INV-<year>-<sequence>."""


def format_number(year, sequence):
    return f"INV-{year}-{sequence:05d}"


def parse_number(number):
    prefix, year, sequence = number.split("-")
    if prefix != "INV":
        raise ValueError(f"not an invoice number: {number}")
    return int(year), int(sequence)


def next_invoice_number(conn, year):
    row = conn.execute("SELECT number FROM invoices WHERE number LIKE ? ORDER BY number DESC LIMIT 1", (f"INV-{year}-%",)).fetchone()
    sequence = parse_number(row["number"])[1] + 1 if row else 1
    return format_number(year, sequence)
