#!/usr/bin/env python3
"""
Real Acquisition Script - Hardcoded Setup

Simply configures and launches a physics acquisition with predefined parameters.

Modify the constants at the top to change acquisition settings.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config.acquisition_config import AcquisitionConfig
from src.acquisition.scans.physics import PhysicsScan


# ============================================================================
# CONFIGURATION CONSTANTS - MODIFY THESE FOR YOUR ACQUISITION
# ============================================================================

LAB = False

# Chips to acquire from (list of (hybrid_id, rd53_id) tuples)
CHIPS = [(0, 0), (1, 4), (1, 6)]

# Acquisition time in seconds (-1 for unlimited)
ACQUISITION_TIME = 60

# Path to Ph2_ACF minidaqExecutable
if LAB:
    PH2_ACF_DIR = "/home/usuario/testing/CosmicRays/Ph2_ACF_v6.02"
else: 
    PH2_ACF_DIR = "/app/Ph2_ACF"


# XML configuration file
if LAB:
    XML_CONFIG = "/home/usuario/testing/CosmicRays/Ph2_ACF_v6.02/RD53_QUAD/CMSIT_RD53A_SQ.xml"
else:
    XML_CONFIG = "/app/RD53_analysis/ConfigFiles/CMSIT_RD53A_SQ.xml"


# ROOT output directory
if LAB:
    ROOT_OUTPUT_DIR = "/home/usuario/testing/CosmicRays/Ph2_ACF_v6.02/RD53_QUAD/Results"
else:
    ROOT_OUTPUT_DIR = "/app/RD53_analysis/Data/ALL/20260312"

# ============================================================================


def get_latest_raw_file(output_dir: Path) -> Path:
    """Find the latest .raw file in output directory."""
    output_path = Path(output_dir)
    if not output_path.exists():
        print(f"❌ Output directory does not exist: {output_path}")
        return None
    
    raw_files = sorted(output_path.glob("*.raw"), key=lambda p: p.stat().st_mtime, reverse=True)
    
    if not raw_files:
        print(f"⚠ No .raw files found in {output_path}")
        return None
    
    latest = raw_files[0]
    print(f"✓ Latest .raw file: {latest.name}")
    return latest


def main():
    """Execute acquisition with hardcoded parameters."""
    
    print("\n" + "=" * 75)
    print("  REAL ACQUISITION LAUNCHER")
    print("=" * 75)
    print(f"\nChips:             {CHIPS}")
    print(f"Acquisition time:  {ACQUISITION_TIME} seconds" if ACQUISITION_TIME > 0 else "Acquisition time:  unlimited")
    print(f"XML config:        {XML_CONFIG}")
    print(f"ROOT output:       {ROOT_OUTPUT_DIR}")
    
    try:
        # Step 1: Configure acquisition
        print("\n[1/3] Configuring AcquisitionConfig...")
        acq_config = AcquisitionConfig()
        acq_config.setup_acq(PH2_ACF_DIR, XML_CONFIG)
        print("  ✓ AcquisitionConfig ready")
        
        # Step 2: Launch PhysicsScan
        print("\n[2/3] Launching PhysicsScan...")
        physics_scan = PhysicsScan(
            chips=CHIPS,
            timeout=ACQUISITION_TIME + 120,  #  Add buffer to timeout
            scan_time=ACQUISITION_TIME,
        )
        physics_scan.run()
        
        # Step 3: Get latest .raw file
        print("\n[3/3] Retrieving output...")
        latest_raw = get_latest_raw_file(ROOT_OUTPUT_DIR)
        
        print("\n" + "=" * 75)
        if physics_scan.scan_ended:
            print("✓ Acquisition COMPLETE")
            if latest_raw:
                print(f"  Output file:  {latest_raw.name}")
        else:
            print("⚠ Acquisition did NOT complete")
        print("=" * 75)
        
        return 0
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())