from rd53_api.config.xml.xml_manager import XmlManager
from rd53_api.chip.register_map import FastCmdReg, ChipSettings, CalibrationSettings

# Carga del XML de ejemplo
xml_file = r"C:\Users\jmarques\Containers\RD53\RD53_analysis\Data\ALL\20251218\Run000374_CMSIT_RD53A_SQ.xml"
xml = XmlManager(xml_file)
xml.load()

print("=== Test FastCmdReg ===")
try:
    # Leer un registro usando enum
    trigger_src = xml.get_register_value(FastCmdReg.TRIGGER_SOURCE)
    print("Trigger source:", trigger_src)

    # Modificar un registro usando enum
    xml.set_register_value(FastCmdReg.HITOR_ENABLE, 1)
    print("HITOR_ENABLE set to 1")

    # Forzar error con un enum que no existe
    try:
        xml.get_register_value("user.ctrl_regs.fast_cmd_reg_99.fake")
    except KeyError as e:
        print("Expected error:", e)
except Exception as e:
    print("FastCmdReg test failed:", e)

print("\n=== Test ChipSettings ===")
try:
    # Leer un setting de chip usando enum
    vthr = xml.get_chip_setting(0, 0, ChipSettings.VTHRESHOLD_LIN)
    print("Vthreshold_LIN:", vthr)

    # Modificar un setting de chip
    xml.set_chip_setting(0, 0, ChipSettings.KRUM_GAIN, 42)
    print("KRUM_CURR_LIN set to 42")

    # Forzar error con un setting que no existe
    try:
        xml.get_chip_setting(0, 0, "FAKE_SETTING")
    except Exception as e:
        print("Expected error:", e)
except Exception as e:
    print("ChipSettings test failed:", e)

print("\n=== Test CalibrationSettings ===")
try:
    # Leer un setting de calibración
    n_events = xml.get_calibration_setting(CalibrationSettings.N_EVENTS)
    print("nEvents:", n_events)

    # Modificar un setting de calibración
    xml.set_calibration_setting(CalibrationSettings.N_TRIGGERS, 20)
    print("nTRIGxEvent set to 20")

    # Forzar error con un setting que no existe
    try:
        xml.get_calibration_setting("FAKE_CAL_SETTING")
    except KeyError as e:
        print("Expected error:", e)
except Exception as e:
    print("CalibrationSettings test failed:", e)

print("\n=== Test done ===")
