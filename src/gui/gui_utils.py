"""gui_utils.py - Piezas de interfaz compartidas por las pestañas."""
from __future__ import annotations
from typing import Callable

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QTabBar, QTabWidget, QTextEdit, QToolButton

# Líneas máximas de los paneles de log: en tomas largas el log crece sin fin y
# un QTextEdit con cientos de miles de líneas ralentiza toda la GUI. Las líneas
# más antiguas se descartan (siguen en el log de consola).
LOG_MAX_LINES = 20_000


def make_log_view(placeholder: str = "") -> QTextEdit:
    """Panel de log de solo lectura con límite de líneas."""
    view = QTextEdit()
    view.setReadOnly(True)
    view.setPlaceholderText(placeholder)
    view.document().setMaximumBlockCount(LOG_MAX_LINES)
    return view


def append_log(view: QTextEdit, msg: str) -> None:
    """Añade una línea al log y lo desplaza hasta el final."""
    view.append(msg)
    bar = view.verticalScrollBar()
    bar.setValue(bar.maximum())


def install_tab_close_button(tabs: QTabWidget, index: int,
                             on_close: Callable[[int], None]) -> None:
    """Botón de cierre discreto para la pestaña `index`.

    El índice de la pestaña cambia al cerrar otras: se resuelve en el clic a
    partir de su widget, nunca se guarda el índice inicial.
    """
    button = QToolButton(tabs)
    button.setAutoRaise(True)
    button.setCursor(Qt.ArrowCursor)
    button.setToolTip("Close tab")
    button.setIcon(tabs.style().standardIcon(tabs.style().SP_TitleBarCloseButton))
    button.setStyleSheet(
        "QToolButton { background: transparent; border: none; padding: 0px; }"
        "QToolButton:hover { background: transparent; }"
    )
    widget = tabs.widget(index)
    button.clicked.connect(lambda *_: on_close(tabs.indexOf(widget)))
    tabs.tabBar().setTabButton(index, QTabBar.RightSide, button)
