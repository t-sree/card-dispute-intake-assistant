import pytest

from card_dispute_intake.models import DisputeCase, DisputeType, FactSource
from card_dispute_intake.rules.checklists import CHECKLISTS, TRANSACTION, checklist_for


@pytest.mark.parametrize("dispute_type", list(DisputeType))
def test_every_dispute_type_has_a_checklist(dispute_type: DisputeType) -> None:
    assert checklist_for(dispute_type)


@pytest.mark.parametrize("dispute_type", list(DisputeType))
def test_transaction_is_asked_first(dispute_type: DisputeType) -> None:
    assert checklist_for(dispute_type)[0] is TRANSACTION


@pytest.mark.parametrize("dispute_type", list(DisputeType))
def test_field_names_are_unique(dispute_type: DisputeType) -> None:
    names = [field.name for field in CHECKLISTS[dispute_type]]
    assert len(names) == len(set(names))


def test_tracking_number_only_required_for_mailed_returns() -> None:
    tracking = next(
        f for f in checklist_for(DisputeType.CREDIT_NOT_PROCESSED) if f.name == "tracking_number"
    )
    case = DisputeCase(dispute_type=DisputeType.CREDIT_NOT_PROCESSED)

    case.set_fact("return_method", "in_store", FactSource.CUSTOMER)
    assert not tracking.applies_to(case)

    case.set_fact("return_method", "mail", FactSource.CUSTOMER)
    assert tracking.applies_to(case)
