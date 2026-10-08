"""
app.py - Entry point de la GUI RD53A.

Uso:
    python3 -m src.gui.app
"""
import sys
import logging

# El logging se configura antes de importar el resto de módulos de la app
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
    force=True,
)

from PyQt5.QtWidgets import QApplication  # noqa: E402
from src.gui.main_window import MainWindow  # noqa: E402


def _log_unhandled_exception(exc_type, exc_value, exc_tb):
    """Excepción no capturada en un slot de Qt: se registra y la GUI sigue viva.

    Con el excepthook por defecto PyQt5 aborta la aplicación (qFatal), lo que
    en mitad de una toma de datos cerraría la ventana sin parar el DAQ.
    """
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    logging.getLogger("app").critical(
        "Unhandled exception", exc_info=(exc_type, exc_value, exc_tb))


def main():
    sys.excepthook = _log_unhandled_exception

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
