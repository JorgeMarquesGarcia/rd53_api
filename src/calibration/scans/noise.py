from __future__ import annotations
from src.calibration.maps import NoiseScanMap
from src.calibration.scans.calibration_scan import CalibrationScan


class NoiseScan(CalibrationScan):
    @property
    def calibration_name(self) -> str:
        return "noise"
    
    def get_map(self):
        return NoiseScanMap()
    
    

