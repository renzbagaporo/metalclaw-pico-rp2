"""Regression checks for the four JLC library orientations observed on v1.r1."""
import unittest

from gen_fab import jlc_rotation


class JlcRotationTests(unittest.TestCase):
    def test_preview_corrections(self):
        cases = [
            ('U1', 'C51118', '0.000000', '270.000000'),
            ('U3', 'C5333729', '90.000000', '0.000000'),
            ('L1', 'C42411119', '0.000000', '180.000000'),
            ('J2', 'C27985146', '-90.000000', '180.000000'),
        ]
        for ref, code, raw, expected in cases:
            with self.subTest(ref=ref):
                self.assertEqual(jlc_rotation(ref, raw, code), expected)
                with self.assertRaises(ValueError):
                    jlc_rotation(ref, raw, 'a-replacement-part')

    def test_unreviewed_angles_are_preserved_exactly(self):
        for ref, raw in [('D1', '90.000000'), ('Y1', '-90.000000'),
                         ('U2', '0.000000'), ('R1', '180.000000')]:
            with self.subTest(ref=ref):
                self.assertEqual(jlc_rotation(ref, raw, ''), raw)


if __name__ == '__main__':
    unittest.main()
