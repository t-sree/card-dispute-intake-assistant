"""Final case output for the agent to review and submit."""

from dataclasses import dataclass
from datetime import date

from card_dispute_intake.data.accounts import Account
from card_dispute_intake.models import DisputeCase, DisputeType, FactValue, Transaction
from card_dispute_intake.rules.checker import check_case
from card_dispute_intake.rules.deadlines import Deadlines, compute_deadlines
from card_dispute_intake.rules.reason_codes import ReasonCode, reason_code_for


@dataclass(frozen=True)
class CaseSummary:
    case_id: str
    dispute_type: DisputeType
    transaction: Transaction
    reason_code: ReasonCode
    deadlines: Deadlines
    facts: dict[str, FactValue]
    missing: tuple[str, ...]

    @property
    def is_complete(self) -> bool:
        return not self.missing


def summarize(case: DisputeCase, account: Account, today: date) -> CaseSummary | None:
    """None until we know both the dispute type and the transaction."""
    if case.dispute_type is None or case.transaction_id is None:
        return None
    transaction = account.find(case.transaction_id)
    if transaction is None:
        return None

    return CaseSummary(
        case_id=case.case_id,
        dispute_type=case.dispute_type,
        transaction=transaction,
        reason_code=reason_code_for(account.network, case.dispute_type),
        deadlines=compute_deadlines(
            case,
            transaction,
            statement_date=account.statement_date_for(transaction.posted_date),
            notice_date=today,
        ),
        facts={name: fact.value for name, fact in case.facts.items()},
        missing=tuple(f.name for f in check_case(case).missing),
    )
