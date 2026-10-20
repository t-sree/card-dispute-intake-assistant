"""Rough keyword tagging of complaints into our dispute types.

Only used to pick a balanced sample of complaints to simulate conversations from. It is
deliberately simple and noisy; accuracy is measured against hand labels, never against this.
"""

import re

from card_dispute_intake.data.complaints import Complaint
from card_dispute_intake.models import DisputeType

UNAUTHORIZED_SUB_ISSUE = "Card was charged for something you did not purchase with the card"

_RECURRING = re.compile(r"subscription|membership|recurring|auto-?renew|renewal|monthly fee")
_CANCEL = re.compile(r"cancel")
_NOT_RECEIVED = re.compile(
    r"never (received|arrived|got|delivered)|not (been )?(received|delivered)"
    r"|did ?n[o']t (receive|arrive|get)|non-?delivery"
)
_RETURNED = re.compile(r"\breturn(ed)?\b|sent (it|them|the \w+) back|shipped (it|them) back")
_NO_CREDIT = re.compile(r"refund|credit")


def guess_dispute_type(complaint: Complaint) -> DisputeType | None:
    if complaint.sub_issue == UNAUTHORIZED_SUB_ISSUE:
        return DisputeType.UNAUTHORIZED

    text = complaint.narrative.lower()
    if _RECURRING.search(text) and _CANCEL.search(text):
        return DisputeType.CANCELLED_RECURRING
    if _NOT_RECEIVED.search(text):
        return DisputeType.NOT_RECEIVED
    if _RETURNED.search(text) and _NO_CREDIT.search(text):
        return DisputeType.CREDIT_NOT_PROCESSED
    return None
