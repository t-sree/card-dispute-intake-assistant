"""Regulatory and network deadlines for a dispute.

Simplified on purpose: real issuers track billing cycles and many per-code exceptions.
- Reg Z (12 CFR 1026.13): the customer has 60 days from the statement that first showed
  the charge to notify the bank. The bank must acknowledge within 30 days and resolve within
  two billing cycles, capped at 90 days.
- Networks: most chargebacks must be filed within 120 days. For goods not received, Visa
  starts the clock at the expected delivery date (capped at 540 days from processing), and
  for credit not processed, at the return date.
"""

from dataclasses import dataclass
from datetime import date, timedelta

from card_dispute_intake.models import DisputeCase, DisputeType, Transaction

CUSTOMER_NOTICE_DAYS = 60
ACKNOWLEDGE_DAYS = 30
RESOLVE_DAYS = 90
CHARGEBACK_DAYS = 120
MAX_DELAYED_START_DAYS = 540


@dataclass(frozen=True)
class Deadlines:
    customer_notice_by: date
    acknowledge_by: date
    resolve_by: date
    chargeback_by: date


def _date_fact(case: DisputeCase, name: str) -> date | None:
    value = case.get_value(name)
    return value if isinstance(value, date) else None


def _chargeback_start(case: DisputeCase, transaction: Transaction) -> date:
    delayed_start = None
    if case.dispute_type is DisputeType.NOT_RECEIVED:
        delayed_start = _date_fact(case, "expected_delivery_date")
    elif case.dispute_type is DisputeType.CREDIT_NOT_PROCESSED:
        delayed_start = _date_fact(case, "return_date")

    if delayed_start is None or delayed_start <= transaction.posted_date:
        return transaction.posted_date
    latest_allowed = transaction.posted_date + timedelta(days=MAX_DELAYED_START_DAYS)
    return min(delayed_start, latest_allowed)


def compute_deadlines(
    case: DisputeCase,
    transaction: Transaction,
    statement_date: date,
    notice_date: date,
) -> Deadlines:
    """statement_date: when the charge first appeared on a statement.
    notice_date: when the customer reported the dispute (usually today)."""
    return Deadlines(
        customer_notice_by=statement_date + timedelta(days=CUSTOMER_NOTICE_DAYS),
        acknowledge_by=notice_date + timedelta(days=ACKNOWLEDGE_DAYS),
        resolve_by=notice_date + timedelta(days=RESOLVE_DAYS),
        chargeback_by=_chargeback_start(case, transaction) + timedelta(days=CHARGEBACK_DAYS),
    )
