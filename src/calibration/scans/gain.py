from __future__ import annotations
from src.calibration.maps import GainScanMap
from src.calibration.scans.calibration_scan import CalibrationScan
from src.chip.register_map import CalibrationSettings

# SCurve y ThrEqu no fijan el barrido de VCal: usan el que haya en el XML.
# El gain scan escribe uno propio, así que al terminar deja el del XML como estaba.
_VCAL_SWEEP = (
    CalibrationSettings.VCAL_START,
    CalibrationSettings.VCAL_STOP,
    CalibrationSettings.VCAL_STEP,
)


class GainScan(CalibrationScan):
    """Gain scan de Ph2_ACF: ToT frente a ΔVCal inyectado, con ajuste lineal por píxel.

    Debe lanzarse con la misma configuración del chip (KRUM_CURR_LIN, umbrales,
    TDAC) que la toma de datos cuyos ToT se quieran convertir a carga.
    """

    @property
    def calibration_name(self) -> str:
        return "gain"

    def get_map(self):
        return GainScanMap()

    def run(self):
        saved = {s: self.xml.get_calibration_setting(s) for s in _VCAL_SWEEP}
        try:
            return super().run()
        finally:
            with self.xml.batch():
                for setting, value in saved.items():
                    self.xml.set_calibration_setting(setting, value)
