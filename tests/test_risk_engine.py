# My tests for risk_engine.py - they check the maths gives the right answers.
# Run with: python -m unittest discover -s tests -v

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import risk_engine as engine  # noqa: E402


class TestRiskMatrix(unittest.TestCase):
    def test_impact_is_worst_of_cia(self):
        self.assertEqual(engine.cia_impact(2, 5, 3), 5)

    def test_score_is_likelihood_times_impact(self):
        self.assertEqual(engine.risk_score(4, 5), 20)

    def test_nist_table_i2(self):
        # I picked some cells from NIST Table I-2 to check my table is copied right
        self.assertEqual(engine.risk_level(5, 5), "Very High")
        self.assertEqual(engine.risk_level(5, 1), "Very Low")
        self.assertEqual(engine.risk_level(3, 4), "Moderate")
        self.assertEqual(engine.risk_level(3, 5), "High")
        self.assertEqual(engine.risk_level(2, 5), "Moderate")
        self.assertEqual(engine.risk_level(1, 5), "Low")

    def test_controls_lower_likelihood(self):
        # 5 x (1 - 0.2) = 4
        self.assertEqual(engine.residual_likelihood(5, 20), 4)
        # 4 x (1 - 0.6) = 1.6 -> rounded up to 2
        self.assertEqual(engine.residual_likelihood(4, 60), 2)

    def test_likelihood_never_below_one(self):
        self.assertEqual(engine.residual_likelihood(3, 100), 1)

    def test_rejects_wrong_input(self):
        with self.assertRaises(ValueError):
            engine.risk_score(6, 3)


class TestMoney(unittest.TestCase):
    def test_sle_and_ale(self):
        # RM 1,000,000 asset, lose 50% each time, happens once every 5 years (0.2)
        one_incident = engine.sle(1_000_000, 50)
        self.assertEqual(one_incident, 500_000)
        self.assertEqual(engine.ale(one_incident, 0.2), 100_000)


class TestFullRow(unittest.TestCase):
    def test_one_risk_end_to_end(self):
        row = {"likelihood": 5, "confidentiality": 4, "integrity": 3, "availability": 3,
               "control_effectiveness": 20, "asset_value": 500_000,
               "exposure_factor": 30, "aro": 2}
        r = engine.assess(row)
        self.assertEqual(r["inherent_score"], 20)
        self.assertEqual(r["inherent_level"], "High")      # likelihood 5, impact 4
        self.assertEqual(r["residual_score"], 16)
        self.assertEqual(r["residual_level"], "High")      # likelihood 4, impact 4
        self.assertEqual(r["ale_before"], 300_000)
        self.assertAlmostEqual(r["ale_after"], 240_000)


if __name__ == "__main__":
    unittest.main()
