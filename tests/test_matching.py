from datetime import date
from decimal import Decimal

from card_dispute_intake.data.accounts import Account
from card_dispute_intake.engine.matching import match_transaction
from card_dispute_intake.models import CardNetwork, Transaction


def txn(tid: str, posted: date, merchant: str, amount: str) -> Transaction:
    return Transaction(
        transaction_id=tid, posted_date=posted, merchant=merchant, amount=Decimal(amount)
    )


ACCOUNT = Account(
    account_id="acct_1",
    network=CardNetwork.VISA,
    statement_day=20,
    transactions=[
        txn("t1", date(2026, 9, 2), "GLOWFIT*MEMBERSHIP 800-555", "49.99"),
        txn("t2", date(2026, 10, 2), "GLOWFIT*MEMBERSHIP 800-555", "49.99"),
        txn("t3", date(2026, 10, 3), "FRESHMART GROCERY", "82.10"),
        txn("t4", date(2026, 10, 5), "SHOEHUB.COM", "120.00"),
        txn("t5", date(2026, 10, 9), "BEAN THERE COFFEE", "6.50"),
    ],
)


def test_no_details_no_match() -> None:
    result = match_transaction(ACCOUNT, None, None, None)
    assert result.transaction is None
    assert result.candidates == ()


def test_unique_merchant_is_matched() -> None:
    result = match_transaction(ACCOUNT, "ShoeHub", None, None)
    assert result.transaction is not None
    assert result.transaction.transaction_id == "t4"


def test_repeated_merchant_without_date_is_ambiguous() -> None:
    result = match_transaction(ACCOUNT, "Glowfit", Decimal("49.99"), None)
    assert result.transaction is None
    assert [t.transaction_id for t in result.candidates] == ["t1", "t2"]


def test_date_breaks_the_tie() -> None:
    result = match_transaction(ACCOUNT, "Glowfit", Decimal("49.99"), date(2026, 10, 2))
    assert result.transaction is not None
    assert result.transaction.transaction_id == "t2"


def test_amount_alone_can_match() -> None:
    result = match_transaction(ACCOUNT, None, Decimal("82.10"), None)
    assert result.transaction is not None
    assert result.transaction.transaction_id == "t3"


def test_unknown_merchant_no_match() -> None:
    result = match_transaction(ACCOUNT, "Totally Unknown Store", None, None)
    assert result.transaction is None
    assert result.candidates == ()


def test_slightly_misspelled_merchant_still_matches() -> None:
    result = match_transaction(ACCOUNT, "Shoe Hub", Decimal("120.00"), None)
    assert result.transaction is not None
    assert result.transaction.transaction_id == "t4"


def test_very_short_name_does_not_match_everything() -> None:
    result = match_transaction(ACCOUNT, "A", None, None)
    assert result.candidates == ()
