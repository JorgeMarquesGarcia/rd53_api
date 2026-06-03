from __future__ import annotations
from src.calibration.maps import SCurveMap
from src.calibration.scans.calibration_scan import CalibrationScan


class SCurveScan(CalibrationScan):
    @property
    def calibration_name(self) -> str:
        return "scurve"
    
    def get_map(self):
        return SCurveMap()
    
    

