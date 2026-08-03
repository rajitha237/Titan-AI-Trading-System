from __future__ import annotations
import unittest
from app.config.deployment_validator import validate_deployment
from app.config.production_profile import load_production_profile


class DeploymentValidatorTests(unittest.TestCase):
    def test_testnet_analysis_is_ready(self):
        result = validate_deployment(
            profile=load_production_profile({}),
            execute_trade_requested=False,
        )
        self.assertTrue(result["ready"])

    def test_mainnet_is_blocked_for_testnet_runner(self):
        result = validate_deployment(
            profile=load_production_profile({
                "TITANAI_ENVIRONMENT": "MAINNET",
                "TITANAI_MAINNET_CONFIRMED": "true",
                "TITANAI_EXECUTION_ENABLED": "true",
            }),
            execute_trade_requested=True,
        )
        self.assertFalse(result["ready"])


if __name__ == "__main__":
    unittest.main()
