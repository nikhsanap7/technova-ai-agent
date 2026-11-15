import sqlite3
from pathlib import Path

# Path to the database file: <project root>/data/enterprise.db
DB_PATH = Path(__file__).resolve().parent.parent / "data" / "enterprise.db"


def get_connection() -> sqlite3.Connection:
    """Open a connection to the SQLite database.

    row_factory = sqlite3.Row lets us access columns by name,
    e.g. row["company"], instead of by position.
    """
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn