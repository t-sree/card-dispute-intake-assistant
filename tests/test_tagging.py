import pytest

from card_dispute_intake.data.complaints import Complaint
from card_dispute_intake.data.tagging import UNAUTHORIZED_SUB_ISSUE, guess_dispute_type
from card_dispute_intake.models import DisputeType

RESOLVING_SUB_ISSUE = (
    "Credit card company isn't resolving a dispute about a purchase on your statement"
)


def complaint(narrative: str, sub_issue: str = RESOLVING_SUB_ISSUE) -> Complaint:
    return Complaint(
        complaint_id="1",
        date_received="2024-01-01",
        product="Credit card",
        issue="Problem with a purchase shown on your statement",
        sub_issue=sub_issue,
        company="Example Bank",
        narrative=narrative,
    )


def test_unauthorized_comes_from_sub_issue() -> None:
    c = complaint("I returned nothing, this is not my charge", sub_issue=UNAUTHORIZED_SUB_ISSUE)
    assert guess_dispute_type(c) is DisputeType.UNAUTHORIZED


@pytest.mark.parametrize(
    ("narrative", "expected"),
    [
        (
            "I cancelled my gym membership in May but they kept charging me.",
            DisputeType.CANCELLED_RECURRING,
        ),
        ("The subscription auto-renewed after I canceled.", DisputeType.CANCELLED_RECURRING),
        ("I ordered a lawnmower and never received it.", DisputeType.NOT_RECEIVED),
        (
            "The package was not delivered and the seller stopped replying.",
            DisputeType.NOT_RECEIVED,
        ),
        (
            "I returned the jacket on March 3 and still have no refund.",
            DisputeType.CREDIT_NOT_PROCESSED,
        ),
        (
            "I shipped it back with tracking and was never credited.",
            DisputeType.CREDIT_NOT_PROCESSED,
        ),
    ],
)
def test_keyword_rules(narrative: str, expected: DisputeType) -> None:
    assert guess_dispute_type(complaint(narrative)) is expected


def test_unrelated_complaint_is_untagged() -> None:
    c = complaint("The car repair was botched and the shop refuses to fix it again.")
    assert guess_dispute_type(c) is None


def test_refund_without_return_is_not_credit_not_processed() -> None:
    c = complaint("The restaurant overcharged me and I asked for a refund.")
    assert guess_dispute_type(c) is None
