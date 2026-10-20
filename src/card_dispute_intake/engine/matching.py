"""Find the disputed charge on the account from what the customer said.

Customers describe charges loosely ("the Glowfit thing, about fifty bucks, early October"),
while statements say "GLOWFIT*MEMBERSHIP 800-555". We score every transaction on merchant
name, amount and date, and only auto-select when one candidate clearly wins. Otherwise the
agent picks from the shortlist.
"""

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from difflib import SequenceMatcher

from card_dispute_intake.data.accounts import Account
from card_dispute_intake.models import Transaction

MIN_SCORE = 0.6
CLEAR_WINNER_MARGIN = 0.15
SHORTLIST_SIZE = 3
DATE_TOLERANCE_DAYS = 3
MIN_NAME_LENGTH = 3


@dataclass(frozen=True)
class MatchResult:
    transaction: Transaction | None
    candidates: tuple[Transaction, ...]


def _normalize(name: str) -> str:
    """Letters only, so "Shoe Hub" and "SHOEHUB.COM" compare as "shoehub" / "shoehubcom"."""
    return re.sub(r"[^a-z]", "", name.lower())


def _merchant_score(said: str, posted: str) -> float:
    said_n, posted_n = _normalize(said), _normalize(posted)
    if len(said_n) < MIN_NAME_LENGTH or not posted_n:
        return 0.0
    if said_n in posted_n:
        return 1.0
    return SequenceMatcher(None, said_n, posted_n).ratio()


def _date_score(said: date, posted: date) -> float:
    days_apart = abs((posted - said).days)
    return max(0.0, 1 - days_apart / (DATE_TOLERANCE_DAYS + 1))


def _score(
    txn: Transaction, merchant: str | None, amount: Decimal | None, charge_date: date | None
) -> float:
    parts: list[tuple[float, float]] = []  # (weight, score)
    if merchant:
        parts.append((0.5, _merchant_score(merchant, txn.merchant)))
    if amount is not None:
        parts.append((0.35, 1.0 if txn.amount == amount else 0.0))
    if charge_date is not None:
        parts.append((0.15, _date_score(charge_date, txn.posted_date)))
    total_weight = sum(w for w, _ in parts)
    return sum(w * s for w, s in parts) / total_weight


def match_transaction(
    account: Account,
    merchant: str | None,
    amount: Decimal | None,
    charge_date: date | None,
) -> MatchResult:
    if not (merchant or amount is not None or charge_date is not None):
        return MatchResult(transaction=None, candidates=())

    scored = sorted(
        ((_score(t, merchant, amount, charge_date), t) for t in account.transactions),
        key=lambda pair: (-pair[0], pair[1].posted_date),
    )
    shortlist = [(s, t) for s, t in scored if s >= MIN_SCORE][:SHORTLIST_SIZE]
    if not shortlist:
        return MatchResult(transaction=None, candidates=())

    best_score, best = shortlist[0]
    runner_up = shortlist[1][0] if len(shortlist) > 1 else 0.0
    if best_score - runner_up >= CLEAR_WINNER_MARGIN:
        return MatchResult(transaction=best, candidates=(best,))
    return MatchResult(transaction=None, candidates=tuple(t for _, t in shortlist))
