"""HTTP request and response models. Unknown fields are rejected, and every input is bounded."""

from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from concierge.bookings.repository import ApprovalRequest

Email = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, to_lower=True, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    ),
]


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


class ApprovalOut(BaseModel):
    id: UUID
    conversation_id: UUID
    booking_reference: str
    action: str
    amount_cents: int
    amount: str
    policy_reason: str
    status: Literal["pending", "approved", "rejected"]
    reviewer: str | None
    review_note: str | None
    created_at: datetime
    decided_at: datetime | None

    @classmethod
    def from_domain(cls, approval: ApprovalRequest) -> Self:
        return cls(
            **approval.__dict__, amount=f"${approval.amount_cents / 100:.2f}"
        )


class DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approve: bool
    note: str | None = Field(default=None, max_length=500)


class DecisionResponse(BaseModel):
    approval: ApprovalOut
    outcome: str | None
    customer_reply: str
