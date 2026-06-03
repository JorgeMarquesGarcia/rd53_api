"""
Tests para rd53_api/analysis/analysis_hit.py

Verifica:
- HitAnalysis hereda de BaseAnalysis
- Filtro de trigger
- Filtro de detector
- Filtro de TOT
- Filtro de layer
"""
from __future__ import annotations
import unittest
import awkward as ak

from rd53_api.analysis.analysis_hit import HitAnalysis
from rd53_api.core.exceptions import NAErrorNoHits, AnalysisError


class FakeRootManager:
    """Mock de RootManager para tests."""
    
    def __init__(self, arrays=None, loaded: bool = True):
        self.arrays = arrays
        self._loaded = loaded

    def is_loaded(self) -> bool:
        return self._loaded


class TestHitAnalysisBasic(unittest.TestCase):
    """Tests básicos de HitAnalysis."""
    
    def setUp(self):
        """Crear datos de prueba con estructura completa."""
        self.arrays = ak.Array({
            "event": [0, 1, 2, 3, 4],
            "RD53_frame_event_nhits": [
                [1, 0, 0],   # Evento 0: 1 hit en chip 0
                [2, 1, 0],   # Evento 1: 2 hits chip 0, 1 hit chip 1
                [0, 0, 0],   # Evento 2: sin hits (será filtrado)
                [1, 2, 1],   # Evento 3: hits en todos los chips
                [1, 0, 0],   # Evento 4: solo chip 0
            ],
            "RD53_frame_triggered": [1, 1, 0, 1, 0],  # Solo eventos 0,1,3 tienen trigger
            "RD53_hit_tot": [
                [5],           # Evento 0: TOT=5
                [2, 3, 4],     # Evento 1: TOT bajo
                [],            # Evento 2: vacío
                [10, 8, 6, 4], # Evento 3: TOT alto
                [3],           # Evento 4: TOT bajo
            ],
            "RD53_hit_row": [
                [10],
                [11, 12, 13],
                [],
                [20, 21, 22, 23],
                [30],
            ],
            "RD53_hit_col": [
                [100],
                [101, 102, 103],
                [],
                [200, 201, 202, 203],
                [300],
            ],
        })
    
    def test_hit_analysis_inherits_clean_data(self):
        """HitAnalysis tiene clean_data de BaseAnalysis."""
        manager = FakeRootManager(arrays=self.arrays, loaded=True)
        analysis = HitAnalysis(root_manager=manager)
        
        # clean_data no debe incluir el evento vacío (evento 2)
        self.assertEqual(len(analysis.clean_data), 4)
    
    def test_trigger_filter(self):
        """Solo eventos con trigger=1 pasan el filtro."""
        manager = FakeRootManager(arrays=self.arrays, loaded=True)
        analysis = HitAnalysis(root_manager=manager)
        
        # De los 4 eventos con hits, solo 3 tienen trigger (0, 1, 3)
        self.assertEqual(len(analysis.trigger_data), 3)
    
    def test_detector_filter(self):
        """Solo eventos con hits en chips 1+ pasan filter_detector."""
        manager = FakeRootManager(arrays=self.arrays, loaded=True)
        analysis = HitAnalysis(root_manager=manager)
        
        # De los 3 con trigger, solo 2 tienen hits en chip 1+ (eventos 1 y 3)
        self.assertEqual(len(analysis.hits), 2)
    
    def test_raises_when_no_trigger_hits(self):
        """Lanza excepción si no hay eventos con trigger."""
        arrays_no_trigger = ak.Array({
            "event": [0, 1],
            "RD53_frame_event_nhits": [[1, 0], [0, 0]],
            "RD53_frame_triggered": [0, 0],  # Ninguno tiene trigger
            "RD53_hit_tot": [[5], []],
            "RD53_hit_row": [[10], []],
            "RD53_hit_col": [[100], []],
        })
        manager = FakeRootManager(arrays=arrays_no_trigger, loaded=True)
        
        with self.assertRaises(NAErrorNoHits):
            HitAnalysis(root_manager=manager)


class TestHitAnalysisFilters(unittest.TestCase):
    """Tests para los métodos de filtrado."""
    
    def setUp(self):
        """Datos con variedad de TOT y layers."""
        self.arrays = ak.Array({
            "event": [0, 1, 2],
            "RD53_frame_event_nhits": [
                [1, 1, 0],  # Hits en chip 0 y 1
                [1, 0, 1],  # Hits en chip 0 y 2
                [1, 1, 1],  # Hits en todos
            ],
            "RD53_frame_triggered": [1, 1, 1],
            "RD53_hit_tot": [
                [5, 2],      # TOT: 5, 2
                [10, 8],     # TOT: 10, 8
                [1, 2, 3],   # TOT: 1, 2, 3 (bajo)
            ],
            "RD53_hit_row": [[10, 11], [20, 21], [30, 31, 32]],
            "RD53_hit_col": [[100, 101], [200, 201], [300, 301, 302]],
        })
    
    def test_tot_filter_default_threshold(self):
        """filter_tot con threshold=3 por defecto."""
        manager = FakeRootManager(arrays=self.arrays, loaded=True)
        analysis = HitAnalysis(root_manager=manager)
        
        filtered = analysis.filter_tot()
        # Evento 0: tiene TOT=2 (<3), no pasa
        # Evento 1: todos TOT>=3, pasa
        # Evento 2: todos TOT<3, no pasa
        self.assertEqual(len(filtered), 1)
    
    def test_layer_filter_empty_returns_all(self):
        """filter_layer sin especificar layers retorna todos."""
        manager = FakeRootManager(arrays=self.arrays, loaded=True)
        analysis = HitAnalysis(root_manager=manager)
        
        filtered = analysis._layer_filter(layer=[])
        self.assertEqual(len(filtered), len(analysis.hits))
    
    def test_analyzed_flag_set(self):
        """Los filtros establecen _analyzed=True."""
        manager = FakeRootManager(arrays=self.arrays, loaded=True)
        analysis = HitAnalysis(root_manager=manager)
        
        self.assertTrue(analysis._analyzed)  # Ya se establece en extract_hits


class TestHitAnalysisValidation(unittest.TestCase):
    """Tests para validación de RootManager."""
    
    def test_raises_when_not_loaded(self):
        """Lanza excepción si RootManager no está cargado."""
        arrays = ak.Array({"event": [0]})
        manager = FakeRootManager(arrays=arrays, loaded=False)
        
        with self.assertRaises(AnalysisError):
            HitAnalysis(root_manager=manager)
    
    def test_raises_when_arrays_none(self):
        """Lanza excepción si arrays es None."""
        manager = FakeRootManager(arrays=None, loaded=True)
        
        with self.assertRaises(AnalysisError):
            HitAnalysis(root_manager=manager)


if __name__ == "__main__":
    unittest.main()
