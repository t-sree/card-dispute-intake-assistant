"""End-to-end turns through the LangGraph flow, with a scripted LLM."""

from datetime import date
from decimal import Decimal

import pytest

from card_dispute_intake.data.accounts import Account
from card_dispute_intake.engine.extraction import ExtractedFact, ExtractedIssue, Extraction
from card_dispute_intake.engine.graph import SuggestionKind
from card_dispute_intake.engine.session import IntakeSession
from card_dispute_intake.llm import FakeLLM
from card_dispute_intake.models import (
    CardNetwork,
    DisputeType,
    FactSource,
    Speaker,
    Transaction,
)

TODAY = date(2026, 10, 20)


def txn(tid: str, posted: date, merchant: str, amount: str, recurring: bool = False) -> Transaction:
    return Transaction(
        transaction_id=tid,
        posted_date=posted,
        merchant=merchant,
        amount=Decimal(amount),
        is_recurring=recurring,
    )


ACCOUNT = Account(
    account_id="acct_1",
    network=CardNetwork.VISA,
    statement_day=20,
    transactions=[
        txn("s1", date(2026, 8, 2), "GLOWFIT MEMBERSHIP", "49.99", recurring=True),
        txn("s2", date(2026, 9, 2), "GLOWFIT MEMBERSHIP", "49.99", recurring=True),
        txn("s3", date(2026, 10, 2), "GLOWFIT MEMBERSHIP", "49.99", recurring=True),
        txn("r1", date(2026, 9, 1), "SHOEHUB.COM", "120.00"),
    ],
)


def unauthorized(**facts: str) -> ExtractedIssue:
    return ExtractedIssue(
        dispute_type=DisputeType.UNAUTHORIZED,
        merchant="Glowfit",
        amount="49.99",
        charge_date="2026-10-02",
        facts=[ExtractedFact(name=k, value=v) for k, v in facts.items()],
    )


def suggestion_kinds(session: IntakeSession) -> list[SuggestionKind]:
    return [s.kind for s in session.state.get("suggestions", [])]


def test_first_turn_creates_case_matches_charge_and_asks_next_question() -> None:
    llm = FakeLLM(Extraction(issues=[unauthorized()]))
    session = IntakeSession(llm, ACCOUNT, TODAY)

    session.agent_says("How can I help?")
    state = session.customer_says("There's a Glowfit charge for 49.99 on Oct 2 I didn't make.")

    [case] = session.cases
    assert case.transaction_id == "s3"
    asks = [s for s in state["suggestions"] if s.kind is SuggestionKind.ASK]
    assert [s.field_name for s in asks] == ["card_in_possession"]
    # The agent's question was part of the transcript the model saw.
    assert "AGENT: How can I help?" in llm.calls[0][1]


def test_recurring_charge_raises_signal_question() -> None:
    session = IntakeSession(FakeLLM(Extraction(issues=[unauthorized()])), ACCOUNT, TODAY)
    state = session.customer_says("Glowfit charged me 49.99 on Oct 2, I never signed up.")

    [signal] = state["signals"][session.cases[0].case_id]
    assert signal.code == "recurring_subscription"
    assert SuggestionKind.SIGNAL in suggestion_kinds(session)


def test_case_completes_over_several_turns() -> None:
    llm = FakeLLM(
        Extraction(issues=[unauthorized()]),
        Extraction(issues=[unauthorized(card_in_possession="yes")]),
        Extraction(
            issues=[
                unauthorized(
                    card_in_possession="yes", recognizes_merchant="no", others_have_access="no"
                )
            ]
        ),
    )
    session = IntakeSession(llm, ACCOUNT, TODAY)

    session.customer_says("Glowfit charged me 49.99 on Oct 2.")
    session.agent_says("Do you still have your card?")
    session.customer_says("Yes.")
    session.agent_says("Do you recognize Glowfit, and has anyone else used your card?")
    session.customer_says("No and no.")

    assert SuggestionKind.COMPLETE in suggestion_kinds(session)
    [summary] = session.summaries()
    assert summary.is_complete
    assert summary.reason_code.code == "10.4"
    assert summary.transaction.transaction_id == "s3"
    assert [m.speaker for m in session.messages] == [
        Speaker.CUSTOMER,
        Speaker.AGENT,
        Speaker.CUSTOMER,
        Speaker.AGENT,
        Speaker.CUSTOMER,
    ]


def test_ambiguous_charge_asks_agent_to_pick_then_confirm() -> None:
    vague = ExtractedIssue(
        dispute_type=DisputeType.UNAUTHORIZED,
        merchant="Glowfit",
        amount=None,
        charge_date=None,
        facts=[],
    )
    session = IntakeSession(FakeLLM(Extraction(issues=[vague])), ACCOUNT, TODAY)

    state = session.customer_says("Something from Glowfit, not sure when.")
    case_id = session.cases[0].case_id
    assert state["candidates"][case_id] == ["s1", "s2", "s3"]
    assert SuggestionKind.PICK_TRANSACTION in suggestion_kinds(session)

    session.confirm_transaction(case_id, "s2")

    [case] = session.cases
    assert case.transaction_id == "s2"
    assert case.transaction_confirmed
    assert SuggestionKind.PICK_TRANSACTION not in suggestion_kinds(session)


def test_agent_fact_reruns_rules_without_llm() -> None:
    llm = FakeLLM(Extraction(issues=[unauthorized()]))  # only one response queued
    session = IntakeSession(llm, ACCOUNT, TODAY)
    session.customer_says("Glowfit, 49.99, Oct 2.")
    case_id = session.cases[0].case_id

    session.set_fact(case_id, "card_in_possession", "yes")

    [case] = session.cases
    assert case.facts["card_in_possession"].source is FactSource.AGENT
    asks = [s for s in session.state["suggestions"] if s.kind is SuggestionKind.ASK]
    assert [s.field_name for s in asks] == ["recognizes_merchant"]
    assert len(llm.calls) == 1


def test_set_fact_rejects_bad_input() -> None:
    session = IntakeSession(FakeLLM(Extraction(issues=[unauthorized()])), ACCOUNT, TODAY)
    session.customer_says("Glowfit, 49.99, Oct 2.")
    case_id = session.cases[0].case_id

    with pytest.raises(ValueError, match="not a field"):
        session.set_fact(case_id, "return_date", "2026-10-01")
    with pytest.raises(ValueError, match="not a valid value"):
        session.set_fact(case_id, "card_in_possession", "perhaps")


def test_two_disputes_in_one_conversation() -> None:
    refund = ExtractedIssue(
        dispute_type=DisputeType.CREDIT_NOT_PROCESSED,
        merchant="ShoeHub",
        amount=None,
        charge_date=None,
        facts=[ExtractedFact(name="return_method", value="mail")],
    )
    session = IntakeSession(FakeLLM(Extraction(issues=[unauthorized(), refund])), ACCOUNT, TODAY)

    session.customer_says("Glowfit charge I didn't make, and ShoeHub never refunded my return.")

    assert [c.dispute_type for c in session.cases] == [
        DisputeType.UNAUTHORIZED,
        DisputeType.CREDIT_NOT_PROCESSED,
    ]
    assert session.cases[1].transaction_id == "r1"
    assert len(session.summaries()) == 2
