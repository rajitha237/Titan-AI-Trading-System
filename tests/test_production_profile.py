from __future__ import annotations
import unittest
from app.config.production_profile import load_production_profile


class ProductionProfileTests(unittest.TestCase):
    def test_default_profile_is_testnet(self):
        profile = load_production_profile({})
        self.assertEqual(profile.environment, "TESTNET")
        self.assertFalse(profile.execution_enabled)

    def test_mainnet_flags_are_parsed(self):
        profile = load_production_profile({
            "TITANAI_ENVIRONMENT": "MAINNET",
            "TITANAI_MAINNET_CONFIRMED": "true",
            "TITANAI_EXECUTION_ENABLED": "true",
        })
        self.assertTrue(profile.is_mainnet)
        self.assertTrue(profile.mainnet_confirmed)


if __name__ == "__main__":
    unittest.main()
