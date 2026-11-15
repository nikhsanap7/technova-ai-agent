"""Deterministic keyword retrieval over data/metadata.json.

Scoring (simple and explainable):
  +3 per query word found in the operation's keywords
  +2 per query word found in the tool name
  +1 per query word found in the description or examples
  +2 bonus if the query contains a number and the operation requires
     parameters (e.g. "customer 1025" -> get_customer beats search_customers)
"""
import json
import re
from pathlib import Path

METADATA_PATH = Path(__file__).resolve().parent.parent / "data" / "metadata.json"

STOPWORDS = {
    "the", "a", "an", "me", "all", "of", "from", "to", "in", "is", "are",
    "which", "have", "has", "with", "for", "show", "give", "please", "as",
    "and", "or", "that", "this", "what", "who", "do", "can", "i", "my",
}


def load_operations() -> list[dict]:
    with open(METADATA_PATH, encoding="utf-8") as f:
        return json.load(f)["operations"]


def _tokens(text: str) -> set[str]:
    """Lowercase words; strip a trailing 's' so 'orders' matches 'order'."""
    words = re.findall(r"[a-z0-9]+", text.lower())
    return {
        (w[:-1] if len(w) > 3 and w.endswith("s") else w)
        for w in words
        if w not in STOPWORDS
    }


def search_operations(query: str, top_k: int = 3) -> list[dict]:
    """Return up to top_k operations ranked by score (score 0 is dropped)."""
    q = _tokens(query)
    has_number = bool(re.search(r"\d", query))
    results = []

    for op in load_operations():
        kw = _tokens(" ".join(op["keywords"]))
        name = _tokens(op["tool_name"].replace("_", " "))
        text = _tokens(op["description"] + " " + " ".join(op["examples"]))

        score = 3 * len(q & kw) + 2 * len(q & name) + len(q & text)
        has_required = any(p["required"] for p in op["parameters"].values())
        if score > 0 and has_number and has_required:
            score += 2

        if score > 0:
            results.append({
                "tool_name": op["tool_name"],
                "score": score,
                "access": op["access"],
                "description": op["description"],
            })

    results.sort(key=lambda r: r["score"], reverse=True)
    return results[:top_k]


def get_write_tools() -> set[str]:
    """Names of all tools marked access = write (used for confirmation later)."""
    return {op["tool_name"] for op in load_operations() if op["access"] == "write"}


if __name__ == "__main__":
    # Manual test: python -m retrieval.metadata_search
    tests = [
        ("Find customer 1025", "get_customer"),
        ("Show all pending orders from German customers", "search_orders"),
        ("Which products have less than 10 units in stock?", "search_products"),
        ("Show all unpaid invoices", "search_unpaid_invoices"),
        ("Mark order 5001 as Delivered", "update_order_status"),
        ("Find all orders belonging to ABC Technologies GmbH", "search_orders"),
        ("How many laptops are in stock?", "check_inventory"),
        ("Show order 5003", "get_order"),
    ]
    top1 = top3 = 0
    for query, expected in tests:
        hits = search_operations(query)
        names = [h["tool_name"] for h in hits]
        ok1 = bool(names) and names[0] == expected
        ok3 = expected in names
        top1 += ok1
        top3 += ok3
        print(f"[{'PASS' if ok1 else 'FAIL'}] {query}")
        print(f"        expected: {expected}")
        print(f"        got:      {[(h['tool_name'], h['score']) for h in hits]}")
    print(f"\nTop-1 correct: {top1}/{len(tests)}   Top-3 contains it: {top3}/{len(tests)}")
    print("Write tools:", get_write_tools())