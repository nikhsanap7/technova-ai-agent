from typing import Optional

from fastapi import APIRouter, HTTPException

from backend.database import get_connection

router = APIRouter(prefix="/customers", tags=["Customers"])

VALID_STATUSES = {"active": "Active", "inactive": "Inactive"}


@router.get("", summary="Search customers by country and/or status")
def search_customers(country: Optional[str] = None, status: Optional[str] = None):
    conditions, params = [], []

    if country:
        conditions.append("country = ? COLLATE NOCASE")
        params.append(country.strip())
    if status:
        normalized = VALID_STATUSES.get(status.strip().lower())
        if normalized is None:
            raise HTTPException(400, "Invalid status. Allowed: Active, Inactive")
        conditions.append("status = ?")
        params.append(normalized)

    sql = "SELECT * FROM customers"
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY customer_id"

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


@router.get("/{customer_id}", summary="Get one customer by ID")
def get_customer(customer_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM customers WHERE customer_id = ?", (customer_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(404, f"Customer {customer_id} not found")
    return dict(row)