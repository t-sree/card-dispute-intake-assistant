import pytest

from card_dispute_intake.models import CardNetwork, DisputeType
from card_dispute_intake.rules.reason_codes import reason_code_for


@pytest.mark.parametrize("network", list(CardNetwork))
@pytest.mark.parametrize("dispute_type", list(DisputeType))
def test_every_combination_has_a_code(network: CardNetwork, dispute_type: DisputeType) -> None:
    code = reason_code_for(network, dispute_type)
    assert code.network is network
    assert code.code


@pytest.mark.parametrize(
    ("network", "dispute_type", "expected"),
    [
        (CardNetwork.VISA, DisputeType.UNAUTHORIZED, "10.4"),
        (CardNetwork.VISA, DisputeType.CREDIT_NOT_PROCESSED, "13.6"),
        (CardNetwork.MASTERCARD, DisputeType.UNAUTHORIZED, "4837"),
        (CardNetwork.MASTERCARD, DisputeType.NOT_RECEIVED, "4853"),
    ],
)
def test_known_codes(network: CardNetwork, dispute_type: DisputeType, expected: str) -> None:
    assert reason_code_for(network, dispute_type).code == expected
