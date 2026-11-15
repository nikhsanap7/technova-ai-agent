from typing import Optional

from fastapi import APIRouter, HTTPException

from backend.database import get_connection
from backend.models import OrderStatusUpdate, VALID_ORDER_STATUSES

router = APIRouter(prefix="/orders", tags=["Orders"])

# Orders joined with customer info, so we can filter by country or company.
BASE_QUERY = """
SELECT o.order_id, o.customer_id, c.company, c.country,
       o.product, o.amount, o.status
FROM orders o
JOIN customers c ON o.customer_id = c.customer_id
"""


@router.get("", summary="Search orders by status, customer, country or company")
def search_orders(
    status: Optional[str] = None,
    customer_id: Optional[int] = None,
    country: Optional[str] = None,
    company: Optional[str] = None,
):
    conditions, params = [], []

    if status:
        valid = {s.lower(): s for s in VALID_ORDER_STATUSES}
        normalized = valid.get(status.strip().lower())
        if normalized is None:
            raise HTTPException(
                400, f"Invalid status. Allowed: {', '.join(VALID_ORDER_STATUSES)}"
            )
        conditions.append("o.status = ?")
        params.append(normalized)
    if customer_id is not None:
        conditions.append("o.customer_id = ?")
        params.append(customer_id)
    if country:
        conditions.append("c.country = ? COLLATE NOCASE")
        params.append(country.strip())
    if company:
        conditions.append("c.company LIKE ?")
        params.append(f"%{company.strip()}%")

    sql = BASE_QUERY
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY o.order_id"

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


@router.get("/{order_id}", summary="Get one order by ID")
def get_order(order_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            BASE_QUERY + " WHERE o.order_id = ?", (order_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(404, f"Order {order_id} not found")
    return dict(row)


@router.patch("/{order_id}/status", summary="Update an order's status (WRITE)")
def update_order_status(order_id: int, body: OrderStatusUpdate):
    conn = get_connection()
    try:
        exists = conn.execute(
            "SELECT 1 FROM orders WHERE order_id = ?", (order_id,)
        ).fetchone()
        if exists is None:
            raise HTTPException(404, f"Order {order_id} not found")

        conn.execute(
            "UPDATE orders SET status = ? WHERE order_id = ?",
            (body.status, order_id),
        )
        conn.commit()
        row = conn.execute(
            BASE_QUERY + " WHERE o.order_id = ?", (order_id,)
        ).fetchone()
    finally:
        conn.close()
    return dict(row)