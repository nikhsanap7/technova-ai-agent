from typing import Optional

from fastapi import APIRouter, HTTPException

from backend.database import get_connection

router = APIRouter(prefix="/invoices", tags=["Invoices"])

PAYMENT_STATUSES = {"paid": "Paid", "unpaid": "Unpaid"}

BASE_QUERY = """
SELECT i.invoice_id, i.customer_id, c.company, i.amount, i.payment_status
FROM invoices i
JOIN customers c ON i.customer_id = c.customer_id
"""


@router.get("", summary="Search invoices by payment status and/or customer")
def search_invoices(
    payment_status: Optional[str] = None, customer_id: Optional[int] = None
):
    conditions, params = [], []

    if payment_status:
        normalized = PAYMENT_STATUSES.get(payment_status.strip().lower())
        if normalized is None:
            raise HTTPException(400, "Invalid payment_status. Allowed: Paid, Unpaid")
        conditions.append("i.payment_status = ?")
        params.append(normalized)
    if customer_id is not None:
        conditions.append("i.customer_id = ?")
        params.append(customer_id)

    sql = BASE_QUERY
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    sql += " ORDER BY i.invoice_id"

    conn = get_connection()
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [dict(r) for r in rows]


@router.get("/{invoice_id}", summary="Get one invoice by ID")
def get_invoice(invoice_id: int):
    conn = get_connection()
    try:
        row = conn.execute(
            BASE_QUERY + " WHERE i.invoice_id = ?", (invoice_id,)
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        raise HTTPException(404, f"Invoice {invoice_id} not found")
    return dict(row)