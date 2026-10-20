"""Map dispute types to card network reason codes.

Mastercard folded most merchant disputes into a single code (4853, Cardholder Dispute)
in 2017, so several of our types share it. Visa keeps them separate.
"""

from dataclasses import dataclass

from card_dispute_intake.models import CardNetwork, DisputeType


@dataclass(frozen=True)
class ReasonCode:
    network: CardNetwork
    code: str
    description: str


_REASON_CODES: dict[tuple[CardNetwork, DisputeType], ReasonCode] = {
    (CardNetwork.VISA, DisputeType.UNAUTHORIZED): ReasonCode(
        CardNetwork.VISA, "10.4", "Other Fraud - Card-Absent Environment"
    ),
    (CardNetwork.VISA, DisputeType.NOT_RECEIVED): ReasonCode(
        CardNetwork.VISA, "13.1", "Merchandise/Services Not Received"
    ),
    (CardNetwork.VISA, DisputeType.CANCELLED_RECURRING): ReasonCode(
        CardNetwork.VISA, "13.2", "Cancelled Recurring Transaction"
    ),
    (CardNetwork.VISA, DisputeType.CREDIT_NOT_PROCESSED): ReasonCode(
        CardNetwork.VISA, "13.6", "Credit Not Processed"
    ),
    (CardNetwork.MASTERCARD, DisputeType.UNAUTHORIZED): ReasonCode(
        CardNetwork.MASTERCARD, "4837", "No Cardholder Authorization"
    ),
    (CardNetwork.MASTERCARD, DisputeType.NOT_RECEIVED): ReasonCode(
        CardNetwork.MASTERCARD, "4853", "Cardholder Dispute - Goods or Services Not Provided"
    ),
    (CardNetwork.MASTERCARD, DisputeType.CANCELLED_RECURRING): ReasonCode(
        CardNetwork.MASTERCARD, "4853", "Cardholder Dispute - Recurring Transaction Cancelled"
    ),
    (CardNetwork.MASTERCARD, DisputeType.CREDIT_NOT_PROCESSED): ReasonCode(
        CardNetwork.MASTERCARD, "4853", "Cardholder Dispute - Credit Not Processed"
    ),
}


def reason_code_for(network: CardNetwork, dispute_type: DisputeType) -> ReasonCode:
    return _REASON_CODES[(network, dispute_type)]
