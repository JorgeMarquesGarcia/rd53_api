"""
app.py - Entry point de la GUI RD53A.

Uso:
    python3 -m rd53_api.gui.app
"""
import sys
import logging
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from rd53_api.gui.main_window import MainWindow

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("RD53A Control")
    app.setOrganizationName("CERN")

    # Estilo base oscuro — se refina con QSS en MainWindow
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()