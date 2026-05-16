from __future__ import annotations

import unittest

from normalizers.municipalities import normalize_municipality_feature


class MunicipalityNormalizerTests(unittest.TestCase):
    def test_normalize_point_lookup(self):
        raw = {
            "features": [
                {
                    "attributes": {
                        "COD": 1,
                        "NAM": "San Salvador",
                        "NA2": "SAN SALVADOR",
                        "NA3": "0614",
                    }
                }
            ]
        }
        row = normalize_municipality_feature(raw, lat=13.69, lon=-89.21)
        self.assertEqual(row["municipality"], "San Salvador")
        self.assertEqual(row["municipality_code"], "0614")


if __name__ == "__main__":
    unittest.main()
