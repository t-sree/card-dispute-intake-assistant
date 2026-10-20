from datetime import date
from decimal import Decimal

from card_dispute_intake.models import DisputeCase, DisputeType, Transaction
from card_dispute_intake.rules.signals import detect_signals


def txn(tid: str, posted: date, merchant: str, recurring: bool = False) -> Transaction:
    return Transaction(
        transaction_id=tid,
        posted_date=posted,
        merchant=merchant,
        amount=Decimal("15.99"),
        is_recurring=recurring,
    )


SUB_JULY = txn("s1", date(2026, 7, 5), "STREAMFLIX", recurring=True)
SUB_AUG = txn("s2", date(2026, 8, 5), "STREAMFLIX", recurring=True)
SUB_SEP = txn("s3", date(2026, 9, 5), "STREAMFLIX", recurring=True)
SHOP_1 = txn("m1", date(2026, 8, 1), "MEGASTORE ONLINE")
SHOP_2 = txn("m2", date(2026, 9, 12), "MEGASTORE ONLINE")
HISTORY = [SUB_JULY, SHOP_1, SUB_AUG, SUB_SEP, SHOP_2]

FRAUD_CASE = DisputeCase(dispute_type=DisputeType.UNAUTHORIZED)


def test_recurring_charge_disputed_as_fraud() -> None:
    [signal] = detect_signals(FRAUD_CASE, SUB_SEP, HISTORY)

    assert signal.code == "recurring_subscription"
    assert "billed 2 time(s) before since 2026-07-05" in signal.message
    assert "free trial" in signal.question


def test_prior_one_off_charges_at_same_merchant() -> None:
    [signal] = detect_signals(FRAUD_CASE, SHOP_2, HISTORY)
    assert signal.code == "prior_undisputed_charges"


def test_first_ever_charge_has_no_signal() -> None:
    assert detect_signals(FRAUD_CASE, SUB_JULY, HISTORY) == []


def test_no_transaction_no_signal() -> None:
    assert detect_signals(FRAUD_CASE, None, HISTORY) == []


def test_only_unauthorized_disputes_are_checked() -> None:
    case = DisputeCase(dispute_type=DisputeType.CANCELLED_RECURRING)
    assert detect_signals(case, SUB_SEP, HISTORY) == []
