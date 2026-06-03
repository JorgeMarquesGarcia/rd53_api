#!/usr/bin/env python3
"""
State Machine Test - 3 Acquisition-Analysis Cycles

Tests the StateOrchestrator with hardcoded acquisition parameters.
Flows: IDLE -> ACQUISITION -> ANALYSIS -> ACQUISITION -> ANALYSIS -> ACQUISITION -> ANALYSIS

Modify CONFIGURATION CONSTANTS at the top to change settings.
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.config.system_config import SystemConfig
from src.config.acquisition_config import AcquisitionConfig
from src.acquisition.scans.physics import PhysicsScan
from src.workflow.state_orchestrator import StateOrchestrator
from src.workflow.system_state import SystemState


# ============================================================================
# CONFIGURATION CONSTANTS
# ============================================================================

LAB = False

# Chips
CHIPS = [(0, 0), (1, 4), (1, 6)]

# Acquisition time per cycle (seconds)
ACQUISITION_TIME = 60

# Path to Ph2_ACF
PH2_ACF_DIR = "/home/usuario/testing/CosmicRays/Ph2_ACF_v6.02" if LAB else "/app/Ph2_ACF"
XML_CONFIG = "/home/usuario/testing/CosmicRays/Ph2_ACF_v6.02/RD53_QUAD/CMSIT_RD53A_SQ.xml" if LAB else "/app/RD53_analysis/ConfigFiles/CMSIT_RD53A_SQ.xml"
ROOT_OUTPUT_DIR = "/home/usuario/testing/CosmicRays/Ph2_ACF_v6.02/RD53_QUAD/Results" if LAB else "/app/RD53_analysis/Data/ALL/20260312"

# Max noisy pixels to trigger next ACQUISITION
MAX_NOISY_PIXELS = 100

# ============================================================================


def print_separator(title: str = ""):
    """Print a formatted separator line."""
    if title:
        print(f"\n{'=' * 75}")
        print(f"  {title}")
        print(f"{'=' * 75}")
    else:
        print(f"\n{'-' * 75}")


def print_state_info(state: SystemState):
    """Print current state with visual indicator."""
    state_display = {
        SystemState.IDLE: "🔴 IDLE",
        SystemState.CALIBRATION: "🟡 CALIBRATION",
        SystemState.ACQUISITION: "🟢 ACQUISITION",
        SystemState.ANALYSIS: "🔵 ANALYSIS",
    }
    print(f"\n→  Current State: {state_display.get(state, str(state))}")


def create_acquisition_executor(acq_config: AcquisitionConfig) -> callable:
    """Create acquisition executor callback for StateOrchestrator."""
    
    def executor() -> bool:
        """Execute PhysicsScan and return whether it completed."""
        print("\n   [ACQUISITION EXECUTOR] Starting PhysicsScan...")
        
        try:
            physics_scan = PhysicsScan(
                chips=CHIPS,
                timeout=ACQUISITION_TIME + 30,  # Add buffer to timeout
                scan_time=ACQUISITION_TIME,
            )
            
            physics_scan.run()
            
            if physics_scan.scan_ended:
                print("   [ACQUISITION EXECUTOR] ✓ Scan completed")
                print(f"   [ACQUISITION EXECUTOR] End pattern: {physics_scan.last_scan_end_pattern}")
                return True
            else:
                print("   [ACQUISITION EXECUTOR] ❌ Scan did not complete")
                return False
                
        except Exception as e:
            print(f"   [ACQUISITION EXECUTOR] ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    return executor


def main():
    """Execute 3 ACQUISITION-ANALYSIS cycles with state machine."""
    
    print_separator("STATE MACHINE TEST - 3 ACQ-ANALYSIS CYCLES")
    
    print("\nConfiguration:")
    print(f"  Chips:          {CHIPS}")
    print(f"  Acq Time:       {ACQUISITION_TIME}s")
    print(f"  XML Config:     {XML_CONFIG}")
    print(f"  Output Dir:     {ROOT_OUTPUT_DIR}")
    print(f"  Max Noisy:      {MAX_NOISY_PIXELS}")
    
    try:
        # ====================================================================
        # SETUP
        # ====================================================================
        print_separator("SETUP")
        
        print("\n[1/3] Initializing SystemConfig (singleton)...")
        sys_config = SystemConfig()
        sys_config.setup()  # Register transition conditions
        sys_config.set_state(SystemState.IDLE)
        sys_config.set_max_noisy_pixels(MAX_NOISY_PIXELS)
        print("  ✓ SystemConfig ready")
        
        print("\n[2/3] Configuring acquisition...")
        acq_setup = AcquisitionConfig()
        acq_setup.setup_acq(PH2_ACF_DIR, XML_CONFIG)
        print("  ✓ Acquisition configured")
        
        print("\n[3/3] Creating StateOrchestrator...")
        acquisition_executor = create_acquisition_executor(sys_config)
        orchestrator = StateOrchestrator(
            acquisition_executor=acquisition_executor
        )
        print("  ✓ StateOrchestrator ready")
        
        # ====================================================================
        # TRANSITION TO ACQUISITION
        # ====================================================================
        print_separator("TRANSITION: IDLE -> ACQUISITION")
        print("\nSetting initial state to ACQUISITION...")
        sys_config.set_state(SystemState.ACQUISITION)
        print_state_info(sys_config.get_state())
        
        # ====================================================================
        # RUN STATE MACHINE
        # ====================================================================
        print_separator("RUN STATE MACHINE - 3 CYCLES MAX")
        
        cycle = 0
        max_cycles = 6  # 3 ACQUISITION + 3 ANALYSIS = up to 6 iterations
        
        results = []
        for i in range(max_cycles):
            cycle += 1
            print_separator(f"ITERATION {i+1}")
            
            current_state = sys_config.get_state()
            print_state_info(current_state)
            
            # Run one orchestration step
            result = orchestrator.run_once()
            results.append(result)
            
            # Display result
            print(f"\n   Details:        {result.details}")
            print(f"   Scan Ended:     {result.scan_ended}")
            print(f"   Noisy Pixels:   {result.n_noisy_pixels}")
            print(f"   Next State:     {result.end_state}")
            
            # Check end condition
            if result.end_state == SystemState.IDLE:
                print("\n   → Returned to IDLE, stopping...")
                break
        
        # ====================================================================
        # SUMMARY
        # ====================================================================
        print_separator("EXECUTION SUMMARY")
        
        print(f"\nTotal Iterations: {len(results)}")
        print("\nState Transitions:")
        
        for idx, result in enumerate(results, 1):
            transition = f"{result.start_state.name} → {result.end_state.name}"
            print(f"  [{idx}] {transition:30} | Noisy={result.n_noisy_pixels:3} | {result.details[:40]}")
        
        print_separator()
        print("✓ STATE MACHINE TEST COMPLETED")
        print_separator()
        
        return 0
        
    except Exception as e:
        print_separator("ERROR")
        print(f"\n❌ Fatal Error: {e}")
        import traceback
        traceback.print_exc()
        print_separator()
        return 1


if __name__ == "__main__":
    sys.exit(main())
