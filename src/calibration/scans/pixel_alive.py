from __future__ import annotations
from src.calibration.maps import PixelAliveMap
from src.calibration.scans.calibration_scan import CalibrationScan


class PixelAliveScan(CalibrationScan):

    @property
    def calibration_name(self) -> str:
        return "pixelalive"
    
    def get_map(self):
        return PixelAliveMap()
    
    


    

    