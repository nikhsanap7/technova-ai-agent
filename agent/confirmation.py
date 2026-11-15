"""Write-operation safety: which tools are writes, and what is pending."""
from dataclasses import dataclass, field
from typing import Optional

from retrieval.metadata_search import get_write_tools

# Single source of truth: tools marked access = "write" in data/metadata.json
WRITE_TOOLS = get_write_tools()

# Checked here as well as in the backend (defence in depth), so we never ask
# the user to confirm a change that the backend would reject anyway.
ALLOWED_ORDER_STATUSES = ["Pending", "Processing", "Delivered", "Cancelled"]


def is_write_tool(name: str) -> bool:
    return name in WRITE_TOOLS


def normalize_order_status(value) -> Optional[str]:
    """'delivered' -> 'Delivered'. Returns None if not a valid status."""
    if not isinstance(value, str):
        return None
    lookup = {s.lower(): s for s in ALLOWED_ORDER_STATUSES}
    return lookup.get(value.strip().lower())


@dataclass
class PendingAction:
    """A write operation that is waiting for the user's explicit confirmation."""
    tool_name: str
    args: dict
    description: str                      # shown to the user
    parts: list = field(default_factory=list)   # function responses for this turn
    slot: int = 0                         # where the write's response goes