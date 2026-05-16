from __future__ import annotations

import unittest

from normalizers.rainfall import normalize_rainfall


RAW_SAMPLE = """
[
  {
    estacion: 61,
    latitud: 13.7185,
    longitud: -89.2027,
    nombre_estacion: 'UES',
    hora_inicial: '21:10',
    valor_inicial: 1911.20,
    hora_reciente: '19:50',
    valor_maximo: 1911.80,
    valor_acumulado: 0.60,
    llueve: 0
  }
]
"""


class RainfallNormalizerTests(unittest.TestCase):
    def test_normalize_js_like_payload(self):
        rows = normalize_rainfall(RAW_SAMPLE)
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(row["station_id"], 61)
        self.assertEqual(row["station_name"], "UES")
        self.assertAlmostEqual(row["rain_mm_period"], 0.6, places=3)
        self.assertFalse(row["is_raining"])


if __name__ == "__main__":
    unittest.main()
