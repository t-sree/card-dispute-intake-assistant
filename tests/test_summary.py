from datetime import date
from decimal import Decimal

from card_dispute_intake.data.accounts import Account
from card_dispute_intake.engine.summary import summarize
from card_dispute_intake.models import (
    CardNetwork,
    DisputeCase,
    DisputeType,
    FactSource,
    Transaction,
)

TODAY = date(2026, 10, 20)
ACCOUNT = Account(
    account_id="acct_1",
    network=CardNetwork.MASTERCARD,
    statement_day=20,
    transactions=[
        Transaction(
            transaction_id="t1",
            posted_date=date(2026, 10, 2),
            merchant="SHOEHUB.COM",
            amount=Decimal("120.00"),
        )
    ],
)


def test_no_summary_without_transaction() -> None:
    case = DisputeCase(dispute_type=DisputeType.CREDIT_NOT_PROCESSED)
    assert summarize(case, ACCOUNT, TODAY) is None


def test_no_summary_for_unknown_transaction() -> None:
    case = DisputeCase(dispute_type=DisputeType.CREDIT_NOT_PROCESSED, transaction_id="nope")
    assert summarize(case, ACCOUNT, TODAY) is None


def test_partial_summary_lists_missing_fields() -> None:
    case = DisputeCase(dispute_type=DisputeType.CREDIT_NOT_PROCESSED, transaction_id="t1")
    case.set_fact("return_date", date(2026, 10, 5), FactSource.CUSTOMER)

    summary = summarize(case, ACCOUNT, TODAY)

    assert summary is not None
    assert not summary.is_complete
    assert summary.missing[0] == "return_method"
    assert summary.reason_code.code == "4853"
    # Statement closes on the 20th, so the 60-day notice window runs from 2026-10-20.
    assert summary.deadlines.customer_notice_by == date(2026, 12, 19)
    assert summary.deadlines.acknowledge_by == date(2026, 11, 19)
    assert summary.facts["return_date"] == date(2026, 10, 5)
