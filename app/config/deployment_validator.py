"""Deployment safety validation v33."""
from __future__ import annotations
from app.config.production_profile import ProductionProfile


def validate_deployment(
    *,
    profile: ProductionProfile,
    execute_trade_requested: bool,
) -> dict:
    checks = {
        "risk_percent_limit": 0 < profile.maximum_risk_percent <= 2.0,
        "leverage_limit": 1 <= profile.maximum_leverage <= 5.0,
        "position_exposure_limit": 0 < profile.maximum_position_percent <= 25.0,
        "daily_loss_limit": 0 < profile.maximum_daily_loss_percent <= 3.0,
        "concurrent_position_limit": profile.maximum_concurrent_positions == 1,
        "runner_matches_profile": not profile.is_mainnet,
    }
    errors = [
        f"Unsafe deployment setting: {name}"
        for name, passed in checks.items()
        if not passed and name != "runner_matches_profile"
    ]
    warnings = []

    if profile.is_mainnet:
        errors.append(
            "The installed auto_testnet_runner supports Binance Futures "
            "Testnet only; Mainnet execution is not implemented"
        )
    if profile.environment == "DEVELOPMENT" and execute_trade_requested:
        errors.append("Execution is blocked in DEVELOPMENT")
    if profile.is_testnet and execute_trade_requested:
        warnings.append("Testnet execution was requested")

    return {
        "status": "ready" if not errors else "blocked",
        "version": "v33",
        "ready": not errors,
        "checks": checks,
        "errors": errors,
        "warnings": warnings,
        "runner_exchange_mode": profile.runner_exchange_mode,
    }
