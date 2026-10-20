"""Turn a conversation transcript into dispute cases.

The LLM only reads: it reports which disputes the customer raised and which facts they
stated, as plain strings. Code then validates every value against the checklist field
definitions and drops anything that doesn't fit, so a hallucinated field or a vague date
never reaches the case.
"""

from datetime import date
from decimal import Decimal, InvalidOperation

from pydantic import BaseModel

from card_dispute_intake.llm import LLMClient
from card_dispute_intake.models import (
    DisputeCase,
    DisputeType,
    FactSource,
    FactValue,
    Message,
)
from card_dispute_intake.rules.checklists import TRANSACTION, FieldKind, checklist_for

# Facts used to find the disputed charge. Not on any checklist.
MERCHANT = "merchant"
AMOUNT = "amount"
CHARGE_DATE = "charge_date"


class ExtractedFact(BaseModel):
    name: str
    value: str


class ExtractedIssue(BaseModel):
    dispute_type: DisputeType
    merchant: str | None
    amount: str | None
    charge_date: str | None
    facts: list[ExtractedFact]


class Extraction(BaseModel):
    issues: list[ExtractedIssue]


def _describe_fields() -> str:
    lines = []
    for dispute_type in DisputeType:
        lines.append(f"{dispute_type.value}:")
        for field in checklist_for(dispute_type):
            if field is TRANSACTION:
                continue
            fmt = {
                FieldKind.YES_NO: '"yes" or "no"',
                FieldKind.DATE: "YYYY-MM-DD",
                FieldKind.CHOICE: " | ".join(field.choices),
                FieldKind.TEXT: "short text",
            }[field.kind]
            lines.append(f"  - {field.name} ({fmt}): {field.question}")
    return "\n".join(lines)


SYSTEM_PROMPT = f"""You read a chat between a bank agent and a credit card customer and report \
the card disputes the customer is raising.

Dispute types:
- unauthorized: the customer says they did not make or allow the charge
- not_received: they paid for goods or services that never arrived
- credit_not_processed: they returned something or were promised a refund that never posted
- cancelled_recurring: they cancelled a subscription or membership but were still charged

Rules:
- One issue per disputed charge or problem. Two different charges means two issues. \
Never report the same charge twice.
- Describe the situation as it stands at the end of the chat. If the customer's later \
messages change what the problem is (for example an "unknown" charge turns out to be a \
membership they cancelled), report only the corrected dispute type.
- Only report facts the customer actually said, or clearly answered when the agent asked. \
Never infer an answer from context: if they say they joined a gym, that does not tell you \
whether they still have their card. Leave out anything not stated.
- merchant, amount (number only, e.g. 49.99) and charge_date describe the disputed charge; \
use null when not mentioned.
- Dates must be YYYY-MM-DD. Resolve relative dates ("last Tuesday") using today's date. \
If a date is too vague to pin to a day, leave that fact out.
- Only use these fact names, with these value formats:

{_describe_fields()}
"""


def _format_transcript(messages: list[Message], today: date) -> str:
    lines = [f"Today's date: {today.isoformat()}", ""]
    lines += [f"{m.speaker.value.upper()}: {m.text}" for m in messages]
    return "\n".join(lines)


def extract(llm: LLMClient, messages: list[Message], today: date) -> Extraction:
    return llm.parse(SYSTEM_PROMPT, _format_transcript(messages, today), Extraction)


def _parse_amount(raw: str) -> Decimal | None:
    try:
        amount = Decimal(raw.replace("$", "").replace(",", "").strip())
    except InvalidOperation:
        return None
    return amount if amount > 0 else None


def _parse_date(raw: str) -> date | None:
    try:
        return date.fromisoformat(raw.strip())
    except ValueError:
        return None


def _issue_to_case(issue: ExtractedIssue, previous: DisputeCase | None) -> DisputeCase:
    case = DisputeCase(dispute_type=issue.dispute_type)
    if previous is not None:
        # Keep identity and anything the agent entered or confirmed by hand.
        case.case_id = previous.case_id
        case.created_at = previous.created_at
        case.transaction_id = previous.transaction_id
        case.transaction_confirmed = previous.transaction_confirmed
        case.facts = {n: f for n, f in previous.facts.items() if f.source is FactSource.AGENT}

    def set_customer_fact(name: str, value: FactValue | None) -> None:
        if value is not None and name not in case.facts:
            case.set_fact(name, value, FactSource.CUSTOMER)

    if issue.merchant:
        set_customer_fact(MERCHANT, issue.merchant.strip())
    if issue.amount:
        set_customer_fact(AMOUNT, _parse_amount(issue.amount))
    if issue.charge_date:
        set_customer_fact(CHARGE_DATE, _parse_date(issue.charge_date))

    fields = {f.name: f for f in checklist_for(issue.dispute_type) if f is not TRANSACTION}
    for fact in issue.facts:
        field = fields.get(fact.name)
        if field is not None:
            set_customer_fact(field.name, field.parse(fact.value))
    return case


def charge_details(case: DisputeCase) -> tuple[str | None, Decimal | None, date | None]:
    """The merchant, amount and date the customer gave for the disputed charge."""
    merchant, amount, charge_date = (case.get_value(n) for n in (MERCHANT, AMOUNT, CHARGE_DATE))
    return (
        merchant if isinstance(merchant, str) else None,
        amount if isinstance(amount, Decimal) else None,
        charge_date if isinstance(charge_date, date) else None,
    )


def merge_cases(previous: list[DisputeCase], extraction: Extraction) -> list[DisputeCase]:
    """Rebuild cases from the latest extraction, keeping ids and agent input from before.

    The whole transcript is re-read every turn, so customer corrections simply win. A case
    is carried over by dispute type; previous cases the customer no longer describes are
    dropped unless the agent has already worked on them.
    """
    unmatched = list(previous)
    cases = []
    for issue in extraction.issues:
        match = next((c for c in unmatched if c.dispute_type is issue.dispute_type), None)
        if match is not None:
            unmatched.remove(match)
        cases.append(_issue_to_case(issue, match))

    agent_touched = [
        c for c in unmatched if any(f.source is FactSource.AGENT for f in c.facts.values())
    ]
    return cases + agent_touched
