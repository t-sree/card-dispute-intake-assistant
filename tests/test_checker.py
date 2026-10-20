from datetime import date

import pytest

from card_dispute_intake.models import DisputeCase, DisputeType, FactSource
from card_dispute_intake.rules.checker import check_case


def missing_names(case: DisputeCase) -> list[str]:
    return [field.name for field in check_case(case).missing]


def test_requires_dispute_type() -> None:
    with pytest.raises(ValueError, match="no dispute type"):
        check_case(DisputeCase())


def test_new_case_is_missing_everything_unconditional() -> None:
    case = DisputeCase(dispute_type=DisputeType.UNAUTHORIZED)
    assert missing_names(case) == [
        "transaction_id",
        "card_in_possession",
        "recognizes_merchant",
        "others_have_access",
    ]


def test_complete_fraud_case() -> None:
    case = DisputeCase(dispute_type=DisputeType.UNAUTHORIZED, transaction_id="txn_001")
    case.set_fact("card_in_possession", True, FactSource.CUSTOMER)
    case.set_fact("recognizes_merchant", False, FactSource.CUSTOMER)
    case.set_fact("others_have_access", False, FactSource.CUSTOMER)

    result = check_case(case)

    assert result.is_complete
    assert result.next_field is None


def test_next_field_follows_checklist_order() -> None:
    case = DisputeCase(dispute_type=DisputeType.NOT_RECEIVED, transaction_id="txn_002")
    case.set_fact("item_description", "running shoes", FactSource.CUSTOMER)

    next_field = check_case(case).next_field

    assert next_field is not None
    assert next_field.name == "expected_delivery_date"


def test_merchant_follow_ups_skipped_when_not_contacted() -> None:
    case = DisputeCase(dispute_type=DisputeType.NOT_RECEIVED, transaction_id="txn_002")
    case.set_fact("item_description", "running shoes", FactSource.CUSTOMER)
    case.set_fact("expected_delivery_date", date(2026, 9, 20), FactSource.CUSTOMER)
    case.set_fact("merchant_contacted", False, FactSource.CUSTOMER)

    assert check_case(case).is_complete


def test_merchant_follow_ups_required_when_contacted() -> None:
    case = DisputeCase(dispute_type=DisputeType.NOT_RECEIVED, transaction_id="txn_002")
    case.set_fact("item_description", "running shoes", FactSource.CUSTOMER)
    case.set_fact("expected_delivery_date", date(2026, 9, 20), FactSource.CUSTOMER)
    case.set_fact("merchant_contacted", True, FactSource.CUSTOMER)

    assert missing_names(case) == ["merchant_contact_date", "merchant_response"]


def test_account_sourced_facts_count_as_present() -> None:
    case = DisputeCase(dispute_type=DisputeType.CANCELLED_RECURRING, transaction_id="txn_003")
    case.set_fact("cancellation_date", date(2026, 8, 28), FactSource.ACCOUNT)

    assert "cancellation_date" not in missing_names(case)
