"""Account-history signals worth one or two extra questions.

These are prompts for the agent, not accusations. Wording stays neutral because most
customers who don't recognize a charge are simply confused, for example by a renewal they
forgot about or a billing name that differs from the brand they know.
"""

from dataclasses import dataclass

from card_dispute_intake.models import DisputeCase, DisputeType, Transaction


@dataclass(frozen=True)
class Signal:
    code: str
    message: str
    question: str


def _earlier_charges(transaction: Transaction, history: list[Transaction]) -> list[Transaction]:
    return [
        t
        for t in history
        if t.merchant == transaction.merchant
        and t.posted_date < transaction.posted_date
        and t.transaction_id != transaction.transaction_id
    ]


def detect_signals(
    case: DisputeCase, transaction: Transaction | None, history: list[Transaction]
) -> list[Signal]:
    if case.dispute_type is not DisputeType.UNAUTHORIZED or transaction is None:
        return []

    earlier = _earlier_charges(transaction, history)
    if not earlier:
        return []

    first = min(t.posted_date for t in earlier)
    if transaction.is_recurring:
        return [
            Signal(
                code="recurring_subscription",
                message=(
                    f"This charge matches a recurring {transaction.merchant} subscription, "
                    f"billed {len(earlier)} time(s) before since {first.isoformat()} "
                    "without a dispute."
                ),
                question=(
                    f"I can see {transaction.merchant} has billed this card monthly since "
                    f"{first:%B %d}. Could this be a subscription or free trial that renewed?"
                ),
            )
        ]
    return [
        Signal(
            code="prior_undisputed_charges",
            message=(
                f"{len(earlier)} earlier charge(s) from {transaction.merchant} since "
                f"{first.isoformat()} were not disputed."
            ),
            question=f"Have you shopped with {transaction.merchant} before on this card?",
        )
    ]
