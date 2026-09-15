from dataclasses import dataclass
from datetime import datetime
from typing import Literal

BookingStatus = Literal["scheduled", "completed", "cancelled"]


@dataclass(frozen=True)
class Booking:
    reference: str
    customer_email: str
    service: str
    scheduled_for: datetime
    amount_cents: int
    status: BookingStatus
    refunded_cents: int = 0

    @property
    def refundable_cents(self) -> int:
        return self.amount_cents - self.refunded_cents

    def to_public_dict(self) -> dict[str, object]:
        """What the model and the customer may see. Email stays out of prompts."""
        return {
            "reference": self.reference,
            "service": self.service,
            "scheduled_for": self.scheduled_for.isoformat(),
            "amount": f"${self.amount_cents / 100:.2f}",
            "status": self.status,
            "refunded": f"${self.refunded_cents / 100:.2f}",
        }
