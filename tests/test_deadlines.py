from datetime import date
from decimal import Decimal

from card_dispute_intake.models import DisputeCase, DisputeType, FactSource, Transaction
from card_dispute_intake.rules.deadlines import compute_deadlines

POSTED = date(2026, 9, 5)
STATEMENT = date(2026, 9, 30)
NOTICE = date(2026, 10, 10)

TXN = Transaction(
    transaction_id="txn_001", posted_date=POSTED, merchant="ShoeHub", amount=Decimal("89.00")
)


def test_regulation_z_deadlines() -> None:
    case = DisputeCase(dispute_type=DisputeType.UNAUTHORIZED, transaction_id="txn_001")

    deadlines = compute_deadlines(case, TXN, statement_date=STATEMENT, notice_date=NOTICE)

    assert deadlines.customer_notice_by == date(2026, 11, 29)
    assert deadlines.acknowledge_by == date(2026, 11, 9)
    assert deadlines.resolve_by == date(2027, 1, 8)


def test_chargeback_window_starts_at_posting_by_default() -> None:
    case = DisputeCase(dispute_type=DisputeType.UNAUTHORIZED, transaction_id="txn_001")

    deadlines = compute_deadlines(case, TXN, statement_date=STATEMENT, notice_date=NOTICE)

    assert deadlines.chargeback_by == date(2027, 1, 3)


def test_not_received_window_starts_at_expected_delivery() -> None:
    case = DisputeCase(dispute_type=DisputeType.NOT_RECEIVED, transaction_id="txn_001")
    case.set_fact("expected_delivery_date", date(2026, 10, 1), FactSource.CUSTOMER)

    deadlines = compute_deadlines(case, TXN, statement_date=STATEMENT, notice_date=NOTICE)

    assert deadlines.chargeback_by == date(2027, 1, 29)


def test_delayed_start_is_capped() -> None:
    case = DisputeCase(dispute_type=DisputeType.NOT_RECEIVED, transaction_id="txn_001")
    case.set_fact("expected_delivery_date", date(2028, 12, 1), FactSource.CUSTOMER)

    deadlines = compute_deadlines(case, TXN, statement_date=STATEMENT, notice_date=NOTICE)

    # 540 days after posting, then the 120-day window
    assert deadlines.chargeback_by == date(2028, 6, 26)


def test_expected_date_before_posting_is_ignored() -> None:
    case = DisputeCase(dispute_type=DisputeType.NOT_RECEIVED, transaction_id="txn_001")
    case.set_fact("expected_delivery_date", date(2026, 9, 1), FactSource.CUSTOMER)

    deadlines = compute_deadlines(case, TXN, statement_date=STATEMENT, notice_date=NOTICE)

    assert deadlines.chargeback_by == date(2027, 1, 3)


def test_credit_not_processed_window_starts_at_return_date() -> None:
    case = DisputeCase(dispute_type=DisputeType.CREDIT_NOT_PROCESSED, transaction_id="txn_001")
    case.set_fact("return_date", date(2026, 9, 15), FactSource.CUSTOMER)

    deadlines = compute_deadlines(case, TXN, statement_date=STATEMENT, notice_date=NOTICE)

    assert deadlines.chargeback_by == date(2027, 1, 13)
