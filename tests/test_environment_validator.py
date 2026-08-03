from __future__ import annotations
import unittest
from app.config.environment_validator import validate_environment
from app.config.production_profile import load_production_profile


class EnvironmentValidatorTests(unittest.TestCase):
    def test_analysis_only_does_not_require_keys(self):
        profile = load_production_profile({})
        result = validate_environment(
            profile=profile,
            execute_trade_requested=False,
            environ={},
        )
        self.assertTrue(result["valid"])

    def test_strict_execution_requires_keys(self):
        environ = {
            "TITANAI_EXECUTION_ENABLED": "true",
            "TITANAI_STRICT_STARTUP_VALIDATION": "true",
        }
        result = validate_environment(
            profile=load_production_profile(environ),
            execute_trade_requested=True,
            environ=environ,
        )
        self.assertFalse(result["valid"])


if __name__ == "__main__":
    unittest.main()
