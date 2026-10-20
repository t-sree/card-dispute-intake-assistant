"""Synthetic card accounts with realistic transaction history.

Each account gets a few monthly subscriptions plus everyday purchases. Generation is seeded,
so the same seed always produces the same account, which keeps tests and evals repeatable.
"""

import random
from datetime import date, timedelta
from decimal import Decimal

from pydantic import BaseModel, Field

from card_dispute_intake.models import CardNetwork, Transaction

SUBSCRIPTIONS: dict[str, Decimal] = {
    "STREAMFLIX": Decimal("15.99"),
    "TUNEBOX MUSIC": Decimal("10.99"),
    "CLOUDVAULT STORAGE": Decimal("2.99"),
    "IRONWORKS GYM": Decimal("39.00"),
    "DAILY HERALD DIGITAL": Decimal("8.00"),
    "MEALKIT EXPRESS": Decimal("69.94"),
}

# merchant -> (min, max) amount in dollars
EVERYDAY_MERCHANTS: dict[str, tuple[int, int]] = {
    "FRESHMART GROCERY": (18, 160),
    "QUICKFUEL #2231": (25, 70),
    "BEAN THERE COFFEE": (4, 14),
    "MEGASTORE ONLINE": (12, 240),
    "CORNER PHARMACY": (6, 55),
    "TACO TOWN": (9, 32),
    "RIDEQUICK TRIP": (8, 45),
    "HOMEGOODS DEPOT": (20, 310),
    "SHOEHUB.COM": (45, 180),
    "CITY PARKING": (3, 20),
}


class Account(BaseModel):
    account_id: str
    network: CardNetwork
    statement_day: int = Field(ge=1, le=28)
    transactions: list[Transaction]

    def find(self, transaction_id: str) -> Transaction | None:
        return next((t for t in self.transactions if t.transaction_id == transaction_id), None)

    def statement_date_for(self, posted: date) -> date:
        """The first statement closing date on or after the posting date."""
        closing = posted.replace(day=self.statement_day)
        if closing >= posted:
            return closing
        next_month = (closing.replace(day=1) + timedelta(days=32)).replace(day=self.statement_day)
        return next_month


def _monthly_dates(day: int, start: date, end: date) -> list[date]:
    dates = []
    current = start.replace(day=day)
    while current <= end:
        if current >= start:
            dates.append(current)
        current = (current.replace(day=1) + timedelta(days=32)).replace(day=day)
    return dates


def generate_account(seed: int, end_date: date, days: int = 90) -> Account:
    rng = random.Random(seed)
    start_date = end_date - timedelta(days=days)
    drafts: list[tuple[date, str, Decimal, bool]] = []

    for merchant in rng.sample(sorted(SUBSCRIPTIONS), k=rng.randint(2, 4)):
        billing_day = rng.randint(1, 28)
        for posted in _monthly_dates(billing_day, start_date, end_date):
            drafts.append((posted, merchant, SUBSCRIPTIONS[merchant], True))

    for offset in range(days + 1):
        posted = start_date + timedelta(days=offset)
        for _ in range(rng.choice([0, 0, 1, 1, 1, 2])):
            merchant = rng.choice(sorted(EVERYDAY_MERCHANTS))
            low, high = EVERYDAY_MERCHANTS[merchant]
            amount = Decimal(rng.randint(low * 100, high * 100)) / 100
            drafts.append((posted, merchant, amount, False))

    drafts.sort(key=lambda d: (d[0], d[1]))
    transactions = [
        Transaction(
            transaction_id=f"txn_{seed}_{i:04d}",
            posted_date=posted,
            merchant=merchant,
            amount=amount,
            is_recurring=recurring,
        )
        for i, (posted, merchant, amount, recurring) in enumerate(drafts)
    ]
    return Account(
        account_id=f"acct_{seed}",
        network=rng.choice(list(CardNetwork)),
        statement_day=rng.randint(1, 28),
        transactions=transactions,
    )
