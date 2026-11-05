CREATE TABLE invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL REFERENCES customers(id),
    number TEXT NOT NULL UNIQUE,
    issue_date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    subtotal TEXT NOT NULL,
    discount TEXT NOT NULL DEFAULT '0.00',
    tax TEXT NOT NULL DEFAULT '0.00',
    late_fee TEXT NOT NULL DEFAULT '0.00',
    paid TEXT NOT NULL DEFAULT '0.00',
    currency TEXT NOT NULL DEFAULT 'USD',
    status TEXT NOT NULL DEFAULT 'open'
);
CREATE TABLE invoice_lines (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    description TEXT NOT NULL,
    quantity INTEGER NOT NULL,
    unit_price TEXT NOT NULL
);
