from pydantic import BaseModel, field_validator

VALID_ORDER_STATUSES = ["Pending", "Processing", "Delivered", "Cancelled"]


class OrderStatusUpdate(BaseModel):
    """Body of the request used to change an order's status."""
    status: str

    @field_validator("status")
    @classmethod
    def normalize_status(cls, value: str) -> str:
        # Accept "delivered", "DELIVERED", " Delivered " -> "Delivered"
        lookup = {s.lower(): s for s in VALID_ORDER_STATUSES}
        match = lookup.get(value.strip().lower())
        if match is None:
            raise ValueError(
                f"Invalid status '{value}'. Allowed: {', '.join(VALID_ORDER_STATUSES)}"
            )
        return match