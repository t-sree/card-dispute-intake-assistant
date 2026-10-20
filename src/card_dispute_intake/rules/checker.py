"""Compare a case against its checklist and report what is still missing."""

from dataclasses import dataclass

from card_dispute_intake.models import DisputeCase
from card_dispute_intake.rules.checklists import TRANSACTION, RequiredField, checklist_for


@dataclass(frozen=True)
class CheckResult:
    missing: tuple[RequiredField, ...]

    @property
    def is_complete(self) -> bool:
        return not self.missing

    @property
    def next_field(self) -> RequiredField | None:
        return self.missing[0] if self.missing else None


def _is_present(case: DisputeCase, field: RequiredField) -> bool:
    # The disputed transaction lives on the case itself rather than in facts.
    if field is TRANSACTION:
        return case.transaction_id is not None
    return case.has_fact(field.name)


def check_case(case: DisputeCase) -> CheckResult:
    if case.dispute_type is None:
        raise ValueError(f"{case.case_id} has no dispute type yet; classify it before checking")

    missing = tuple(
        field
        for field in checklist_for(case.dispute_type)
        if field.applies_to(case) and not _is_present(case, field)
    )
    return CheckResult(missing=missing)
