"""
main_window.py - Ventana principal de la GUI RD53A.
"""
from __future__ import annotations
import logging
from PyQt5.QtWidgets import (
    QMainWindow, QTabWidget, QStatusBar,
    QLabel, QWidget, QHBoxLayout,
)
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QColor

from src.config.system_config import SystemConfig
from src.workflow.system_state import SystemState
from src.gui.tabs.config_tab       import ConfigTab
from src.gui.tabs.calibration_tab  import CalibrationTab
from src.gui.tabs.acquisition_tab  import AcquisitionTab

# ---------------------------------------------------------------------------
# Paleta de colores — estilo osciloscopio / industrial oscuro
# ---------------------------------------------------------------------------
QSS = """
QMainWindow, QWidget {
    background-color: #1A1D23;
    color: #D0D4DC;
    font-family: 'Courier New', monospace;
    font-size: 12px;
}

QTabWidget::pane {
    border: 1px solid #2E3340;
    background: #1A1D23;
}

QTabBar::tab {
    background: #22262E;
    color: #7A8090;
    padding: 8px 24px;
    border: 1px solid #2E3340;
    border-bottom: none;
    font-size: 11px;
    letter-spacing: 0.5px;
    text-transform: uppercase;
    min-width: 100px;
}

QTabBar::tab:selected {
    background: #1A1D23;
    color: #00E5FF;
    border-top: 2px solid #00E5FF;
}

QTabBar::tab:hover:!selected {
    color: #90A4B0;
    background: #252930;
}

QGroupBox {
    border: 1px solid #2E3340;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 8px;
    color: #7A8090;
    font-size: 10px;
    letter-spacing: 1px;
}

QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
    color: #00E5FF;
}

QPushButton {
    background: #22262E;
    color: #D0D4DC;
    border: 1px solid #3A4050;
    border-radius: 3px;
    padding: 6px 16px;
    font-family: 'Courier New', monospace;
    letter-spacing: 1px;
}

QPushButton:hover {
    background: #2A2F3A;
    border-color: #00E5FF;
    color: #00E5FF;
}

QPushButton:pressed {
    background: #1A1D23;
}

QPushButton:disabled {
    color: #404550;
    border-color: #2A2F3A;
}

QPushButton#btn_launch {
    background: #003D4A;
    color: #00E5FF;
    border: 1px solid #00E5FF;
    font-weight: bold;
    padding: 8px 24px;
    letter-spacing: 2px;
}

QPushButton#btn_launch:hover {
    background: #00E5FF;
    color: #1A1D23;
}

QPushButton#btn_launch:disabled {
    background: #1A1D23;
    color: #2A3540;
    border-color: #2A3540;
}

QLineEdit, QComboBox, QSpinBox {
    background: #22262E;
    color: #D0D4DC;
    border: 1px solid #3A4050;
    border-radius: 3px;
    padding: 4px 8px;
    selection-background-color: #00E5FF;
    selection-color: #1A1D23;
}

QLineEdit:focus, QComboBox:focus, QSpinBox:focus {
    border-color: #00E5FF;
}

QComboBox::drop-down {
    border: none;
    width: 20px;
}

QComboBox QAbstractItemView {
    background: #22262E;
    color: #D0D4DC;
    border: 1px solid #3A4050;
    selection-background-color: #003D4A;
}

QCheckBox {
    color: #D0D4DC;
    spacing: 6px;
}

QCheckBox::indicator {
    width: 14px;
    height: 14px;
    border: 1px solid #3A4050;
    border-radius: 2px;
    background: #22262E;
}

QCheckBox::indicator:checked {
    background: #00E5FF;
    border-color: #00E5FF;
}

QTextEdit {
    background: #0F1117;
    color: #7FBF7F;
    border: 1px solid #2E3340;
    border-radius: 3px;
    font-family: 'Courier New', monospace;
    font-size: 11px;
}

QScrollBar:vertical {
    background: #1A1D23;
    width: 8px;
    border: none;
}

QScrollBar::handle:vertical {
    background: #3A4050;
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #00E5FF;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QStatusBar {
    background: #0F1117;
    color: #7A8090;
    border-top: 1px solid #2E3340;
    font-size: 10px;
    letter-spacing: 1px;
}

QSplitter::handle {
    background: #2E3340;
    width: 1px;
}

QLabel#section_title {
    color: #00E5FF;
    font-size: 10px;
    letter-spacing: 2px;
    text-transform: uppercase;
}
"""

