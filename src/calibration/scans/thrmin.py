from __future__ import annotations
from src.calibration.maps import ThresholdMinimizationMap
from src.calibration.scans.calibration_scan import CalibrationScan


class ThresholdMinimizationScan(CalibrationScan):
    @property
    def calibration_name(self) -> str:
        return "thrmin"
    
    def get_map(self):
        return ThresholdMinimizationMap()
    
    

