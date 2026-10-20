"""Core domain models shared by the rules engine, extraction layer and UI."""

from datetime import UTC, date, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class DisputeType(StrEnum):
    UNAUTHORIZED = "unauthorized"
    NOT_RECEIVED = "not_received"
    CREDIT_NOT_PROCESSED = "credit_not_processed"
    CANCELLED_RECURRING = "cancelled_recurring"


class CardNetwork(StrEnum):
    VISA = "visa"
    MASTERCARD = "mastercard"


class FactSource(StrEnum):
    """Where a fact came from. Matters for review: stated facts are claims, account data is not."""

    CUSTOMER = "customer"
    ACCOUNT = "account"
    AGENT = "agent"


FactValue = bool | date | Decimal | str


class Transaction(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    transaction_id: str
    posted_date: date
    merchant: str
    amount: Decimal = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=3)
    is_recurring: bool = False


class Fact(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    name: str
    value: FactValue
    source: FactSource


def _new_case_id() -> str:
    return f"case_{uuid4().hex[:12]}"


def _utc_now() -> datetime:
    return datetime.now(UTC)


class DisputeCase(BaseModel):
    """A single dispute being built up during a conversation.

    One conversation can produce several cases (e.g. a fraud charge and a missing refund),
    so the case, not the conversation, is the unit the checklist runs against.
    """

    model_config = ConfigDict(extra="forbid")

    case_id: str = Field(default_factory=_new_case_id)
    dispute_type: DisputeType | None = None
    transaction_id: str | None = None
    transaction_confirmed: bool = False
    facts: dict[str, Fact] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_utc_now)

    def set_fact(self, name: str, value: FactValue, source: FactSource) -> None:
        """Record a fact, replacing any earlier value (e.g. the customer corrects a date)."""
        self.facts[name] = Fact(name=name, value=value, source=source)

    def has_fact(self, name: str) -> bool:
        return name in self.facts

    def get_value(self, name: str) -> FactValue | None:
        fact = self.facts.get(name)
        return fact.value if fact else None


class Speaker(StrEnum):
    CUSTOMER = "customer"
    AGENT = "agent"


class Message(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    speaker: Speaker
    text: str