# Colores por estado
STATE_COLORS = {
    SystemState.IDLE:        ("#7A8090", "IDLE"),
    SystemState.CALIBRATION: ("#FFB300", "CALIBRATION"),
    SystemState.ACQUISITION: ("#00E5FF", "ACQUISITION"),
    SystemState.ANALYSIS:    ("#69F0AE", "ANALYSIS"),
}


class MainWindow(QMainWindow):
    """Ventana principal de la GUI RD53A."""

    def __init__(self):
        super().__init__()
        self.logger = logging.getLogger("MainWindow")
        self.setWindowTitle("RD53A Control System")
        self.resize(1400, 860)
        self.setStyleSheet(QSS)

        self._build_tabs()
        self._build_status_bar()
        self._start_state_polling()
        self.calibration_tab.plots_loading.connect(self._on_plots_loading)

        self.logger.info("MainWindow inicializado.")

    # ------------------------------------------------------------------
    # Construcción
    # ------------------------------------------------------------------
    def _build_tabs(self):
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)

        self.config_tab      = ConfigTab(self)
        self.calibration_tab = CalibrationTab(self)
        self.acquisition_tab = AcquisitionTab(self)

        self.tabs.addTab(self.config_tab,      "CONFIG")
        self.tabs.addTab(self.calibration_tab, "CALIBRATION")
        self.tabs.addTab(self.acquisition_tab, "ACQUISITION")

        # Conectar señal de configuración aplicada
        self.config_tab.config_applied.connect(self._on_config_applied)

    def _build_status_bar(self):
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # Indicador de estado de la máquina
        self._state_label = QLabel("● IDLE")
        self._state_label.setFont(QFont("Courier New", 10))
        self.status_bar.addPermanentWidget(self._state_label)

        # Separador
        sep = QLabel("  |  ")
        sep.setStyleSheet("color: #2E3340;")
        self.status_bar.addPermanentWidget(sep)

        # Info adicional
        self._info_label = QLabel("Sistema no configurado")
        self._info_label.setStyleSheet("color: #7A8090;")
        self.status_bar.addPermanentWidget(self._info_label)

        self._update_state_indicator()

    def _start_state_polling(self):
        """Refresca el indicador de estado cada 500ms."""
        self._state_timer = QTimer(self)
        self._state_timer.timeout.connect(self._update_state_indicator)
        self._state_timer.start(2000)

    # ------------------------------------------------------------------
    # Actualización de estado
    # ------------------------------------------------------------------
    def _update_state_indicator(self):
        state = SystemConfig.get_state()
        color, name = STATE_COLORS.get(state, ("#7A8090", "UNKNOWN"))
        self._state_label.setText(f"● {name}")
        self._state_label.setStyleSheet(f"color: {color}; font-weight: bold;")

    def _on_config_applied(self):
        """Callback cuando el usuario aplica la configuración."""
        self._info_label.setText(
            f"Ph2_ACF: {SystemConfig.get_ph2_acf_dir().name}  "
            f"| Cols: {SystemConfig.get_active_columns()}"
        )
        self.acquisition_tab.on_config_applied()
        self.logger.info("Configuración aplicada correctamente.")

    def _on_plots_loading(self, loading: bool):
        if loading:
            self._state_timer.stop()
        else:
            self._state_timer.start(2000)