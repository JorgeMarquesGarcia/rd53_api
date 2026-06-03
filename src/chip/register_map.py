from __future__ import annotations
from enum import Enum
from typing import Union
Value = Union[int, float, str]


class FastCmdReg(Enum):
    """Fast commands regs in RD53A"""
    TRIGGER_SOURCE = "user.ctrl_regs.fast_cmd_reg_2.trigger_source"
    HITOR_ENABLE = "user.ctrl_regs.fast_cmd_reg_2.HitOr_enable_l12"
    NUM_TRIGGERS = "user.ctrl_regs.fast_cmd_reg_3.triggers_to_accept"

    def __str__(self) -> str:
        return self.value

class ChipSettings(Enum):
    """RD53A chip settings names"""
    VTHRESHOLD_LIN = "Vthreshold_LIN"
    KRUM_GAIN = "KRUM_CURR_LIN"
    VTHRESHOLD_SYNC = "VTH_SYNC"
    VTHRESHOLD_DIFF1 = "VTH1_DIFF"
    VTHRESHOLD_DIFF2 = "VTH2_DIFF"
    VCAL_H = "VCAL_HIGH"
    VCAL_M = "VCAL_MED"
    LATENCY = "LATENCY_CONFIG"
    CLK_DATA_DELAY = "CLK_DATA_DELAY"
    CAL_FINE_DELAY = "CAL_EDGE_FINE_DELAY"
    V_TRIM_DIG = "VOLTAGE_TRIM_DIGITAL"
    V_TRIM_ANALOG = "VOLTAGE_TRIM_ANA"
    

    def __str__(self) -> str:
        return self.value


class CalibrationSettings(Enum):
    """RD53A calibration analysis settings names"""
    N_EVENTS = "nEvents"
    N_EVTBURST = "nEvtsBurst"
    N_TRIGGERS = "nTRIGxEvent"
    INJ_TYPE = "INJtype"
    RST_MASK = "ResetMask"
    RST_TDAC = "ResetTDAC"
    COL_START = "COLstart"
    COL_STOP = "COLstop"
    LAT_START = "LatencyStart"
    LAT_STOP = "LatencyStop"
    VCAL_START = "VCALHstart"
    VCAL_STOP = "VCALHstop"
    VCAL_STEP = "VCALHnsteps"
    VCAL_MED = "VCalMED"
    T_OCCUPANCY = "TargetOcc"
    OCC_PP = "OccPerPixel"
    GROUPS = "DoOnlyNGroups"
    UPDATE = "UpdateChipCfg"
    CLK_DELAY = "nClkDelays"
    SAVE_BINARY = "SaveBinaryData"
    THR_START = "ThrStart"
    THR_STOP = "ThrStop"
    THR_TARGET = "TargetThr"

    def __str__(self) -> str:
        return self.value
