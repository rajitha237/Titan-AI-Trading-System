from __future__ import annotations

from dataclasses import asdict, dataclass
from math import isfinite
from typing import Any


MAX_ACCOUNT_EXPOSURE_PERCENT = 25.0
MIN_FREE_BALANCE_PERCENT = 40.0
MINIMUM_ACCOUNT_BALANCE_USDT = 30.0


@dataclass(frozen=True)
class AccountProtectionResult:
    allowed: bool
    reason: str

    balance: float
    available_balance: float

    maximum_exposure_usdt: float
    requested_position_usdt: float
    required_margin_usdt: float

    exchange_minimum_notional: float

    minimum_free_balance_usdt: float
    remaining_available_balance_usdt: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _validate_non_negative_number(
    name: str,
    value: float,
) -> float:
    try:
        number = float(value)

    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{name} must be a valid number"
        ) from exc

    if not isfinite(number):
        raise ValueError(
            f"{name} must be finite"
        )

    if number < 0:
        raise ValueError(
            f"{name} cannot be negative"
        )

    return number


def evaluate_account_protection(
    balance: float,
    available_balance: float,
    requested_position_usdt: float,
    required_margin_usdt: float,
    exchange_minimum_notional: float,
    max_account_exposure_percent: float = (
        MAX_ACCOUNT_EXPOSURE_PERCENT
    ),
    min_free_balance_percent: float = (
        MIN_FREE_BALANCE_PERCENT
    ),
    minimum_account_balance_usdt: float = (
        MINIMUM_ACCOUNT_BALANCE_USDT
    ),
) -> dict[str, Any]:
    """
    Decide whether a new trade is safe for the account.

    Important distinctions:

    - requested_position_usdt is the full leveraged position notional.
    - required_margin_usdt is the amount expected to be reserved from
      the available account balance.

    This function never increases a position merely to satisfy an
    exchange minimum. If the exchange minimum exceeds the configured
    safe account exposure, the trade is rejected.
    """

    balance = _validate_non_negative_number(
        "balance",
        balance,
    )

    available_balance = _validate_non_negative_number(
        "available_balance",
        available_balance,
    )

    requested_position_usdt = _validate_non_negative_number(
        "requested_position_usdt",
        requested_position_usdt,
    )

    required_margin_usdt = _validate_non_negative_number(
        "required_margin_usdt",
        required_margin_usdt,
    )

    exchange_minimum_notional = _validate_non_negative_number(
        "exchange_minimum_notional",
        exchange_minimum_notional,
    )

    max_account_exposure_percent = (
        _validate_non_negative_number(
            "max_account_exposure_percent",
            max_account_exposure_percent,
        )
    )

    min_free_balance_percent = (
        _validate_non_negative_number(
            "min_free_balance_percent",
            min_free_balance_percent,
        )
    )

    minimum_account_balance_usdt = (
        _validate_non_negative_number(
            "minimum_account_balance_usdt",
            minimum_account_balance_usdt,
        )
    )

    if max_account_exposure_percent > 100:
        raise ValueError(
            "max_account_exposure_percent cannot exceed 100"
        )

    if min_free_balance_percent > 100:
        raise ValueError(
            "min_free_balance_percent cannot exceed 100"
        )

    maximum_exposure_usdt = (
        balance
        * max_account_exposure_percent
        / 100.0
    )

    minimum_free_balance_usdt = (
        balance
        * min_free_balance_percent
        / 100.0
    )

    # Futures available balance is reduced by margin, not by the full
    # leveraged position notional.
    remaining_available_balance_usdt = (
        available_balance - required_margin_usdt
    )

    def build_result(
        allowed: bool,
        reason: str,
    ) -> dict[str, Any]:
        result = AccountProtectionResult(
            allowed=allowed,
            reason=reason,

            balance=round(
                balance,
                8,
            ),
            available_balance=round(
                available_balance,
                8,
            ),

            maximum_exposure_usdt=round(
                maximum_exposure_usdt,
                8,
            ),
            requested_position_usdt=round(
                requested_position_usdt,
                8,
            ),
            required_margin_usdt=round(
                required_margin_usdt,
                8,
            ),

            exchange_minimum_notional=round(
                exchange_minimum_notional,
                8,
            ),

            minimum_free_balance_usdt=round(
                minimum_free_balance_usdt,
                8,
            ),
            remaining_available_balance_usdt=round(
                remaining_available_balance_usdt,
                8,
            ),
        )

        return result.to_dict()

    if balance < minimum_account_balance_usdt:
        return build_result(
            False,
            (
                "Account balance is below the configured minimum "
                f"of {minimum_account_balance_usdt:.2f} USDT"
            ),
        )

    if available_balance <= 0:
        return build_result(
            False,
            "No available balance is available for a new trade",
        )

    if requested_position_usdt <= 0:
        return build_result(
            False,
            "Requested position size must be greater than zero",
        )

    if required_margin_usdt <= 0:
        return build_result(
            False,
            "Required margin must be greater than zero",
        )

    if exchange_minimum_notional <= 0:
        return build_result(
            False,
            "Exchange minimum notional is invalid",
        )

    # Account safety has priority over the exchange minimum.
    if exchange_minimum_notional > maximum_exposure_usdt:
        return build_result(
            False,
            (
                "Exchange minimum notional exceeds the configured "
                "maximum account exposure"
            ),
        )

    # Never increase the requested trade just to meet exchange rules.
    if requested_position_usdt < exchange_minimum_notional:
        return build_result(
            False,
            (
                "Requested position is below the exchange minimum "
                "notional; position size will not be force-increased"
            ),
        )

    if requested_position_usdt > maximum_exposure_usdt:
        return build_result(
            False,
            (
                "Requested position exceeds the configured maximum "
                "account exposure"
            ),
        )

    # Available account balance is checked against margin, not notional.
    if required_margin_usdt > available_balance:
        return build_result(
            False,
            (
                "Required margin exceeds the available account "
                "balance"
            ),
        )

    if (
        remaining_available_balance_usdt
        < minimum_free_balance_usdt
    ):
        return build_result(
            False,
            (
                "Trade would leave less than the configured minimum "
                "free balance"
            ),
        )

    return build_result(
        True,
        "Account protection passed",
    )