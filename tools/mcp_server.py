"""MCP server: exposes TechNova enterprise operations as tools.

It contains no business data. Every tool calls the FastAPI backend.
IMPORTANT: a stdio MCP server must never print() to stdout, because stdout
is the channel used to talk to the client. We log to a file and stderr.
"""
import logging
import sys
from pathlib import Path
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

API_BASE = "http://127.0.0.1:8000"

# ---------- logging (file + stderr, never stdout) ----------
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "tool_calls.log", encoding="utf-8"),
        logging.StreamHandler(sys.stderr),
    ],
)
log = logging.getLogger("technova.mcp")

mcp = FastMCP("TechNova Enterprise Tools")


# ---------- helper that talks to the backend ----------
def _api(method: str, path: str, params: Optional[dict] = None,
         json_body: Optional[dict] = None) -> dict:
    """Call the FastAPI backend and return a uniform result dict:
    {"ok": True, "data": ...}  or  {"ok": False, "error": "..."}"""
    params = {k: v for k, v in (params or {}).items() if v is not None}
    try:
        r = httpx.request(method, API_BASE + path, params=params,
                          json=json_body, timeout=10)
    except httpx.ConnectError:
        result = {"ok": False,
                  "error": "Enterprise backend is not reachable. "
                           "Is uvicorn running on port 8000?"}
    except httpx.TimeoutException:
        result = {"ok": False, "error": "Enterprise backend timed out."}
    else:
        if r.status_code >= 400:
            try:
                detail = r.json().get("detail", r.text)
            except ValueError:
                detail = r.text
            result = {"ok": False, "status_code": r.status_code, "error": detail}
        else:
            data = r.json()
            result = {"ok": True, "data": data}
            if isinstance(data, list):
                result["count"] = len(data)
    log.info("API %s %s params=%s -> ok=%s", method, path, params, result["ok"])
    return result


def _log_tool(tool_name: str, /, **args) -> None:
    log.info("TOOL %s args=%s", tool_name, args)


def _bad_id(name: str, value: int) -> dict:
    return {"ok": False, "error": f"{name} must be a positive integer, got {value}"}


# ---------- customer tools (read) ----------
@mcp.tool()
def get_customer(customer_id: int) -> dict:
    """Retrieve the details of ONE customer by numeric customer ID
    (e.g. 1025): company name, country and status."""
    _log_tool("get_customer", customer_id=customer_id)
    if customer_id <= 0:
        return _bad_id("customer_id", customer_id)
    return _api("GET", f"/customers/{customer_id}")


@mcp.tool()
def search_customers(country: Optional[str] = None,
                     status: Optional[str] = None) -> dict:
    """Search customers. Optional filters: country (e.g. 'Germany') and
    status ('Active' or 'Inactive'). With no filters, returns all customers."""
    _log_tool("search_customers", country=country, status=status)
    return _api("GET", "/customers", {"country": country, "status": status})


# ---------- order tools ----------
@mcp.tool()
def get_order(order_id: int) -> dict:
    """Retrieve ONE order by numeric order ID (e.g. 5001), including the
    customer's company and country."""
    _log_tool("get_order", order_id=order_id)
    if order_id <= 0:
        return _bad_id("order_id", order_id)
    return _api("GET", f"/orders/{order_id}")


@mcp.tool()
def search_orders(status: Optional[str] = None,
                  customer_id: Optional[int] = None,
                  country: Optional[str] = None,
                  company: Optional[str] = None) -> dict:
    """Search orders. All filters are optional and can be combined:
    status ('Pending', 'Processing', 'Delivered' or 'Cancelled'),
    customer_id (number), country of the customer (e.g. 'Germany'),
    company (customer company name, partial match, e.g. 'ABC Technologies')."""
    _log_tool("search_orders", status=status, customer_id=customer_id,
              country=country, company=company)
    return _api("GET", "/orders", {"status": status, "customer_id": customer_id,
                                   "country": country, "company": company})


@mcp.tool()
def update_order_status(order_id: int, status: str) -> dict:
    """WRITE OPERATION: change the status of an order. Allowed statuses:
    'Pending', 'Processing', 'Delivered', 'Cancelled'.
    Must only be executed after the user has explicitly confirmed."""
    _log_tool("update_order_status", order_id=order_id, status=status)
    if order_id <= 0:
        return _bad_id("order_id", order_id)
    return _api("PATCH", f"/orders/{order_id}/status", json_body={"status": status})


# ---------- product tools (read) ----------
@mcp.tool()
def search_products(name: Optional[str] = None,
                    stock_below: Optional[int] = None) -> dict:
    """List products with price and stock. Optional filters: name (partial
    match) and stock_below (returns products with stock STRICTLY LESS than
    this number, e.g. 10 for 'less than 10 units'). Use this for low-inventory
    questions."""
    _log_tool("search_products", name=name, stock_below=stock_below)
    return _api("GET", "/products", {"name": name, "stock_below": stock_below})


@mcp.tool()
def check_inventory(product_name: str) -> dict:
    """Check stock level and price of ONE product by its exact name
    (e.g. 'Laptop')."""
    _log_tool("check_inventory", product_name=product_name)
    if not product_name.strip():
        return {"ok": False, "error": "product_name must not be empty"}
    return _api("GET", f"/products/{product_name.strip()}")


# ---------- invoice tools (read) ----------
@mcp.tool()
def search_invoices(customer_id: Optional[int] = None,
                    payment_status: Optional[str] = None) -> dict:
    """Search invoices. Optional filters: customer_id (number) and
    payment_status ('Paid' or 'Unpaid'). With no filters, returns all invoices."""
    _log_tool("search_invoices", customer_id=customer_id,
              payment_status=payment_status)
    return _api("GET", "/invoices", {"customer_id": customer_id,
                                     "payment_status": payment_status})


@mcp.tool()
def search_unpaid_invoices() -> dict:
    """Return all invoices whose payment status is 'Unpaid'."""
    _log_tool("search_unpaid_invoices")
    return _api("GET", "/invoices", {"payment_status": "Unpaid"})


if __name__ == "__main__":
    mcp.run()  # default transport: stdio