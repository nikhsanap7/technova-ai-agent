from backend.database import get_connection

SCHEMA = """
DROP TABLE IF EXISTS invoices;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS customers;

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    company     TEXT NOT NULL,
    country     TEXT NOT NULL,
    status      TEXT NOT NULL CHECK (status IN ('Active', 'Inactive'))
);

CREATE TABLE products (
    name  TEXT PRIMARY KEY,
    stock INTEGER NOT NULL CHECK (stock >= 0),
    price REAL NOT NULL
);

CREATE TABLE orders (
    order_id    INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    product     TEXT NOT NULL REFERENCES products(name),
    amount      REAL NOT NULL,
    status      TEXT NOT NULL
        CHECK (status IN ('Pending', 'Processing', 'Delivered', 'Cancelled'))
);

CREATE TABLE invoices (
    invoice_id     INTEGER PRIMARY KEY,
    customer_id    INTEGER NOT NULL REFERENCES customers(customer_id),
    amount         REAL NOT NULL,
    payment_status TEXT NOT NULL CHECK (payment_status IN ('Paid', 'Unpaid'))
);
"""

CUSTOMERS = [
    (1025, "ABC Technologies GmbH", "Germany", "Active"),
    (1026, "Global Solutions Ltd", "UK", "Active"),
    (1027, "TechVision GmbH", "Germany", "Active"),
    (1028, "Future Systems Inc", "USA", "Inactive"),
]

# Keyboard is needed because order 5004 uses it. Webcam is added so that
# the "low inventory" query returns more than one product.
PRODUCTS = [
    ("Laptop", 15, 1250),
    ("Monitor", 30, 400),
    ("Server", 5, 7500),
    ("Keyboard", 50, 75),
    ("Webcam", 8, 90),
]

ORDERS = [
    (5001, 1025, "Laptop", 2500, "Pending"),
    (5002, 1026, "Monitor", 800, "Delivered"),
    (5003, 1027, "Server", 7500, "Pending"),
    (5004, 1025, "Keyboard", 150, "Processing"),
    (5005, 1028, "Laptop", 2200, "Pending"),
]

INVOICES = [
    (7001, 1025, 2500, "Unpaid"),
    (7002, 1026, 800, "Paid"),
    (7003, 1027, 7500, "Unpaid"),
]


def seed() -> None:
    conn = get_connection()
    conn.executescript(SCHEMA)
    conn.executemany("INSERT INTO customers VALUES (?, ?, ?, ?)", CUSTOMERS)
    conn.executemany("INSERT INTO products VALUES (?, ?, ?)", PRODUCTS)
    conn.executemany("INSERT INTO orders VALUES (?, ?, ?, ?, ?)", ORDERS)
    conn.executemany("INSERT INTO invoices VALUES (?, ?, ?, ?)", INVOICES)
    conn.commit()

    # Quick self-check: print row counts and the pending German orders
    for table in ("customers", "products", "orders", "invoices"):
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"{table}: {count} rows")

    rows = conn.execute(
        """
        SELECT o.order_id, c.company, o.product, o.status
        FROM orders o JOIN customers c ON o.customer_id = c.customer_id
        WHERE o.status = 'Pending' AND c.country = 'Germany'
        """
    ).fetchall()
    print("\nPending orders from German customers:")
    for r in rows:
        print(" ", dict(r))

    conn.close()


if __name__ == "__main__":
    seed()