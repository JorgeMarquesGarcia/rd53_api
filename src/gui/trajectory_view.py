"""trajectory_view.py - Panel Qt de trayectorias con animación."""
from __future__ import annotations
from collections import deque
from pathlib import Path

from PyQt5.QtWidgets import (
    QWidget, QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QListWidget,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QBrush, QColor

from src.chip.detector_geometry import z_position
from src.plotter.trajectory_interactive import InteractiveCoincidencePlotter

TRAJECTORY_FRAME_MS: int = 25          # 20 posiciones × 25 ms = 0,5 s por track
REMOVED_TRACK_COLOR: str = "#7A8090"   # tracks quitados del plot: en cursiva y atenuados


def track_planes(track: dict) -> int:
    """Número de planos del detector con hit en un track {(hybrid, lane): (row, col, tot)}."""
    return len({z_position(h) for h, _lane in track})


class TrajectoryView(QWidget):
    """Panel de trayectorias: incrusta el plotter 3D y marca el ritmo de la animación.

    El plotter solo dibuja; aquí vive la cola de tracks pendientes y el QTimer
    que avanza la animación en el hilo de la GUI (sin time.sleep).

    El botón Edit plot abre una ventana con los tracks dibujados, numerados,
    para resaltar uno, quitarlo del plot o volver a añadirlo.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._plotter = InteractiveCoincidencePlotter()
        self._queue: deque[tuple[int, dict]] = deque()   # (número, track) pendientes de animar
        self._n_given = 0   # tracks recibidos desde reset(): numeración por defecto
        self._editor: EditPlotDialog | None = None
        self._timer = QTimer(self)
        self._timer.setInterval(TRAJECTORY_FRAME_MS)
        self._timer.timeout.connect(self._on_frame)

        self._btn_edit = QPushButton("Edit plot")
        self._btn_edit.setToolTip("Highlight, remove or add back the drawn tracks")
        self._btn_edit.setEnabled(False)
        self._btn_edit.clicked.connect(self._open_editor)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.addStretch()
        header.addWidget(self._btn_edit)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(header)
        layout.addWidget(self._plotter.get_canvas(), 1)

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def reset(self, active_chips: list[tuple]) -> None:
        """Detiene la animación, vacía la cola y deja solo los planos."""
        self._timer.stop()
        self._queue.clear()
        self._n_given = 0
        self._plotter.reset(active_chips)
        if self._editor is not None:
            self._editor.reload()
        self._on_tracks_added()

    def animate(self, events: list[dict], numbers: list[int] | None = None) -> None:
        """Encola tracks para animarlos uno tras otro.

        numbers: número de cada track en Edit plot (p. ej. el del log de
        HitAnalysis). Por defecto, su posición entre los recibidos desde reset().
        """
        self._queue.extend(zip(self._numbers(events, numbers), events))
        if not self._timer.isActive():
            self._start_next()

    def draw_all(self, events: list[dict], numbers: list[int] | None = None) -> None:
        """Dibuja los tracks de golpe, sin animación (descarta la cola pendiente)."""
        self._timer.stop()
        self._queue.clear()
        self._plotter.draw_tracks(events, self._numbers(events, numbers))
        self._on_tracks_added()

    def save(self, output_dir: Path | None = None) -> Path:
        return self._plotter.save(output_dir)

    # ------------------------------------------------------------------
    # Animación
    # ------------------------------------------------------------------

    def _start_next(self) -> None:
        while self._queue:
            number, event = self._queue.popleft()
            if self._plotter.start_track(event, number):
                self._on_tracks_added()
                self._timer.start()
                return
        self._timer.stop()

    def _on_frame(self) -> None:
        if not self._plotter.advance():
            self._start_next()

    # ------------------------------------------------------------------
    # Edit plot
    # ------------------------------------------------------------------

    def _numbers(self, events: list[dict], numbers: list[int] | None) -> list[int]:
        """Número de cada track: el dado o su posición entre los recibidos desde reset()."""
        if numbers is None:
            numbers = range(self._n_given + 1, self._n_given + len(events) + 1)
        self._n_given += len(events)
        return list(numbers)

    def _on_tracks_added(self) -> None:
        self._btn_edit.setEnabled(self._plotter.n_tracks > 0)
        if self._editor is not None:
            self._editor.sync()

    def _open_editor(self) -> None:
        if self._editor is None:
            self._editor = EditPlotDialog(self._plotter, self)
        self._editor.show()
        self._editor.raise_()
        self._editor.activateWindow()


class EditPlotDialog(QDialog):
    """Ventana Edit plot: lista de los tracks dibujados de un TrajectoryView.

    Seleccionar un track lo resalta; Remove track lo quita del plot (en la lista
    queda en cursiva) y Add track lo vuelve a añadir. Doble clic hace lo mismo
    que el botón. Mientras se anima, la selección sigue al track en curso.
    """

    def __init__(self, plotter: InteractiveCoincidencePlotter, parent=None):
        super().__init__(parent)
        self._plotter = plotter
        self.setWindowTitle("Edit plot")
        self.setWindowFlags(self.windowFlags() | Qt.Tool)   # pequeña, sobre la ventana principal
        self.resize(280, 420)

        self._list = QListWidget()
        self._list.setToolTip("Select a track to highlight it. "
                              "Double-click removes it from the plot or adds it back.")
        self._list.currentRowChanged.connect(self._on_row_changed)
        self._list.itemDoubleClicked.connect(lambda _item: self._toggle_removed())

        self._status = QLabel()
        self._status.setStyleSheet(f"color: {REMOVED_TRACK_COLOR}; font-size: 10px;")

        self._btn_toggle = QPushButton("Remove track")
        self._btn_toggle.clicked.connect(self._toggle_removed)
        self._btn_clear = QPushButton("Clear highlight")
        self._btn_clear.clicked.connect(self._clear_highlight)

        buttons = QHBoxLayout()
        buttons.addWidget(self._btn_toggle)
        buttons.addWidget(self._btn_clear)

        layout = QVBoxLayout(self)
        layout.addWidget(self._list, 1)
        layout.addWidget(self._status)
        layout.addLayout(buttons)
        self.sync()

    # ------------------------------------------------------------------
    # Sincronización con el plot
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Rehace la lista entera (el plot se ha reiniciado)."""
        self._list.blockSignals(True)
        self._list.clear()
        self._list.blockSignals(False)
        self.sync()

    def sync(self) -> None:
        """Añade a la lista los tracks nuevos del plot y selecciona el resaltado."""
        self._list.blockSignals(True)
        for index in range(self._list.count(), self._plotter.n_tracks):
            number, event = self._plotter.track(index)
            self._list.addItem(f"Track {number}  ({track_planes(event)} planes)")
            self._style_item(index)
        self._list.blockSignals(False)
        self._select(self._plotter.highlighted)
        self._update_controls()

    def _select(self, index: int | None) -> None:
        """Selecciona una fila sin tocar el plot (None: ninguna)."""
        self._list.blockSignals(True)
        if index is None:
            self._list.clearSelection()
            self._list.setCurrentRow(-1)
        else:
            self._list.setCurrentRow(index)
        self._list.blockSignals(False)

    def _style_item(self, index: int) -> None:
        """Los tracks quitados del plot salen en cursiva y atenuados."""
        item = self._list.item(index)
        removed = not self._plotter.is_track_visible(index)
        font = item.font()
        font.setItalic(removed)
        item.setFont(font)
        item.setData(Qt.ForegroundRole, QBrush(QColor(REMOVED_TRACK_COLOR)) if removed else None)

    def _update_controls(self) -> None:
        row = self._list.currentRow()
        removed = row >= 0 and not self._plotter.is_track_visible(row)
        self._btn_toggle.setEnabled(row >= 0)
        self._btn_toggle.setText("Add track" if removed else "Remove track")
        self._btn_clear.setEnabled(self._plotter.highlighted is not None)

        n = self._plotter.n_tracks
        n_removed = sum(1 for i in range(n) if not self._plotter.is_track_visible(i))
        self._status.setText(f"{n} tracks, {n_removed} removed" if n_removed else f"{n} tracks")

    # ------------------------------------------------------------------
    # Acciones del usuario
    # ------------------------------------------------------------------

    def _on_row_changed(self, row: int) -> None:
        # Un track quitado no se resalta: solo se puede volver a añadir
        if row >= 0 and self._plotter.is_track_visible(row):
            self._plotter.highlight(row)
        else:
            self._plotter.highlight(None)
        self._update_controls()

    def _toggle_removed(self) -> None:
        row = self._list.currentRow()
        if row < 0:
            return
        visible = not self._plotter.is_track_visible(row)
        self._plotter.set_track_visible(row, visible)
        if visible:
            self._plotter.highlight(row)   # vuelve al plot resaltado: sigue seleccionado
        self._style_item(row)
        self._update_controls()

    def _clear_highlight(self) -> None:
        self._plotter.highlight(None)
        self._select(None)
        self._update_controls()
