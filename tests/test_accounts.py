from collections import defaultdict
from datetime import date

from card_dispute_intake.data.accounts import Account, generate_account
from card_dispute_intake.models import CardNetwork

END = date(2026, 10, 15)


def test_same_seed_same_account() -> None:
    assert generate_account(7, END) == generate_account(7, END)


def test_different_seeds_differ() -> None:
    assert generate_account(1, END) != generate_account(2, END)


def test_transactions_within_window_and_sorted() -> None:
    account = generate_account(3, END, days=60)
    dates = [t.posted_date for t in account.transactions]

    assert dates == sorted(dates)
    assert min(dates) >= date(2026, 8, 16)
    assert max(dates) <= END


def test_transaction_ids_unique() -> None:
    ids = [t.transaction_id for t in generate_account(4, END).transactions]
    assert len(ids) == len(set(ids))


def test_subscriptions_bill_monthly_on_same_day() -> None:
    account = generate_account(5, END, days=90)
    by_merchant: dict[str, list[date]] = defaultdict(list)
    for t in account.transactions:
        if t.is_recurring:
            by_merchant[t.merchant].append(t.posted_date)

    assert 2 <= len(by_merchant) <= 4
    for dates in by_merchant.values():
        assert len({d.day for d in dates}) == 1
        assert len(dates) >= 3


def test_find_transaction() -> None:
    account = generate_account(6, END)
    first = account.transactions[0]
    assert account.find(first.transaction_id) == first
    assert account.find("missing") is None


def test_statement_date_same_month_when_before_closing() -> None:
    account = Account(account_id="a", network=CardNetwork.VISA, statement_day=20, transactions=[])
    assert account.statement_date_for(date(2026, 9, 5)) == date(2026, 9, 20)
    assert account.statement_date_for(date(2026, 9, 20)) == date(2026, 9, 20)


def test_statement_date_rolls_to_next_month() -> None:
    account = Account(account_id="a", network=CardNetwork.VISA, statement_day=20, transactions=[])
    assert account.statement_date_for(date(2026, 9, 25)) == date(2026, 10, 20)
    assert account.statement_date_for(date(2026, 12, 28)) == date(2027, 1, 20)
