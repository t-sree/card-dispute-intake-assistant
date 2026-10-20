from datetime import date

import pytest

from card_dispute_intake.models import DisputeCase, DisputeType, FactSource
from card_dispute_intake.rules.checklists import (
    CHECKLISTS,
    TRANSACTION,
    RequiredField,
    checklist_for,
)


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


def field(dispute_type: DisputeType, name: str) -> RequiredField:
    return next(f for f in checklist_for(dispute_type) if f.name == name)


@pytest.mark.parametrize(("raw", "expected"), [("yes", True), (" No ", False), ("maybe", None)])
def test_parse_yes_no(raw: str, expected: bool | None) -> None:
    assert field(DisputeType.UNAUTHORIZED, "card_in_possession").parse(raw) is expected


def test_parse_date() -> None:
    return_date = field(DisputeType.CREDIT_NOT_PROCESSED, "return_date")
    assert return_date.parse("2026-09-03") == date(2026, 9, 3)
    assert return_date.parse("early September") is None


def test_parse_choice() -> None:
    method = field(DisputeType.CREDIT_NOT_PROCESSED, "return_method")
    assert method.parse("Mail") == "mail"
    assert method.parse("courier") is None


def test_parse_text_rejects_blank() -> None:
    item = field(DisputeType.NOT_RECEIVED, "item_description")
    assert item.parse("  running shoes ") == "running shoes"
    assert item.parse("   ") is None
