from typing import Optional

from fastapi import APIRouter, HTTPException

from backend.database import get_connection

router = APIRouter(prefix="/products", tags=["Products"])


@router.get("", summary="List products, optionally filtered by name or low stock")
def search_products(name: Optional[str] = None, stock_below: Optional[int] = None):
    """stock_below=10 returns products with stock strictly less than 10."""
    conditions, params = [], []

    if name:
        conditions.append("name LIKE ?")
        params.append(f"%{name.strip()}%")
    if stock_below is not None:
        conditions.append("stock < ?")
        params.append(stock_below)

    sql = "SELECT * FROM products"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY name"

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


@router.get("/{name}", summary="Get one product (check inventory) by exact name")
def get_product(name: str):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM products WHERE name = ? COLLATE NOCASE", (name.strip(),)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(404, f"Product '{name}' not found")
    return dict(row)