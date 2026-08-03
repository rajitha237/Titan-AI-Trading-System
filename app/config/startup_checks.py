"""Combined startup readiness v33."""
from __future__ import annotations
from app.config.deployment_validator import validate_deployment
from app.config.environment_validator import validate_environment
from app.config.production_profile import load_production_profile


def evaluate_startup_readiness(
    *,
    execute_trade_requested: bool,
    environ: dict | None = None,
) -> dict:
    profile = load_production_profile(environ)
    environment = validate_environment(
        profile=profile,
        execute_trade_requested=execute_trade_requested,
        environ=environ,
    )
    deployment = validate_deployment(
        profile=profile,
        execute_trade_requested=execute_trade_requested,
    )
    errors = list(dict.fromkeys([
        *environment["errors"],
        *deployment["errors"],
    ]))
    warnings = list(dict.fromkeys([
        *environment["warnings"],
        *deployment["warnings"],
    ]))

    return {
        "status": "ready" if not errors else "blocked",
        "version": "v33",
        "startup_allowed": not errors,
        "profile": profile.to_dict(),
        "environment_validation": environment,
        "deployment_validation": deployment,
        "errors": errors,
        "warnings": warnings,
        "secrets_redacted": True,
    }
