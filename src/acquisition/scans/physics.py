from __future__ import annotations
from rd53_api.acquisition.maps import PhysicsMap
from rd53_api.acquisition.scans.acquisition_scan import AcquisitionScan

class PhysicsScan(AcquisitionScan):
    """
    Physics data acquisition scan.
    
    Acquires real physics data from configured chips for particle detection.
    Configures XML for each chip (global settings once, per-chip settings for each),
    then launches a single physics acquisition that reads from all chips simultaneously.
    
    Usage:
        scan = PhysicsScan(chips=[(0, 0), (1, 0), (1, 1)], scan_time=300)
        output = scan.run()
        if scan.scan_ended:
            print(f"Physics acquisition successful: {scan.last_scan_end_pattern}")
    """
    
    @property
    def acquisition_name(self) -> str:
        """Return the acquisition type identifier for Ph2_ACF."""
        return "physics"
    
    def get_map(self):
        """Return the physics acquisition map with physics-specific parameters."""
        return PhysicsMap()
    

