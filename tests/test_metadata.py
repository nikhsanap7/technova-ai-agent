from retrieval.metadata_search import load_operations
from tools.mcp_client import list_tools_sync


def test_metadata_matches_mcp_server():
    meta = {op["tool_name"]: op for op in load_operations()}
    live = {t["name"]: t for t in list_tools_sync()}

    assert set(meta) == set(live), (
        f"Only in metadata: {set(meta) - set(live)}; "
        f"only in MCP server: {set(live) - set(meta)}"
    )

    for name, op in meta.items():
        live_params = set(live[name]["input_schema"].get("properties", {}))
        assert set(op["parameters"]) == live_params, f"Parameter mismatch in {name}"
        live_required = set(live[name]["input_schema"].get("required", []))
        meta_required = {p for p, d in op["parameters"].items() if d["required"]}
        assert meta_required == live_required, f"Required-flag mismatch in {name}"


def test_only_update_is_write():
    from retrieval.metadata_search import get_write_tools
    assert get_write_tools() == {"update_order_status"}