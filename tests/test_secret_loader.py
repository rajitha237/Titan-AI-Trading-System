from __future__ import annotations
import unittest
from app.config.secret_loader import load_secret_bundle, redact_secret


class SecretLoaderTests(unittest.TestCase):
    def test_diagnostics_do_not_expose_values(self):
        result = load_secret_bundle({
            "BINANCE_TESTNET_API_KEY": "real-key",
            "BINANCE_TESTNET_API_SECRET": "real-secret",
        })
        text = str(result["diagnostics"])
        self.assertNotIn("real-key", text)
        self.assertNotIn("real-secret", text)

    def test_redaction(self):
        self.assertEqual(redact_secret("secret"), "[REDACTED]")


if __name__ == "__main__":
    unittest.main()
