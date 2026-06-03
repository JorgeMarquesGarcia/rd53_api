from __future__ import annotations
from abc import ABC, abstractmethod
import numpy as np
import ctypes

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import ROOT
ROOT.gROOT.SetBatch(True)

import matplotlib
matplotlib.use("Qt5Agg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas


# ---------------------------------------------------------------------------
# Mapeo: sufijo del nombre de figura -> clase plotter
# Se rellena automáticamente cuando cada subclase declara plot_key
# ---------------------------------------------------------------------------
PLOTTER_REGISTRY: dict[str, type[PlotterBase]] = {}

# ---------------------------------------------------------------------------
# Figuras de interés por tipo de análisis
# ---------------------------------------------------------------------------
ANALYSIS_PLOTS: dict[str, list[str]] = {
    "scurve":     ["SCurves", "Threshold1D"],
    "noise":      ["PixelAlive", "ToT2D", "ToT1D"],
    "pixelalive": ["PixelAlive"],
    "threqu":     ["ThrEqualization", "TDAC1D", "TDAC2D", "Masked2D"],
}


class PlotterBase(ABC):
    """Clase abstracta base para todos los plotters de RD53A.

    Cada subclase se registra automáticamente en PLOTTER_REGISTRY declarando
    el atributo de clase `plot_key` con el sufijo del nombre de la figura
    (p.ej. "SCurves", "Threshold1D", "PixelAlive"...).

    Flujo de uso:
        plotter = PlotterBase.for_key("SCurves", root_path, canvas_path)
        widget  = plotter.get_canvas()   # FigureCanvas para insertar en Qt
    """

    plot_key: str = ""  # subclases deben definir esto

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        if cls.plot_key:
            PLOTTER_REGISTRY[cls.plot_key] = cls

    # ------------------------------------------------------------------
    # Constructor
    # ------------------------------------------------------------------
    def __init__(self, root_path: str, canvas_path: str):
        self.root_path   = root_path
        self.canvas_path = canvas_path
        self.logger      = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"Inicializando {self.__class__.__name__}")
        self.logger.debug(f"root_path={root_path}, canvas_path={canvas_path}")
        self._figure     = Figure(figsize=(7, 4), tight_layout=True)
        self._ax         = self._figure.add_subplot(111)
        self._canvas     = FigureCanvas(self._figure)
        self._data: dict = {}

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------
    def get_canvas(self) -> FigureCanvas:
        """Extrae datos del fichero ROOT y devuelve el widget Qt listo para usar."""
        self.logger.info(f"Iniciando get_canvas()")
        try:
            self._data = self._extract()
            self.logger.info(f"Datos extraídos exitosamente")
            self._draw(self._ax, self._data)
            self.logger.info(f"Dibujado completado")
            self._canvas.draw()
            self.logger.info(f"Canvas renderizado")
            return self._canvas
        except Exception as e:
            self.logger.exception(f"Error en get_canvas(): {e}")
            raise

    def refresh(self, root_path: str | None = None, canvas_path: str | None = None) -> None:
        """Actualiza el plot con un nuevo fichero o canvas (reutiliza el widget Qt)."""
        self.logger.info(f"Iniciando refresh()")
        try:
            if root_path:
                self.logger.debug(f"Actualizando root_path: {root_path}")
                self.root_path = root_path
            if canvas_path:
                self.logger.debug(f"Actualizando canvas_path: {canvas_path}")
                self.canvas_path = canvas_path
            self._ax.cla()
            self.logger.debug(f"Axes limpiados")
            self._data = self._extract()
            self.logger.info(f"Datos extraídos en refresh()")
            self._draw(self._ax, self._data)
            self.logger.info(f"Dibujado completado en refresh()")
            self._canvas.draw()
            self.logger.info(f"Refresh completado exitosamente")
        except Exception as e:
            self.logger.exception(f"Error en refresh(): {e}")
            raise

    # ------------------------------------------------------------------
    # Métodos abstractos que cada subclase implementa
    # ------------------------------------------------------------------
    @abstractmethod
    def _extract(self) -> dict:
        """Lee el TCanvas desde ROOT y devuelve los datos como dict de numpy arrays."""
        ...

    @abstractmethod
    def _draw(self, ax, data: dict) -> None:
        """Dibuja sobre el Axes de matplotlib usando los datos extraídos."""
        ...

    # ------------------------------------------------------------------
    # Helpers compartidos para extracción desde ROOT
    # ------------------------------------------------------------------
    def _open_canvas(self) -> tuple[ROOT.TFile, ROOT.TCanvas]:
        """Abre el fichero ROOT y devuelve (file, canvas). El caller cierra el file."""
        self.logger.info(f"Abriendo fichero ROOT: {self.root_path}")
        try:
            f = ROOT.TFile(self.root_path, "READ")
            if not f or f.IsZombie():
                self.logger.error(f"No se pudo abrir el fichero ROOT: {self.root_path}")
                raise ValueError(f"No se pudo abrir el fichero ROOT: {self.root_path}")
            self.logger.debug(f"Fichero abierto. Buscando canvas: {self.canvas_path}")
            
            canvas = f.Get(self.canvas_path)
            if not canvas or not isinstance(canvas, ROOT.TCanvas):
                self.logger.error(
                    f"No se encontró un TCanvas válido en '{self.canvas_path}' "
                    f"dentro de '{self.root_path}'"
                )
                f.Close()
                raise ValueError(
                    f"No se encontró un TCanvas en '{self.canvas_path}' "
                    f"dentro de '{self.root_path}'"
                )
            self.logger.info(f"Canvas encontrado exitosamente")
            return f, canvas
        except Exception as e:
            self.logger.exception(f"Error al abrir canvas: {e}")
            raise

    def _get_primitive(self, canvas: ROOT.TCanvas, classname_prefix: str):
        """Devuelve la primera primitiva del canvas que coincida con el prefijo."""
        self.logger.debug(f"Buscando primitiva con prefijo: {classname_prefix}")
        for p in canvas.GetListOfPrimitives():
            if p.ClassName().startswith(classname_prefix):
                self.logger.info(f"Primitiva encontrada: {p.ClassName()}")
                return p
        self.logger.warning(f"No se encontró primitiva con prefijo '{classname_prefix}'")
        return None

    @staticmethod
    def _th1_to_dict(h) -> dict:
        """Convierte un TH1x de ROOT a numpy arrays."""
        logger.debug(f"Convirtiendo TH1 '{h.GetTitle()}' a diccionario")
        nx = h.GetNbinsX()
        logger.debug(f"TH1 tiene {nx} bins")
        result = {
            "values": np.array([h.GetBinContent(i) for i in range(1, nx + 1)]),
            "edges":  np.array([h.GetXaxis().GetBinLowEdge(i) for i in range(1, nx + 2)]),
            "xlabel": h.GetXaxis().GetTitle(),
            "ylabel": h.GetYaxis().GetTitle(),
            "title":  h.GetTitle(),
        }
        logger.info(f"TH1 convertido exitosamente. Rango valores: [{result['values'].min():.2f}, {result['values'].max():.2f}]")
        return result

    @staticmethod
    def _th2_to_dict(h) -> dict:
        """Convierte un TH2x de ROOT a numpy arrays."""
        logger.debug(f"Convirtiendo TH2 '{h.GetTitle()}' a diccionario")
        nx = h.GetNbinsX()
        ny = h.GetNbinsY()
        logger.debug(f"TH2 tiene {nx}x{ny} bins")
        values = np.array(h, dtype=np.float64).reshape(nx+2, ny+2)[1:-1, 1:-1]
        if values.sum() == 0:
            raise ValueError(f"Histograma '{h.GetName()}' está vacío (0 entradas)")
        return {
            "values": values,
            "xedges": np.array([h.GetXaxis().GetBinLowEdge(i) for i in range(1, nx+2)]),
            "yedges": np.array([h.GetYaxis().GetBinLowEdge(i) for i in range(1, ny+2)]),
            "xlabel": h.GetXaxis().GetTitle(),
            "ylabel": h.GetYaxis().GetTitle(),
            "title":  h.GetTitle(),
        }

    # ------------------------------------------------------------------
    # Factory methods
    # ------------------------------------------------------------------
    @staticmethod
    def for_key(plot_key: str, root_path: str, canvas_path: str) -> "PlotterBase":
        """Devuelve la instancia del plotter correcto según el sufijo de figura."""
        logger.info(f"Buscando plotter para plot_key='{plot_key}'")
        cls = PLOTTER_REGISTRY.get(plot_key)
        if cls is None:
            logger.error(
                f"No hay plotter registrado para '{plot_key}'. "
                f"Disponibles: {list(PLOTTER_REGISTRY.keys())}"
            )
            raise KeyError(
                f"No hay plotter registrado para '{plot_key}'. "
                f"Disponibles: {list(PLOTTER_REGISTRY.keys())}"
            )
        logger.info(f"Plotter encontrado: {cls.__name__}")
        return cls(root_path, canvas_path)

    @staticmethod
    def for_analysis(analysis: str, root_path: str, chip_dir: str) -> list["PlotterBase"]:
        """Devuelve todos los plotters necesarios para un tipo de análisis.

        Args:
            analysis:  'scurve' | 'noise' | 'pixelalive' | 'threqu'
            root_path: ruta al fichero .root
            chip_dir:  ruta hasta el directorio del chip dentro del .root,
                       p.ej. 'Detector/Board_0/OpticalGroup_0/Hybrid_2/Chip_0'
                       El canvas_path completo se construye dentro de cada plotter.
        """
        logger.info(f"Creando plotters para análisis: '{analysis}'")
        keys = ANALYSIS_PLOTS.get(analysis, [])
        if not keys:
            logger.error(
                f"Análisis desconocido: '{analysis}'. "
                f"Disponibles: {list(ANALYSIS_PLOTS.keys())}"
            )
            raise ValueError(
                f"Análisis desconocido: '{analysis}'. "
                f"Disponibles: {list(ANALYSIS_PLOTS.keys())}"
            )
        logger.info(f"Se van a crear {len(keys)} plotters: {keys}")
        plotters = [PlotterBase.for_key(k, root_path, chip_dir) for k in keys]
        logger.info(f"Todos los plotters creados exitosamente")
        return plotters