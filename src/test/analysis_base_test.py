from __future__ import annotations
import unittest
import awkward as ak

from src.analysis.analysis_noise import NoiseAnalysis
from src.analysis.analysis_hit import HitAnalysis
from src.analysis.analysis_latency import LatencyAnalysis
from src.core.exceptions import (
    AnalysisError,
    LAnRootError,
    LAnRootArraysError,
)


class FakeRootManager:
    def __init__(self, arrays=None, loaded: bool = True):
        self.arrays = arrays
        self._loaded = loaded

    def is_loaded(self) -> bool:
        return self._loaded


class TestAnalysisBaseIntegration(unittest.TestCase):
    def setUp(self):
        self.arrays = ak.Array(
            {
                "event": [0, 1, 2, 3],
                "RD53_frame_event_nhits": [
                    [1, 0, 0],
                    [2, 1, 0],
                    [0, 0, 0],
                    [1, 2, 0],
                ],
                "RD53_frame_triggered": [1, 1, 0, 1],
                "RD53_hit_tot": [
                    [5],
                    [2, 3],
                    [],
                    [1, 2],
                ],
                "RD53_hit_row": [
                    [10],
                    [11, 12],
                    [],
                    [13, 14],
                ],
                "RD53_hit_col": [
                    [20],
                    [21, 22],
                    [],
                    [23, 24],
                ],
            }
        )

    def test_noise_analysis_works_with_base_class(self):
        """NoiseAnalysis hereda de BaseAnalysis y detecta píxeles ruidosos."""
        manager = FakeRootManager(arrays=self.arrays, loaded=True)
        analysis = NoiseAnalysis(root_manager=manager)

        # clean_data excluye eventos vacíos
        self.assertEqual(len(analysis.clean_data), 3)
        # noisy_events y noisy_pixels están disponibles
        self.assertIsNotNone(analysis.noisy_events)
        self.assertIsNotNone(analysis.noisy_pixels)

    def test_hit_analysis_works_with_base_class(self):
        """HitAnalysis hereda de BaseAnalysis y extrae hits."""
        manager = FakeRootManager(arrays=self.arrays, loaded=True)
        analysis = HitAnalysis(root_manager=manager)

        # clean_data excluye eventos vacíos
        self.assertEqual(len(analysis.clean_data), 3)
        # trigger_data y hits están disponibles
        self.assertIsNotNone(analysis.trigger_data)
        self.assertIsNotNone(analysis.hits)

    def test_latency_analysis_works_with_base_class(self):
        manager = FakeRootManager(arrays=self.arrays, loaded=True)
        analysis = LatencyAnalysis(
            root_manager=manager,
            ntrig=4,
            chip_latency={"H0_RD53_0": 40},
        )

        self.assertEqual(len(analysis.clean_data), 3)
        self.assertIn("mean", analysis.statistics)
        self.assertIn("H0_RD53_0", analysis.chip_latency)

    def test_noise_analysis_raises_when_root_not_loaded(self):
        """NoiseAnalysis lanza excepción si RootManager no está cargado."""
        manager = FakeRootManager(arrays=self.arrays, loaded=False)
        with self.assertRaises(AnalysisError):
            NoiseAnalysis(root_manager=manager)

    def test_noise_analysis_raises_when_arrays_missing(self):
        """NoiseAnalysis lanza excepción si arrays es None."""
        manager = FakeRootManager(arrays=None, loaded=True)
        with self.assertRaises(AnalysisError):
            NoiseAnalysis(root_manager=manager)

    def test_hit_analysis_raises_when_root_not_loaded(self):
        """HitAnalysis lanza excepción si RootManager no está cargado."""
        manager = FakeRootManager(arrays=self.arrays, loaded=False)
        with self.assertRaises(AnalysisError):
            HitAnalysis(root_manager=manager)

    def test_hit_analysis_raises_when_arrays_missing(self):
        """HitAnalysis lanza excepción si arrays es None."""
        manager = FakeRootManager(arrays=None, loaded=True)
        with self.assertRaises(AnalysisError):
            HitAnalysis(root_manager=manager)

    def test_latency_analysis_raises_when_root_not_loaded(self):
        manager = FakeRootManager(arrays=self.arrays, loaded=False)
        with self.assertRaises(LAnRootError):
            LatencyAnalysis(root_manager=manager)

    def test_latency_analysis_raises_when_arrays_missing(self):
        manager = FakeRootManager(arrays=None, loaded=True)
        with self.assertRaises(LAnRootArraysError):
            LatencyAnalysis(root_manager=manager)


if __name__ == "__main__":
    unittest.main()
