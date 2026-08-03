"""Environment validation v33."""
from __future__ import annotations
from app.config.production_profile import ProductionProfile
from app.config.secret_loader import load_secret_bundle


def validate_environment(
    *,
    profile: ProductionProfile,
    execute_trade_requested: bool,
    environ: dict | None = None,
) -> dict:
    diagnostics = load_secret_bundle(environ)["diagnostics"]
    errors = []
    warnings = []

    supported = profile.environment in {"DEVELOPMENT", "TESTNET", "MAINNET"}
    if not supported:
        errors.append("TITANAI_ENVIRONMENT must be DEVELOPMENT, TESTNET, or MAINNET")

    credentials_ok = all(
        diagnostics[name]["present"] and not diagnostics[name]["placeholder"]
        for name in ("binance_api_key", "binance_api_secret")
    )
    credentials_required = execute_trade_requested and (
        profile.strict_startup_validation or profile.is_mainnet
    )
    if credentials_required and not credentials_ok:
        errors.append("Valid Binance API credentials are required for strict execution startup")
    elif execute_trade_requested and not credentials_ok:
        warnings.append(
            "Binance credentials were not verified by startup validation; "
            "the exchange client may reject execution"
        )

    telegram_ok = (
        not profile.telegram_enabled
        or all(
            diagnostics[name]["present"] and not diagnostics[name]["placeholder"]
            for name in ("telegram_bot_token", "telegram_chat_id")
        )
    )
    if not telegram_ok:
        message = "Telegram is enabled but token or chat ID is missing or placeholder"
        (errors if profile.is_mainnet else warnings).append(message)

    mainnet_confirmation = not profile.is_mainnet or profile.mainnet_confirmed
    if not mainnet_confirmation:
        errors.append("MAINNET requires TITANAI_MAINNET_CONFIRMED=true")

    execution_opt_in = not execute_trade_requested or profile.execution_enabled
    if not execution_opt_in:
        errors.append("Execution requires TITANAI_EXECUTION_ENABLED=true")

    return {
        "status": "valid" if not errors else "invalid",
        "version": "v33",
        "valid": not errors,
        "checks": {
            "supported_environment": supported,
            "api_credentials": credentials_ok,
            "telegram_configuration": telegram_ok,
            "mainnet_confirmation": mainnet_confirmation,
            "execution_opt_in": execution_opt_in,
        },
        "errors": errors,
        "warnings": warnings,
        "secret_diagnostics": diagnostics,
        "secrets_redacted": True,
    }
