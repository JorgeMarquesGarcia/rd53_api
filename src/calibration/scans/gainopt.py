from __future__ import annotations
import re

from src.calibration.maps import GainOptimizationMap
from src.calibration.scans.gain import GainScan
from src.chip.register_map import ChipSettings
from src.remote.terminal import ANSI_ESCAPE_PATTERN

# Resultado por chip que imprime GainOptimization::analyze(), p. ej.
# "Krummenacher Current for [board/opticalGroup/hybrid/chip = 0/0/1/4] is 35"
KRUM_RESULT_PATTERN = re.compile(
    r"Krummenacher Current for \[board/opticalGroup/hybrid/chip = \d+/\d+/(\d+)/(\d+)\] is (\d+)"
)


class GainOptimizationScan(GainScan):
    """Gain optimization de Ph2_ACF: ajusta KRUM_CURR_LIN de cada chip.

    Ph2_ACF guarda el KRUM elegido en el .txt del chip, pero los <Settings> del
    XML (KRUM_CURR_LIN="29") se aplican por encima del .txt: sin copiarlo al XML
    el valor optimizado no se usaría en los runs siguientes.
    """

    @property
    def calibration_name(self) -> str:
        return "gainopt"

    def get_map(self):
        return GainOptimizationMap()

    def run(self):
        output = super().run()
        if self.scan_ended:
            self._update_xml_krum(output)
        return output

    def _update_xml_krum(self, output: str) -> None:
        """Copia al XML el KRUM_CURR_LIN elegido para cada chip calibrado."""
        krum_map = self.get_map()
        found = {
            (int(m.group(1)), int(m.group(2))): int(m.group(3))
            for m in KRUM_RESULT_PATTERN.finditer(ANSI_ESCAPE_PATTERN.sub("", output or ""))
        }
        with self.xml.batch():
            for hybrid_id, rd53_id in self.chips:
                chip = f"H{hybrid_id} Chip {rd53_id}"
                value = found.get((hybrid_id, rd53_id))
                if value is None:
                    self.report.append(f"[WARN]  KRUM_CURR_LIN for {chip} not found in the DAQ output: XML unchanged.")
                    continue
                # 0 es el valor inicial de la búsqueda: queda si todos los ajustes fallan
                if value == 0 or not krum_map.krum_start <= value <= krum_map.krum_stop:
                    self.report.append(f"[WARN]  KRUM_CURR_LIN = {value} for {chip} looks like a failed "
                                       f"optimization: XML unchanged.")
                    continue
                old = self.xml.get_chip_setting(hybrid_id, rd53_id, ChipSettings.KRUM_GAIN)
                self.xml.set_chip_setting(hybrid_id, rd53_id, ChipSettings.KRUM_GAIN, value)
                self.report.append(f"[INFO]  KRUM_CURR_LIN {chip}: {old} -> {value} (XML updated)")
