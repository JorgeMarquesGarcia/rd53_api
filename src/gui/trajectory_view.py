"""trajectory_view.py - Panel Qt de trayectorias con animación."""
from __future__ import annotations
from collections import deque
from pathlib import Path

from PyQt5.QtWidgets import QWidget, QVBoxLayout
from PyQt5.QtCore import QTimer

from src.plotter.trajectory_interactive import InteractiveCoincidencePlotter

TRAJECTORY_FRAME_MS: int = 25   # 20 posiciones × 25 ms = 0,5 s por track


class TrajectoryView(QWidget):
    """Panel de trayectorias: incrusta el plotter 3D y marca el ritmo de la animación.

    El plotter solo dibuja; aquí vive la cola de tracks pendientes y el QTimer
    que avanza la animación en el hilo de la GUI (sin time.sleep).
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._plotter = InteractiveCoincidencePlotter()
        self._queue: deque[dict] = deque()
        self._timer = QTimer(self)
        self._timer.setInterval(TRAJECTORY_FRAME_MS)
        self._timer.timeout.connect(self._on_frame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._plotter.get_canvas())

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    def reset(self, active_chips: list[tuple]) -> None:
        """Detiene la animación, vacía la cola y deja solo los planos."""
        self._timer.stop()
        self._queue.clear()
        self._plotter.reset(active_chips)

    def animate(self, events: list[dict]) -> None:
        """Encola tracks para animarlos uno tras otro."""
        self._queue.extend(events)
        if not self._timer.isActive():
            self._start_next()

    def draw_all(self, events: list[dict]) -> None:
        """Dibuja los tracks de golpe, sin animación (descarta la cola pendiente)."""
        self._timer.stop()
        self._queue.clear()
        self._plotter.draw_tracks(events)

    def save(self, output_dir: Path | None = None) -> Path:
        return self._plotter.save(output_dir)

    # ------------------------------------------------------------------
    # Animación
    # ------------------------------------------------------------------

    def _start_next(self) -> None:
        while self._queue:
            if self._plotter.start_track(self._queue.popleft()):
                self._timer.start()
                return
        self._timer.stop()

    def _on_frame(self) -> None:
        if not self._plotter.advance():
            self._start_next()
