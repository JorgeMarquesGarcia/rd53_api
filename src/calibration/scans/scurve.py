from __future__ import annotations
from rd53_api.calibration.maps import SCurveMap
from rd53_api.calibration.scans.calibration_scan import CalibrationScan


class SCurveScan(CalibrationScan):
    @property
    def calibration_name(self) -> str:
        return "scurve"
    
    def get_map(self):
        return SCurveMap()
    
    

