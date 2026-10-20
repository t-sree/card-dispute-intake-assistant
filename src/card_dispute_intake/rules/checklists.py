"""Required information per dispute type.

Field lists are based on the evidence card networks expect for the matching reason codes
(see reason_codes.py) and the billing error notice content in Regulation Z, 12 CFR 1026.13.
Order matters: it is the order an agent would naturally ask in, and the next-question logic
relies on it.
"""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from enum import StrEnum

from card_dispute_intake.models import DisputeCase, DisputeType, FactValue

Condition = Callable[[DisputeCase], bool]


class FieldKind(StrEnum):
    YES_NO = "yes_no"
    DATE = "date"
    CHOICE = "choice"
    TEXT = "text"


_YES = {"yes", "y", "true"}
_NO = {"no", "n", "false"}


@dataclass(frozen=True)
class RequiredField:
    name: str
    question: str
    kind: FieldKind = FieldKind.TEXT
    choices: tuple[str, ...] = ()
    required_if: Condition | None = None

    def applies_to(self, case: DisputeCase) -> bool:
        return self.required_if is None or self.required_if(case)

    def parse(self, raw: str) -> FactValue | None:
        """Convert a raw extracted string into a typed value, or None if it doesn't fit."""
        text = raw.strip()
        match self.kind:
            case FieldKind.YES_NO:
                lowered = text.lower()
                return True if lowered in _YES else False if lowered in _NO else None
            case FieldKind.DATE:
                try:
                    return date.fromisoformat(text)
                except ValueError:
                    return None
            case FieldKind.CHOICE:
                lowered = text.lower()
                return lowered if lowered in self.choices else None
            case FieldKind.TEXT:
                return text or None


def _fact_equals(name: str, expected: object) -> Condition:
    return lambda case: case.get_value(name) == expected


TRANSACTION = RequiredField("transaction_id", "Which charge on the account is this about?")

_MERCHANT_CONTACT = (
    RequiredField(
        "merchant_contacted", "Have you contacted the merchant about this?", FieldKind.YES_NO
    ),
    RequiredField(
        "merchant_contact_date",
        "When did you contact them?",
        FieldKind.DATE,
        required_if=_fact_equals("merchant_contacted", True),
    ),
    RequiredField(
        "merchant_response",
        "What did the merchant tell you?",
        required_if=_fact_equals("merchant_contacted", True),
    ),
)

CHECKLISTS: dict[DisputeType, tuple[RequiredField, ...]] = {
    DisputeType.UNAUTHORIZED: (
        TRANSACTION,
        RequiredField("card_in_possession", "Do you still have your card?", FieldKind.YES_NO),
        RequiredField(
            "recognizes_merchant",
            "Do you recognize the merchant name at all?",
            FieldKind.YES_NO,
        ),
        RequiredField(
            "others_have_access",
            "Has anyone else, like a family member, had access to your card or card details?",
            FieldKind.YES_NO,
        ),
    ),
    DisputeType.NOT_RECEIVED: (
        TRANSACTION,
        RequiredField("item_description", "What did you order?"),
        RequiredField(
            "expected_delivery_date", "When were you expecting to receive it?", FieldKind.DATE
        ),
        *_MERCHANT_CONTACT,
    ),
    DisputeType.CREDIT_NOT_PROCESSED: (
        TRANSACTION,
        RequiredField("return_date", "When did you return the item?", FieldKind.DATE),
        RequiredField(
            "return_method",
            "How did you return it, by mail or in store?",
            FieldKind.CHOICE,
            choices=("mail", "in_store"),
        ),
        RequiredField(
            "tracking_number",
            "Do you have the return tracking number?",
            required_if=_fact_equals("return_method", "mail"),
        ),
        *_MERCHANT_CONTACT,
    ),
    DisputeType.CANCELLED_RECURRING: (
        TRANSACTION,
        RequiredField("cancellation_date", "When did you cancel the subscription?", FieldKind.DATE),
        RequiredField(
            "cancellation_method",
            "How did you cancel: online, by phone or email?",
            FieldKind.CHOICE,
            choices=("online", "phone", "email"),
        ),
        RequiredField(
            "cancellation_confirmation",
            "Did you get a cancellation confirmation number or email?",
        ),
        *_MERCHANT_CONTACT,
    ),
}


def checklist_for(dispute_type: DisputeType) -> tuple[RequiredField, ...]:
    return CHECKLISTS[dispute_type]
