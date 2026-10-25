"""Regression checks for the JLC library placement corrections on v1.r1."""
import unittest

from gen_fab import jlc_position, jlc_rotation


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

    def test_library_placement_heads(self):
        cases = [
            ('J1', 'C52209111', '163.810000', '-76.005000', '180.000000',
             ('163.8100mm', '-77.3232mm')),
            ('D1', 'C172430', '170.150000', '-78.830000', '90.000000',
             ('170.1500mm', '-78.5300mm')),
        ]
        for ref, code, x, y, angle, expected in cases:
            with self.subTest(ref=ref):
                self.assertEqual(jlc_position(ref, x, y, angle, code), expected)
                with self.assertRaises(ValueError):
                    jlc_position(ref, x, y, angle, 'a-replacement-part')
                with self.assertRaises(ValueError):
                    jlc_position(ref, x, y, str(float(angle) + 90), code)

    def test_other_positions_are_unchanged(self):
        self.assertEqual(jlc_position('U1', '168.857500', '-83.320000', '0',
                                      'C51118'), ('168.8575mm', '-83.3200mm'))


if __name__ == '__main__':
    unittest.main()
