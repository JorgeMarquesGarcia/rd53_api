from __future__ import annotations
from abc import ABC, abstractmethod
import numpy as np

import logging
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
    "gain":       ["Gain", "SlopeLowQ1D", "InterceptLowQ1D", "Chi2DoF1D"],
    # El .root de GainOptimization incluye el gain scan final con el KRUM elegido
    "gainopt":    ["KrumCurr", "Gain", "SlopeLowQ1D", "InterceptLowQ1D"],
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
        self.logger.info("Iniciando get_canvas()")
        try:
            self._data = self._extract()
            self.logger.info("Datos extraídos exitosamente")
            self._draw(self._ax, self._data)
            self.logger.info("Dibujado completado")
            self._canvas.draw()
            self.logger.info("Canvas renderizado")
            return self._canvas
        except Exception as e:
            self.logger.exception(f"Error en get_canvas(): {e}")
            raise

    def refresh(self, root_path: str | None = None, canvas_path: str | None = None) -> None:
        """Actualiza el plot con un nuevo fichero o canvas (reutiliza el widget Qt)."""
        self.logger.info("Iniciando refresh()")
        try:
            if root_path:
                self.logger.debug(f"Actualizando root_path: {root_path}")
                self.root_path = root_path
            if canvas_path:
                self.logger.debug(f"Actualizando canvas_path: {canvas_path}")
                self.canvas_path = canvas_path
            self._ax.cla()
            self.logger.debug("Axes limpiados")
            self._data = self._extract()
            self.logger.info("Datos extraídos en refresh()")
            self._draw(self._ax, self._data)
            self.logger.info("Dibujado completado en refresh()")
            self._canvas.draw()
            self.logger.info("Refresh completado exitosamente")
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
            self.logger.info("Canvas encontrado exitosamente")
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
    def _th2_flat_buffer(h) -> np.ndarray | None:
        """Buffer interno del TH2 (con under/overflow) como array plano, o None.

        Primero el puntero de GetArray() (rápido); si esta versión de PyROOT no
        lo permite, el protocolo de secuencia de numpy.
        """
        size = h.GetSize()
        try:
            buf = h.GetArray()
            buf.reshape((size,))
            flat = np.array(buf, dtype=np.float64)
            if flat.size == size:
                return flat
        except Exception:
            pass
        try:
            return np.asarray(h, dtype=np.float64).ravel()
        except Exception:
            return None

    @staticmethod
    def _th2_matches(h, values: np.ndarray) -> bool:
        """Comprueba la suma total y, contra GetBinContent, la fila y la columna completas del máximo."""
        if not np.isclose(values.sum(), h.Integral(), rtol=1e-6, atol=1e-9):
            return False
        ix, iy = np.unravel_index(int(np.argmax(values)), values.shape)
        nx, ny = values.shape
        col_ok = all(np.isclose(values[ix, j], h.GetBinContent(int(ix) + 1, j + 1)) for j in range(ny))
        row_ok = all(np.isclose(values[i, iy], h.GetBinContent(i + 1, int(iy) + 1)) for i in range(nx))
        return col_ok and row_ok

    @staticmethod
    def _th2_values(h) -> np.ndarray:
        """Contenido de un TH2 como array (nx, ny) indexado [bin_x, bin_y], sin under/overflow.

        ROOT guarda los bins con x variando más rápido (bin global =
        binx + (nx + 2) * biny). El resultado se verifica contra GetBinContent
        y, si no coincide (otra versión de PyROOT), se lee bin a bin.
        """
        nx, ny = h.GetNbinsX(), h.GetNbinsY()
        values = None
        flat = PlotterBase._th2_flat_buffer(h)
        if flat is not None and flat.size == (nx + 2) * (ny + 2):
            values = flat.reshape(ny + 2, nx + 2)[1:-1, 1:-1].T
        elif flat is not None and flat.size == nx * ny:
            values = flat.reshape(nx, ny)   # interfaz UHI: values() sin flow, [x, y]

        if values is None or not PlotterBase._th2_matches(h, values):
            logger.debug("TH2 '%s': lectura bin a bin", h.GetName())
            values = np.array([[h.GetBinContent(ix, iy) for iy in range(1, ny + 1)]
                               for ix in range(1, nx + 1)], dtype=np.float64)
        return np.ascontiguousarray(values)

    @staticmethod
    def _th2_to_dict(h) -> dict:
        """Convierte un TH2x de ROOT a numpy arrays."""
        logger.debug(f"Convirtiendo TH2 '{h.GetTitle()}' a diccionario")
        nx = h.GetNbinsX()
        ny = h.GetNbinsY()
        logger.debug(f"TH2 tiene {nx}x{ny} bins")
        values = PlotterBase._th2_values(h)
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
            analysis:  'scurve' | 'noise' | 'pixelalive' | 'threqu' | 'gain' | 'gainopt'
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
        logger.info("Todos los plotters creados exitosamente")
        return plotters