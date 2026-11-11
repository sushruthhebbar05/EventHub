"""A fake payment gateway. No real money, no real card processing.

Test cards:
  any valid-looking number          -> approved
  4000 0000 0000 0002               -> declined
  4000 0000 0000 9995               -> declined (insufficient funds)
"""
import secrets
from dataclasses import dataclass

DECLINED = {
    "4000000000000002": "Your card was declined.",
    "4000000000009995": "Insufficient funds.",
}


@dataclass
class ChargeResult:
    approved: bool
    reference: str | None
    failure_reason: str | None


def charge(card_number: str, amount) -> ChargeResult:
    if card_number in DECLINED:
        return ChargeResult(False, None, DECLINED[card_number])
    return ChargeResult(True, "mock_" + secrets.token_hex(8), None)
