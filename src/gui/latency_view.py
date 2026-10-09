"""latency_view.py - Resultado de LatencyAnalysis: posición de los hits en la ventana
de trigger y aplicación de la latencia al XML y a las adquisiciones.
"""
from __future__ import annotations
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QMessageBox,
)
from PyQt5.QtCore import Qt, pyqtSignal
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT

from src.acquisition.maps.acquisition_map import LATENCY_MAX
from src.chip.detector_geometry import rd53_id
from src.config.acquisition_config import AcquisitionConfig
from src.config.system_config import SystemConfig
from src.plotter.latency_histogram import build_latency_canvas

_COLUMNS = ("Chip", "Hits", "Median BX", "Mean BX", "Std", "Range", "Shift to centre")


def _signed(shift: float) -> str:
    return f"{round(shift):+d} BX"


class LatencyView(QWidget):
    """Página de resultados de latencia de un .root de Physics.

    result: dict que emite LatencyAnalysisWorker (ver analysis_tab).
    APPLY LATENCY escribe LATENCY_CONFIG en el XML activo y emite
    latency_applied para que el Acquisition tab la use en las próximas tomas.
    """

    log_message = pyqtSignal(str)
    latency_applied = pyqtSignal(int)

    def __init__(self, root_path: Path, result: dict, parent=None):
        super().__init__(parent)
        self._root_path = root_path
        self._result = result
        stats = result["chip_stats"]
        acq_ntrig = result["acq_ntrig"]

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        xml = result["xml_name"] or "not found"
        layout.addWidget(QLabel(
            f"Run window: {result['ntrig']} BX  ·  acquisitions: nTRIGxEvent = {acq_ntrig} "
            f"(centre BX{acq_ntrig // 2})  ·  run XML: {xml}"))

        suggestion = QLabel(self._suggestion_text(result))
        suggestion.setWordWrap(True)
        suggestion.setTextInteractionFlags(Qt.TextSelectableByMouse)
        suggestion.setToolTip("Lowering LATENCY_CONFIG by 1 moves the hits 1 BX earlier in the window.")
        suggestion.setStyleSheet("font-weight: bold;")
        layout.addWidget(suggestion)

        layout.addWidget(self._build_table(stats, acq_ntrig))

        canvas = build_latency_canvas(result["histograms"], stats, result["ntrig"], acq_ntrig // 2)
        layout.addWidget(NavigationToolbar2QT(canvas, self))
        layout.addWidget(canvas, 1)

        layout.addWidget(self._build_apply_panel())

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    @staticmethod
    def _suggestion_text(result: dict) -> str:
        shift = result["shift"]
        chip = result["reference_chip"]
        source = f"trigger plane H{chip[0]}·{chip[1]}" if chip else "all entries with hits"
        basis = (f"median of the {source} at BX{result['reference']:g} → "
                 f"BX{result['acq_ntrig'] // 2}")
        current, suggested = result["current_latency"], result["suggested_latency"]
        if not suggested:
            return (f"Current LATENCY_CONFIG unknown: change it by {_signed(shift)} "
                    f"to centre the hits in the acquisitions ({basis}).")
        pairs = {(current[chip], suggested[chip]) for chip in suggested}
        if len(pairs) == 1:
            (old, new), = pairs
            change = f"{old} → {new} in all chips"
        else:
            change = ", ".join(f"H{h}·{c}: {current[(h, c)]} → {suggested[(h, c)]}"
                               for h, c in suggested)
        return f"Suggested LATENCY_CONFIG for acquisitions: {change}  ({_signed(shift)}, {basis})."

    @staticmethod
    def _build_table(stats: dict, acq_ntrig: int) -> QTableWidget:
        table = QTableWidget(len(stats), len(_COLUMNS))
        table.setHorizontalHeaderLabels(_COLUMNS)
        table.horizontalHeaderItem(len(_COLUMNS) - 1).setToolTip(
            f"BX to add to LATENCY_CONFIG to bring the median of this chip to "
            f"BX{acq_ntrig // 2}, the centre of the acquisition window")
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        table.setSelectionMode(QAbstractItemView.NoSelection)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        for row, ((h, c), s) in enumerate(stats.items()):
            if s["n_hits"]:
                values = (f"H{h} · Chip {c}", str(s["n_hits"]), f"{s['median']:g}", f"{s['mean']:.2f}",
                          f"{s['std']:.2f}", f"BX{s['min_pos']} – BX{s['max_pos']}",
                          _signed(acq_ntrig // 2 - s["median"]))
            else:
                values = (f"H{h} · Chip {c}", "0", "—", "—", "—", "—", "—")
            for col, text in enumerate(values):
                item = QTableWidgetItem(text)
                item.setTextAlignment(Qt.AlignCenter)
                table.setItem(row, col, item)
        table.resizeRowsToContents()
        height = table.horizontalHeader().height() + sum(
            table.rowHeight(r) for r in range(table.rowCount())) + 2 * table.frameWidth()
        table.setFixedHeight(height)
        return table

    def _build_apply_panel(self) -> QWidget:
        group = QGroupBox("APPLY LATENCY (active XML + acquisitions)")
        row = QHBoxLayout(group)
        row.addWidget(QLabel("LATENCY_CONFIG:"))
        self._spin_apply = QSpinBox()
        self._spin_apply.setRange(0, LATENCY_MAX)
        self._spin_apply.setValue(self._default_apply_value())
        self._spin_apply.setMaximumWidth(90)
        row.addWidget(self._spin_apply)
        self._acq_note = QLabel()
        self._acq_note.setStyleSheet("color: #7A8090;")
        self._update_acq_note()
        row.addWidget(self._acq_note)
        row.addStretch()
        btn = QPushButton("APPLY LATENCY")
        btn.setObjectName("btn_launch")
        btn.setToolTip("Write LATENCY_CONFIG in the active XML for the chips of this file and "
                       "use it in the next acquisitions (Acquisition tab)")
        btn.clicked.connect(self._apply_latency)
        row.addWidget(btn)
        return group

    def _update_acq_note(self):
        self._acq_note.setText(f"(acquisitions now: latency {self._result['acq_latency']}, "
                               f"nTRIGxEvent {self._result['acq_ntrig']})")

    def _default_apply_value(self) -> int:
        """La latencia propuesta (la del plano de referencia si los chips difieren).

        Sin XML del run no se conoce la latencia con que se tomó: se parte de la
        de las adquisiciones y el usuario la ajusta con el desplazamiento indicado.
        """
        suggested = self._result["suggested_latency"]
        if not suggested:
            return self._result["acq_latency"]
        chip = self._result["reference_chip"]
        value = suggested.get(chip, next(iter(suggested.values())))
        return min(max(value, 0), LATENCY_MAX)

    # ------------------------------------------------------------------
    # Aplicar
    # ------------------------------------------------------------------
    def _apply_latency(self):
        value = self._spin_apply.value()
        # La latencia propuesta depende del nTRIGxEvent de las adquisiciones
        ntrig_now = AcquisitionConfig.get_ntriggers()
        if ntrig_now != self._result["acq_ntrig"]:
            self._warn(f"nTRIGxEvent of the acquisitions changed from {self._result['acq_ntrig']} "
                       f"to {ntrig_now} after this analysis: run LATENCY ANALYSIS again.")
            return
        chips = list(self._result["chip_stats"])
        try:
            hw_chips = {chip: (chip[0], rd53_id(*chip)) for chip in chips}
            xml_path = SystemConfig.get_xml_path()
        except Exception as e:
            self._warn(f"Cannot apply the latency:\n{e}")
            return

        names = ", ".join(f"H{h} · Chip {c}" for h, c in chips)
        msg = (f"Set LATENCY_CONFIG = {value}?\n\n"
               f"XML: {xml_path}\nChips: {names}\n\n"
               f"It also becomes the latency of the next acquisitions "
               f"(Acquisition tab, now {self._result['acq_latency']}).")
        if QMessageBox.question(self, "Apply latency", msg) != QMessageBox.Yes:
            return

        try:
            failed = AcquisitionConfig.set_chip_latency(hw_chips.values(), value)
        except Exception as e:
            self.log_message.emit(f"[ERROR] Cannot write LATENCY_CONFIG in the XML: {e}")
            self._warn(f"Cannot write LATENCY_CONFIG in the XML:\n{e}")
            return

        written = [chip for chip, hw in hw_chips.items() if hw not in failed]
        if written:
            self.log_message.emit(f"[OK]   LATENCY_CONFIG = {value} in {xml_path.name}: " + ", ".join(
                f"H{h}·{c}" for h, c in written))
        for (h, r), error in failed.items():
            self.log_message.emit(f"[WARN] LATENCY_CONFIG not written for H{h} · RD53A {r}: {error}")
        self._result["acq_latency"] = value
        self._update_acq_note()
        self.latency_applied.emit(value)

    def _warn(self, msg: str):
        QMessageBox.warning(self, "Latency", msg)
