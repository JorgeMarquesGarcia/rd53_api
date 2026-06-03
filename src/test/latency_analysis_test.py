from __future__ import annotations
import logging
from rd53_api.analysis.analysis_latency import LatencyAnalysis
from rd53_api.config.root.root_manager import RootManager
from rd53_api.config.xml.xml_manager import XmlManager
from rd53_api.chip.register_map import ChipSettings, CalibrationSettings
FILES_PATH = "/app/RD53_analysis/Data/ALL/20260211"
xml_file = FILES_PATH + "/Run000554_CMSIT_RD53A_SQQ.xml"
root_file = FILES_PATH + "/Run000554_Physics_Board000.root"

## XML configuration
xml_manager = XmlManager()
xml_manager.load(xml_file)
ntrig = int(xml_manager.get_calibration_setting(CalibrationSettings.N_TRIGGERS))
print(f"N_triggers: {ntrig}")

chip_latency = {}
chip_latency["H0_RD53_0"] = int(xml_manager.get_chip_setting(hybrid_id=0, rd53_id=0, name = ChipSettings.LATENCY))
chip_latency["H1_RD53_4"] = int(xml_manager.get_chip_setting(hybrid_id=1, rd53_id=4, name = ChipSettings.LATENCY))
chip_latency["H1_RD53_6"] = int(xml_manager.get_chip_setting(hybrid_id=1, rd53_id=6, name = ChipSettings.LATENCY))

print(f"Chip H0_RD53_0 latency: {chip_latency['H0_RD53_0']}")
print(f"Chip H1_RD53_4 latency: {chip_latency['H1_RD53_4']}")
print(f"Chip H1_RD53_6 latency: {chip_latency['H1_RD53_6']}")

## ROOT file loading
root_manager = RootManager(FILES_PATH)
root_manager.load(root_file)

## Latency Analysis 
LA = LatencyAnalysis(root_manager=root_manager, ntrig=ntrig, chip_latency=chip_latency)

print(f"Statistics: mean={LA.statistics['mean']}, std={LA.statistics['std']}, min={LA.statistics['min_pos']}, max={LA.statistics['max_pos']}")
print("\n")

#print(f"Positions in group: {LA.positions_in_group}")
#print(f"Group index: {LA.group_index}")
print(f"Adjusted Latency values (same ntrig): {LA.chip_latency}")
print("\n")

# Test: Cambiar a un ntrig diferente
ntrig_new = [5,10,15]
for ntrig_val in ntrig_new:
    LA1 = LatencyAnalysis(root_manager=root_manager, ntrig=ntrig, chip_latency=chip_latency, new_Ntrig=ntrig_val)
    print(f"Latency for ntrig_new={ntrig_val}: {LA1.chip_latency}")
    print(f"Explanation: Hit físico = latency_old + position_mean = 44 + {LA.statistics['mean']:.2f} = {44 + LA.statistics['mean']:.2f}")
    print(f"             new_latency = hit_físico - ntrig_new//2 = {44 + LA.statistics['mean']:.2f} - {ntrig_val//2} = {44 + LA.statistics['mean'] - ntrig_val//2:.2f}")
    