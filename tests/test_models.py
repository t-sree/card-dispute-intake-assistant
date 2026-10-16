from datetime import date
from decimal import Decimal

import pytest
from pydantic import ValidationError

from card_dispute_intake.models import DisputeCase, DisputeType, FactSource, Transaction


def make_transaction(**overrides: object) -> Transaction:
    fields: dict[str, object] = {
        "transaction_id": "txn_001",
        "posted_date": date(2026, 9, 5),
        "merchant": "StreamFlix",
        "amount": Decimal("15.99"),
    }
    fields.update(overrides)
    return Transaction.model_validate(fields)


class TestTransaction:
    def test_amount_parsed_as_decimal(self) -> None:
        txn = make_transaction(amount="15.99")
        assert txn.amount == Decimal("15.99")

    @pytest.mark.parametrize("amount", ["0", "-10.00"])
    def test_rejects_non_positive_amount(self, amount: str) -> None:
        with pytest.raises(ValidationError):
            make_transaction(amount=amount)

    def test_rejects_unknown_fields(self) -> None:
        with pytest.raises(ValidationError):
            make_transaction(category="streaming")

    def test_is_immutable(self) -> None:
        txn = make_transaction()
        with pytest.raises(ValidationError):
            txn.amount = Decimal("1.00")  # type: ignore[misc]


class TestDisputeCase:
    def test_new_case_starts_empty(self) -> None:
        case = DisputeCase()
        assert case.case_id.startswith("case_")
        assert case.dispute_type is None
        assert case.facts == {}

    def test_case_ids_are_unique(self) -> None:
        assert DisputeCase().case_id != DisputeCase().case_id

    def test_set_and_get_fact(self) -> None:
        case = DisputeCase(dispute_type=DisputeType.UNAUTHORIZED)
        case.set_fact("card_in_possession", True, FactSource.CUSTOMER)

        assert case.has_fact("card_in_possession")
        assert case.get_value("card_in_possession") is True
        assert case.facts["card_in_possession"].source is FactSource.CUSTOMER

    def test_later_fact_replaces_earlier(self) -> None:
        case = DisputeCase()
        case.set_fact("return_date", date(2026, 9, 1), FactSource.CUSTOMER)
        case.set_fact("return_date", date(2026, 9, 3), FactSource.CUSTOMER)

        assert case.get_value("return_date") == date(2026, 9, 3)
        assert len(case.facts) == 1

    def test_missing_fact_returns_none(self) -> None:
        case = DisputeCase()
        assert not case.has_fact("merchant_contacted")
        assert case.get_value("merchant_contacted") is None
