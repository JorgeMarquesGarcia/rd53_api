from __future__ import annotations
from rd53_api.calibration.maps import ThresholdEqualizationMap 
from rd53_api.calibration.scans.calibration_scan import CalibrationScan


class ThresholdEqualizationScan(CalibrationScan):
    @property
    def calibration_name(self) -> str:
        return "threqu"
    
    def get_map(self):
        return ThresholdEqualizationMap()
    
    

