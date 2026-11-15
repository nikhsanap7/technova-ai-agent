from tools.mcp_client import call_tool_sync


def test_all_read_tools_execute():
    """Runs every read tool once. Needs the backend running and seeded."""
    cases = [
        ("get_customer", {"customer_id": 1025}),
        ("search_customers", {}),
        ("get_order", {"order_id": 5001}),
        ("search_orders", {}),
        ("search_products", {}),
        ("search_products", {"name": "Lap"}),
        ("search_products", {"stock_below": 10}),
        ("check_inventory", {"product_name": "Laptop"}),
        ("search_invoices", {}),
        ("search_unpaid_invoices", {}),
    ]
    for name, args in cases:
        result = call_tool_sync(name, args)
        assert result.get("ok") is True, f"{name} {args} -> {result}"