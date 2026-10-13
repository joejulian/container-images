import unittest

import numpy as np

from conditioning_ab import compare, verify_positions


class ComparisonTests(unittest.TestCase):
    def test_known_metrics_and_repeat(self):
        a = np.array([[1., 2.], [3., 4.]], dtype=np.float32)
        repeat = compare(a, a.copy())
        self.assertTrue(repeat["byte_identical"])
        self.assertEqual(repeat["rmse"], 0)
        result = compare(a, a + 1)
        self.assertEqual(result["rmse"], 1)
        self.assertEqual(result["max_abs"], 1)
        self.assertAlmostEqual(result["relative_rmse"], 1 / np.sqrt(7.5))
        self.assertEqual(result["changed_elements"], 4)

    def test_invalid_values_are_rejected_without_mutation(self):
        for value in (np.nan, np.inf, -np.inf):
            a = np.array([value], dtype=np.float32)
            before = a.tobytes()
            with self.assertRaises(ValueError):
                compare(a, np.zeros_like(a))
            self.assertEqual(a.tobytes(), before)

    def test_position_guard_rejects_other_changes(self):
        original = [0, 1, 2, 0, 4, 2, 0, 1, 5, 0, 0, 0]
        corrected = original[:9] + original[:3]
        self.assertEqual(verify_positions(original, corrected, 3)["changed_positions"], 2)
        corrected[4] += 1
        with self.assertRaises(ValueError):
            verify_positions(original, corrected, 3)
        with self.assertRaises(ValueError):
            verify_positions(original, original, 3)


if __name__ == "__main__":
    unittest.main()
