from __future__ import annotations
from src.calibration.maps import ThresholdEqualizationMap 
from src.calibration.scans.calibration_scan import CalibrationScan


class ThresholdEqualizationScan(CalibrationScan):
    @property
    def calibration_name(self) -> str:
        return "threqu"
    
    def get_map(self):
        return ThresholdEqualizationMap()
    
    

