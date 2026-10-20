from datetime import date
from decimal import Decimal

from card_dispute_intake.engine.extraction import (
    AMOUNT,
    CHARGE_DATE,
    MERCHANT,
    SYSTEM_PROMPT,
    ExtractedFact,
    ExtractedIssue,
    Extraction,
    extract,
    merge_cases,
)
from card_dispute_intake.llm import FakeLLM
from card_dispute_intake.models import DisputeCase, DisputeType, FactSource, Message, Speaker

TODAY = date(2026, 10, 20)


def issue(
    dispute_type: DisputeType,
    facts: dict[str, str] | None = None,
    merchant: str | None = None,
    amount: str | None = None,
    charge_date: str | None = None,
) -> ExtractedIssue:
    return ExtractedIssue(
        dispute_type=dispute_type,
        merchant=merchant,
        amount=amount,
        charge_date=charge_date,
        facts=[ExtractedFact(name=k, value=v) for k, v in (facts or {}).items()],
    )


def test_prompt_lists_checklist_fields_but_not_transaction() -> None:
    assert "card_in_possession" in SYSTEM_PROMPT
    assert "return_method (mail | in_store)" in SYSTEM_PROMPT
    assert "transaction_id" not in SYSTEM_PROMPT


def test_extract_sends_transcript_with_speakers_and_date() -> None:
    llm = FakeLLM(Extraction(issues=[]))
    messages = [
        Message(speaker=Speaker.AGENT, text="How can I help?"),
        Message(speaker=Speaker.CUSTOMER, text="I don't recognize a charge."),
    ]

    extract(llm, messages, TODAY)

    _, user_prompt = llm.calls[0]
    assert "Today's date: 2026-10-20" in user_prompt
    assert "AGENT: How can I help?" in user_prompt
    assert "CUSTOMER: I don't recognize a charge." in user_prompt


def test_facts_are_typed_and_invalid_ones_dropped() -> None:
    extraction = Extraction(
        issues=[
            issue(
                DisputeType.UNAUTHORIZED,
                facts={
                    "card_in_possession": "yes",
                    "recognizes_merchant": "not sure",  # not yes/no -> dropped
                    "favorite_color": "blue",  # not on checklist -> dropped
                },
                merchant=" GLOWFIT ",
                amount="$49.99",
                charge_date="2026-10-02",
            )
        ]
    )

    [case] = merge_cases([], extraction)

    assert case.dispute_type is DisputeType.UNAUTHORIZED
    assert case.get_value("card_in_possession") is True
    assert not case.has_fact("recognizes_merchant")
    assert not case.has_fact("favorite_color")
    assert case.get_value(MERCHANT) == "GLOWFIT"
    assert case.get_value(AMOUNT) == Decimal("49.99")
    assert case.get_value(CHARGE_DATE) == date(2026, 10, 2)


def test_bad_amount_and_date_are_ignored() -> None:
    extraction = Extraction(
        issues=[issue(DisputeType.UNAUTHORIZED, amount="about fifty", charge_date="last week")]
    )
    [case] = merge_cases([], extraction)
    assert not case.has_fact(AMOUNT)
    assert not case.has_fact(CHARGE_DATE)


def test_two_issues_make_two_cases() -> None:
    extraction = Extraction(
        issues=[issue(DisputeType.UNAUTHORIZED), issue(DisputeType.CREDIT_NOT_PROCESSED)]
    )
    cases = merge_cases([], extraction)
    assert [c.dispute_type for c in cases] == [
        DisputeType.UNAUTHORIZED,
        DisputeType.CREDIT_NOT_PROCESSED,
    ]


def test_merge_keeps_case_id_and_agent_input() -> None:
    previous = DisputeCase(
        dispute_type=DisputeType.NOT_RECEIVED, transaction_id="txn_9", transaction_confirmed=True
    )
    previous.set_fact("expected_delivery_date", date(2026, 9, 30), FactSource.AGENT)
    previous.set_fact("item_description", "old answer", FactSource.CUSTOMER)

    extraction = Extraction(
        issues=[
            issue(
                DisputeType.NOT_RECEIVED,
                facts={"item_description": "lawnmower", "expected_delivery_date": "2026-09-01"},
            )
        ]
    )
    [case] = merge_cases([previous], extraction)

    assert case.case_id == previous.case_id
    assert case.transaction_id == "txn_9"
    assert case.transaction_confirmed
    assert case.get_value("item_description") == "lawnmower"
    # The agent's entry wins over what the model read from the chat.
    assert case.get_value("expected_delivery_date") == date(2026, 9, 30)


def test_case_dropped_when_customer_corrects_type() -> None:
    previous = DisputeCase(dispute_type=DisputeType.UNAUTHORIZED)
    extraction = Extraction(issues=[issue(DisputeType.CANCELLED_RECURRING)])

    cases = merge_cases([previous], extraction)

    assert [c.dispute_type for c in cases] == [DisputeType.CANCELLED_RECURRING]


def test_case_with_agent_input_is_kept_even_if_not_extracted() -> None:
    previous = DisputeCase(dispute_type=DisputeType.UNAUTHORIZED)
    previous.set_fact("card_in_possession", True, FactSource.AGENT)

    cases = merge_cases([previous], Extraction(issues=[]))

    assert cases == [previous]
