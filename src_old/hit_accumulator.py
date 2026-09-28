"""
Hit Accumulator for RD53A detector data.

This module provides a class to accumulate and filter hits across multiple iterations.
Data-only operations, no visualization logic.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger("HIT_ACCUMULATOR")


class HitAccumulator:
    """
    Acumula y filtra hits de múltiples iteraciones.
    
    Esta clase solo maneja datos, sin lógica de visualización.
    Para análisis y plots, usar el módulo physics.py
    
    Attributes:
        events: Lista de números de evento
        hit_cols: Lista de columnas de hits (RD53_hit_col)
        hit_rows: Lista de filas de hits (RD53_hit_row)
        hit_tots: Lista de valores TOT de hits
        bx_counters: Lista de contadores BX
        last_event: Último evento procesado (para filtrado incremental)
    """
    
    def __init__(self):
        """Inicializa el acumulador con listas vacías."""
        self.events = []
        self.hit_cols = []
        self.hit_rows = []
        self.hit_tots = []
        self.bx_counters = []
        self.last_event = 0  # Último evento procesado
    
    def add_hits(self, df_hits: pd.DataFrame) -> None:
        """
        Añade nuevos hits al acumulador.
        
        Solo añade eventos con número mayor al último evento procesado,
        evitando duplicados en procesamiento incremental.
        
        Args:
            df_hits: DataFrame con hits filtrados (eventos con hits > 0)
                    Debe contener columnas: 'event', 'RD53_hit_col', 'RD53_hit_row',
                    'RD53_hit_tot', 'FW_bx_counter'
        """
        # Filtrar eventos nuevos (después del último evento procesado)
        mask = df_hits['event'] > self.last_event
        
        if not mask.any():
            logger.info(f"No hay eventos nuevos (último: {self.last_event})")
            return
        
        logger.info(f"Añadiendo {mask.sum()} eventos nuevos (desde evento {self.last_event + 1})")
        
        # Extraer y guardar las variables necesarias (operación vectorizada directa)
        self.events.extend(df_hits.loc[mask, 'event'].tolist())
        self.hit_cols.extend(df_hits.loc[mask, 'RD53_hit_col'].tolist())
        self.hit_rows.extend(df_hits.loc[mask, 'RD53_hit_row'].tolist())
        self.hit_tots.extend(df_hits.loc[mask, 'RD53_hit_tot'].tolist())
        self.bx_counters.extend(df_hits.loc[mask, 'FW_bx_counter'].tolist())
        
        # Actualizar el último evento procesado
        self.last_event = df_hits.loc[mask, 'event'].max()
        logger.info(f"Último evento actualizado: {self.last_event}")
    
    def get_dataframe(self) -> pd.DataFrame:
        """
        Retorna un DataFrame con todos los hits acumulados.
        
        Returns:
            DataFrame con columnas: 'event', 'RD53_hit_col', 'RD53_hit_row',
            'RD53_hit_tot', 'FW_bx_counter'
        """
        return pd.DataFrame({
            'event': self.events,
            'RD53_hit_col': self.hit_cols,
            'RD53_hit_row': self.hit_rows,
            'RD53_hit_tot': self.hit_tots,
            'FW_bx_counter': self.bx_counters
        })
    
    def filter_by_event(self, min_event: Optional[int] = None, 
                       max_event: Optional[int] = None) -> pd.DataFrame:
        """
        Filtra hits por rango de eventos.
        
        Args:
            min_event: Evento mínimo (inclusive). Si None, desde el inicio.
            max_event: Evento máximo (inclusive). Si None, hasta el final.
            
        Returns:
            DataFrame filtrado
        """
        df = self.get_dataframe()
        
        if min_event is not None:
            df = df[df['event'] >= min_event]
        if max_event is not None:
            df = df[df['event'] <= max_event]
        
        return df
    
    def filter_by_tot(self, min_tot: Optional[int] = None, 
                     max_tot: Optional[int] = None) -> pd.DataFrame:
        """
        Filtra hits por rango de TOT.
        
        Args:
            min_tot: TOT mínimo (inclusive). Si None, sin límite inferior.
            max_tot: TOT máximo (inclusive). Si None, sin límite superior.
            
        Returns:
            DataFrame filtrado
        """
        df = self.get_dataframe()
        
        if min_tot is not None:
            df = df[df['RD53_hit_tot'] >= min_tot]
        if max_tot is not None:
            df = df[df['RD53_hit_tot'] <= max_tot]
        
        return df
    
    def filter_by_region(self, col_range: Optional[Tuple[int, int]] = None,
                        row_range: Optional[Tuple[int, int]] = None) -> pd.DataFrame:
        """
        Filtra hits por región espacial (columnas y/o filas).
        
        Args:
            col_range: Tupla (min_col, max_col) inclusive. Si None, sin filtrar columnas.
            row_range: Tupla (min_row, max_row) inclusive. Si None, sin filtrar filas.
            
        Returns:
            DataFrame filtrado
        """
        df = self.get_dataframe()
        
        if col_range is not None:
            min_col, max_col = col_range
            df = df[(df['RD53_hit_col'] >= min_col) & (df['RD53_hit_col'] <= max_col)]
        
        if row_range is not None:
            min_row, max_row = row_range
            df = df[(df['RD53_hit_row'] >= min_row) & (df['RD53_hit_row'] <= max_row)]
        
        return df
    
    def filter_by_bx_counter(self, min_bx: Optional[int] = None, 
                            max_bx: Optional[int] = None) -> pd.DataFrame:
        """
        Filtra hits por rango de BX counter (bunch crossing counter).
        
        Args:
            min_bx: BX counter mínimo (inclusive). Si None, sin límite inferior.
            max_bx: BX counter máximo (inclusive). Si None, sin límite superior.
            
        Returns:
            DataFrame filtrado
        """
        df = self.get_dataframe()
        
        if min_bx is not None:
            df = df[df['FW_bx_counter'] >= min_bx]
        if max_bx is not None:
            df = df[df['FW_bx_counter'] <= max_bx]
        
        return df
    
    def get_statistics(self) -> dict:
        """
        Calcula estadísticas básicas de los hits acumulados.
        
        Returns:
            Diccionario con estadísticas:
                - total_events: Número total de eventos
                - total_hits: Número total de hits
                - avg_tot: TOT promedio
                - std_tot: Desviación estándar TOT
                - min_tot, max_tot: Rango de TOT
                - first_event, last_event: Rango de eventos
        """
        if len(self.events) == 0:
            return {
                'total_events': 0,
                'total_hits': 0,
                'avg_tot': 0.0,
                'std_tot': 0.0,
                'min_tot': 0,
                'max_tot': 0,
                'first_event': 0,
                'last_event': 0
            }
        
        df = self.get_dataframe()
        
        # Expandir listas anidadas de TOT
        all_tots = []
        for tot_data in df['RD53_hit_tot']:
            if isinstance(tot_data, (list, np.ndarray)):
                all_tots.extend(tot_data)
            else:
                all_tots.append(tot_data)
        
        all_tots = np.array(all_tots)
        
        return {
            'total_events': len(df),
            'total_hits': len(all_tots),
            'avg_tot': float(np.mean(all_tots)),
            'std_tot': float(np.std(all_tots)),
            'min_tot': int(np.min(all_tots)),
            'max_tot': int(np.max(all_tots)),
            'first_event': int(df['event'].min()),
            'last_event': int(df['event'].max())
        }
    
    def save_to_file(self, filepath: Path) -> None:
        """
        Guarda los datos acumulados en un archivo CSV.
        
        Args:
            filepath: Ruta del archivo donde guardar (con extensión .csv)
        """
        df = self.get_dataframe()
        df.to_csv(filepath, index=False)
        logger.info(f"Datos guardados en: {filepath}")
    
    def append_from_uproot(self, uproot_file) -> int:
        """
        Extrae hits de un archivo uproot y los acumula.
        
        Args:
            uproot_file: Objeto uproot file (resultado de uproot.open())
            
        Returns:
            Número de hits (eventos) añadidos en esta operación
            
        Example:
            >>> import uproot
            >>> acc = HitAccumulator()
            >>> with uproot.open("data.root") as file:
            ...     new_hits = acc.append_from_uproot(file)
            >>> print(f"Added {new_hits} hits")
        """
        # Import local para evitar dependencias circulares
        from runsummary import extract_hits
        
        try:
            df_hits = extract_hits(uproot_file)
            initial_count = len(self.events)
            self.add_hits(df_hits)
            added = len(self.events) - initial_count
            
            logger.info(f"Appended {added} hits from uproot file")
            return added
            
        except Exception as e:
            logger.error(f"Error appending from uproot file: {e}", exc_info=True)
            return 0
    
    @classmethod
    def from_uproot(cls, uproot_file) -> "HitAccumulator":
        """
        Crea un HitAccumulator inicializado con datos de un archivo uproot.
        
        Args:
            uproot_file: Objeto uproot file (resultado de uproot.open())
            
        Returns:
            Nueva instancia de HitAccumulator con los datos cargados
            
        Example:
            >>> import uproot
            >>> with uproot.open("data.root") as file:
            ...     acc = HitAccumulator.from_uproot(file)
            >>> print(f"Loaded {len(acc)} events")
        """
        accumulator = cls()
        accumulator.append_from_uproot(uproot_file)
        logger.info(f"Created HitAccumulator from uproot file with {len(accumulator)} events")
        return accumulator
    
    def reset(self) -> None:
        """
        Reinicia el acumulador a su estado inicial.
        
        Limpia todas las listas de datos y resetea el contador de eventos.
        """
        self.events = []
        self.hit_cols = []
        self.hit_rows = []
        self.hit_tots = []
        self.bx_counters = []
        self.last_event = 0
        
        logger.info("HitAccumulator reseteado")
    
    def __len__(self) -> int:
        """Retorna el número de eventos acumulados."""
        return len(self.events)
    
    def __repr__(self) -> str:
        """Representación string del acumulador."""
        return (f"HitAccumulator(events={len(self.events)}, "
                f"last_event={self.last_event})")
    
    def __bool__(self) -> bool:
        """Retorna True si hay datos acumulados."""
        return len(self.events) > 0


__all__ = ["HitAccumulator"]
