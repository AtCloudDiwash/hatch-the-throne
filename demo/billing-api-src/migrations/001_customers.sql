CREATE TABLE customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    tier TEXT NOT NULL DEFAULT 'standard',
    region TEXT NOT NULL DEFAULT 'NONE',
    payment_terms_days INTEGER NOT NULL DEFAULT 30,
    created_on TEXT NOT NULL
);
