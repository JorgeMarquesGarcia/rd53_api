"""noise_mask_view.py - Resultado de NoiseAnalysis: mapas de píxeles ruidosos y
aplicación de la máscara a los TXT de la configuración activa (guardar como).
"""
from __future__ import annotations
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QGroupBox, QLabel,
    QPushButton, QLineEdit, QCheckBox, QTabWidget, QMessageBox,
)
from PyQt5.QtCore import pyqtSignal
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT

from src.config.system_config import SystemConfig
from src.calibration.procedures.noisemaskcal import NoiseMaskCalibration, default_output_name
from src.plotter.noise_map import build_noise_map_canvas

ChipKey = tuple[int, int]


class NoiseMaskView(QWidget):
    """Página de resultados de ruido de un fichero .root."""

    log_message = pyqtSignal(str)

    def __init__(self, root_path: Path,
                 pixel_counts: dict[ChipKey, dict[tuple[int, int], int]],
                 stats: dict, parent=None):
        super().__init__(parent)
        self._root_path = root_path
        self._pixel_counts = {k: v for k, v in pixel_counts.items() if v}
        # Todas las filas del panel: chip -> (checkbox, etiqueta TXT origen, nombre de salida)
        self._rows: dict[ChipKey, tuple[QCheckBox, QLabel, QLineEdit]] = {}
        # TXT origen de los chips que se pueden enmascarar (se recalcula en refresh_sources)
        self._sources: dict[ChipKey, str] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(
            f"{stats['n_noisy_pixels']} noisy pixel(s) in {len(self._pixel_counts)} chip(s)  "
            f"·  {stats['noise_percentage']:.4f} % of {stats['total_pixels']} pixels"
        ))
        layout.addWidget(self._build_maps(), 1)
        layout.addWidget(self._build_mask_panel())
        self.refresh_sources()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build_maps(self) -> QWidget:
        tabs = QTabWidget()
        for (h, c), counts in sorted(self._pixel_counts.items()):
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 0, 0)
            canvas = build_noise_map_canvas(
                counts, title=f"H{h} · Chip {c} — {len(counts)} noisy pixel(s)")
            page_layout.addWidget(NavigationToolbar2QT(canvas, page))
            page_layout.addWidget(canvas, 1)
            tabs.addTab(page, f"H{h} · Chip {c} ({len(counts)})")
        return tabs

    def _build_mask_panel(self) -> QWidget:
        group = QGroupBox("MASK NOISY PIXELS (active configuration, save as)")
        layout = QVBoxLayout(group)

        grid = QGridLayout()
        grid.addWidget(QLabel("Chip"), 0, 0)
        grid.addWidget(QLabel("Source TXT"), 0, 1)
        grid.addWidget(QLabel("Save as"), 0, 2)

        for row, chip_key in enumerate(sorted(self._pixel_counts), start=1):
            h, c = chip_key
            cb = QCheckBox(f"H{h} · Chip {c} ({len(self._pixel_counts[chip_key])} px)")
            src_label = QLabel()
            edit = QLineEdit()
            self._rows[chip_key] = (cb, src_label, edit)
            grid.addWidget(cb, row, 0)
            grid.addWidget(src_label, row, 1)
            grid.addWidget(edit, row, 2)
        grid.setColumnStretch(2, 1)
        layout.addLayout(grid)

        bottom = QHBoxLayout()
        self._chk_update_xml = QCheckBox("Point XML to the masked TXT files")
        self._chk_update_xml.setChecked(False)
        bottom.addWidget(self._chk_update_xml)
        bottom.addStretch()
        self._btn_apply = QPushButton("APPLY MASK")
        self._btn_apply.setObjectName("btn_launch")
        self._btn_apply.clicked.connect(self._apply_mask)
        bottom.addWidget(self._btn_apply)
        layout.addLayout(bottom)
        return group

    def refresh_sources(self):
        """Resuelve el TXT origen de cada chip con la configuración activa.

        Se llama al crear la vista y cada vez que se aplica la configuración,
        así el panel no se queda con el estado del momento del análisis.
        """
        try:
            txt_base_dir = SystemConfig.get_txt_base_dir()
        except Exception:
            txt_base_dir = None

        old_sources = self._sources
        self._sources = {}
        for chip_key, (cb, src_label, edit) in self._rows.items():
            try:
                hw_hybrid, hw_id = NoiseMaskCalibration.hw_key(chip_key)
                source = NoiseMaskCalibration.config_file_for(chip_key)
            except ValueError:
                hw_hybrid, hw_id, source = chip_key[0], None, None

            if txt_base_dir is None:
                reason = "(TXT base directory not set: APPLY CONFIG)"
            elif hw_id is None:
                reason = f"(hybrid {chip_key[0]} not in detector layout)"
            elif not source:
                reason = f"(no configFile for H{hw_hybrid} · RD53A {hw_id} in XML)"
            else:
                reason = None

            if reason is not None:
                cb.setChecked(False)
                cb.setEnabled(False)
                edit.setEnabled(False)
                edit.clear()
                src_label.setText(reason)
                src_label.setToolTip("")
                continue

            self._sources[chip_key] = source
            cb.setEnabled(True)
            edit.setEnabled(True)
            src_label.setText(source)
            src_label.setToolTip(str(Path(txt_base_dir) / source))
            # Conservar lo que haya escrito el usuario si el origen no ha cambiado
            if old_sources.get(chip_key) != source:
                cb.setChecked(True)
                edit.setText(default_output_name(source))

        self._btn_apply.setEnabled(bool(self._sources))

    # ------------------------------------------------------------------
    # Aplicar máscara
    # ------------------------------------------------------------------
    def _selected_outputs(self) -> dict[ChipKey, str] | None:
        """{chip: nombre de salida} de los chips marcados; None si algún nombre no es válido."""
        outputs: dict[ChipKey, str] = {}
        for chip_key, source in self._sources.items():
            cb, _label, edit = self._rows[chip_key]
            if not cb.isChecked():
                continue
            name = edit.text().strip()
            h, c = chip_key
            if not name.lower().endswith(".txt"):
                self._warn(f"H{h} · Chip {c}: the output name must end in .txt")
                return None
            if Path(name).name == Path(source).name:
                self._warn(f"H{h} · Chip {c}: the output name must differ from the source TXT")
                return None
            outputs[chip_key] = name
        return outputs

    def _apply_mask(self):
        outputs = self._selected_outputs()
        if outputs is None:
            return
        if not outputs:
            self._warn("No chips selected.")
            return

        txt_base_dir = Path(SystemConfig.get_txt_base_dir())
        existing = [n for n in outputs.values() if (txt_base_dir / n).exists()]
        lines = [
            f"H{h} · Chip {c}: {len(self._pixel_counts[(h, c)])} px → {name}"
            for (h, c), name in sorted(outputs.items())
        ]
        msg = (f"Mask these pixels?\n\nFolder: {txt_base_dir}\n\n"
               + "\n".join(lines))
        if existing:
            msg += "\n\nThese files already exist and will be REPLACED:\n" + "\n".join(existing)
        if self._chk_update_xml.isChecked():
            msg += "\n\nThe XML will be updated to use the new TXT files."
        if QMessageBox.question(self, "Apply noise mask", msg) != QMessageBox.Yes:
            return

        pixels = {k: list(self._pixel_counts[k]) for k in outputs}
        try:
            paths = NoiseMaskCalibration(pixels).apply(
                output_names=outputs,
                update_xml=self._chk_update_xml.isChecked(),
            )
        except Exception as e:
            self.log_message.emit(f"[ERROR] Cannot apply noise mask: {e}")
            self._warn(f"Cannot apply noise mask:\n{e}")
            return

        for (h, c), path in sorted(paths.items()):
            self.log_message.emit(
                f"[OK]   H{h} · Chip {c}: {len(pixels[(h, c)])} pixel(s) masked → {path}")
        if self._chk_update_xml.isChecked():
            self.log_message.emit("[OK]   XML updated to use the masked TXT files.")

    def _warn(self, msg: str):
        QMessageBox.warning(self, "Noise mask", msg)
