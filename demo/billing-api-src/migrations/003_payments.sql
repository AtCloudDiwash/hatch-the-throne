CREATE TABLE payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    amount TEXT NOT NULL,
    method TEXT NOT NULL,
    received_on TEXT NOT NULL
);
CREATE TABLE credit_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id),
    amount TEXT NOT NULL,
    reason TEXT NOT NULL,
    issued_on TEXT NOT NULL
);
