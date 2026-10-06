"""HTTP request and response models. Unknown fields are rejected, and every input is bounded."""

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

from concierge.bookings.models import Booking
from concierge.bookings.repository import ApprovalRequest

Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    ),
]


def _dollars(cents: int) -> str:
    return f"${cents / 100:.2f}"


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_id: UUID | None = Field(
        default=None, description="Omit to start a new conversation; reuse it for follow-ups"
    )
    customer_email: Email = Field(description="Customer identity, asserted by the client backend")
    message: str = Field(min_length=1, max_length=4_000)


class Source(BaseModel):
    id: str
    title: str
    heading: str


class TranscriptMessage(BaseModel):
    role: Literal["customer", "assistant"]
    content: str


class ChatResponse(BaseModel):
    conversation_id: UUID
    status: Literal["completed", "pending_approval"]
    reply: str
    outcome: str | None
    intent: str | None
    handoff_reason: str | None = Field(
        default=None, description="Why the turn went to a person, when outcome is handoff"
    )
    sources: list[Source]
    request_id: str


class StatsOut(BaseModel):
    """Live cost figures from the token ledger: aggregates only, no customer or chat data."""

    window_hours: int
    conversations: int = Field(description="Conversations that reached a model in the window")
    usd_total: float
    usd_per_conversation: float | None = Field(
        description="Null until at least one conversation has reached a model"
    )
    tokens_in_window: int
    daily_token_budget: int
    conversation_token_budget: int
    unpriced_models: list[str] = Field(
        description="Models with no price on file; their cost is counted at the highest tier"
    )


class BookingOut(BaseModel):
    reference: str
    service: str
    scheduled_for: datetime
    status: Literal["scheduled", "completed", "cancelled"]
    amount_cents: int
    amount: str
    refunded_cents: int
    refunded: str

    @classmethod
    def from_domain(cls, booking: Booking) -> Self:
        return cls(
            reference=booking.reference,
            service=booking.service,
            scheduled_for=booking.scheduled_for,
            status=booking.status,
            amount_cents=booking.amount_cents,
            amount=_dollars(booking.amount_cents),
            refunded_cents=booking.refunded_cents,
            refunded=_dollars(booking.refunded_cents),
        )


class ApprovalOut(BaseModel):
    id: UUID
    conversation_id: UUID
    customer_email: str | None = None
    booking_reference: str
    action: str
    amount_cents: int
    amount: str
    # What the reviewer actually authorised when it was less than the policy amount.
    approved_amount_cents: int | None = None
    approved_amount: str | None = None
    policy_reason: str
    status: Literal["pending", "approved", "rejected"]
    reviewer: str | None
    review_note: str | None
    created_at: datetime
    decided_at: datetime | None

    @classmethod
    def from_domain(cls, approval: ApprovalRequest) -> Self:
        approved = approval.approved_amount_cents
        fields = {k: v for k, v in approval.__dict__.items() if k != "approved_amount_cents"}
        return cls(
            **fields,
            amount=_dollars(approval.amount_cents),
            approved_amount_cents=approved,
            approved_amount=_dollars(approved) if approved is not None else None,
        )


class ApprovalDetail(BaseModel):
    approval: ApprovalOut
    booking: BookingOut | None
    transcript: list[TranscriptMessage]


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approve: bool
    note: str | None = Field(default=None, max_length=500)
    approved_amount_cents: int | None = Field(
        default=None,
        gt=0,
        description="Approve LESS than the policy amount. Omit to approve the full amount.",
    )

    @model_validator(mode="after")
    def _amount_only_with_approval(self) -> Self:
        if self.approved_amount_cents is not None and not self.approve:
            raise ValueError("an amount can only accompany an approval")
        return self


class DecisionResponse(BaseModel):
    approval: ApprovalOut
    outcome: str | None
    customer_reply: str
