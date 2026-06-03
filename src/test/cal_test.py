from pathlib import Path
from src.config.calibration_config import CalibrationConfig
from src.calibration.scans import SCurveScan

CalibrationConfig.set_ph2_acf_dir(r"/home/usuario/testing/CosmicRays/Ph2_ACF_v6.02")
CalibrationConfig.set_xml_path(r"/home/usuario/testing/CosmicRays/Ph2_ACF_v6.02/RD53_QUAD/CMSIT_RD53A_prueba.xml")

print(CalibrationConfig.get_ph2_acf_dir())
print(CalibrationConfig.get_xml_path())

if CalibrationConfig.is_configured():
    print("Conffigurationo ready")

scan = SCurveScan(hybrid_id=0, rd53_id=0, timeout=1000)

print(scan.run())
