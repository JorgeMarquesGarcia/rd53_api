from __future__ import annotations
from rd53_api.calibration.maps import NoiseScanMap
from rd53_api.calibration.scans.calibration_scan import CalibrationScan


class NoiseScan(CalibrationScan):
    @property
    def calibration_name(self) -> str:
        return "noise"
    
    def get_map(self):
        return NoiseScanMap()
    
    

