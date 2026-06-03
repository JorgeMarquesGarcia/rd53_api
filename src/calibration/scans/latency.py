from __future__ import annotations
from rd53_api.calibration.maps import LatencyScanMap
from rd53_api.calibration.scans.calibration_scan import CalibrationScan


class LatencyScan(CalibrationScan):
    @property
    def calibration_name(self) -> str:
        return "latency"
    
    def get_map(self):
        return LatencyScanMap()
    
    

