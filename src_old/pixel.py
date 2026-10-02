from __future__ import annotations
import pandas as pd
import os 
import numpy as np
from ManipulateITchipMask import Mask, NCOLS, NROWS, saveCFGfile, readCFGfile
from runsummary import save_summary_dict
from pathlib import Path
import logging 
import statistics as stats

LAB_MODE = False
# Path configuration based on mode
if LAB_MODE:
    # Lab environment (Linux)
    RESULTS_PATH = "/home/usuario/testing/CosmicRays/Ph2_ACF_JM/RD53A/Results"
    ROOT_PATH = RESULTS_PATH
    CONFIG_PATH = RESULTS_PATH
else:
    # Desktop environment (Windows)
    ROOT_PATH = "C:\\Users\\jmarques\\Documents\\00_Projects\\02_TFM\\01_Lab\\Python\\Data"
    CONFIG_PATH = r'C:\\Users\\jmarques\\Documents\\00_Projects\\02_TFM\\01_Lab\\Python\\ConfigFiles'

logger = logging.getLogger("PIXEL") 

class PixelAnalyzer: 
    def __init__(self, df_hits: pd.DataFrame):
        self.df_hits = df_hits
        self.pixel_data = {}
        self.hits_df = None  # DataFrame para análisis más fáciles
        self.noisy_pixels = {}
        self.latency_results = {}

        logger.debug("PixelAnalyzer initialized with %d hit records.", len(df_hits))

    def analyze_pixels(self):

        pixel_data = {}
        hits_list = []  # Para crear DataFrame
        
        for i in range(len(self.df_hits)):
            rows = self.df_hits.RD53_hit_row.iloc[i]
            cols = self.df_hits.RD53_hit_col.iloc[i]
            tots = self.df_hits.RD53_hit_tot.iloc[i]
            nevent = self.df_hits.event.iloc[i]

            rows = rows.to_list() if hasattr(rows, 'to_list') else [rows] if not isinstance(rows, (list, np.ndarray)) else rows
            cols = cols.to_list() if hasattr(cols, 'to_list') else [cols] if not isinstance(cols, (list, np.ndarray)) else cols
            tots = tots.to_list() if hasattr(tots, 'to_list') else [tots] if not isinstance(tots, (list, np.ndarray)) else tots
            nevent = nevent.to_list() if hasattr(nevent, 'to_list') else [nevent] if not isinstance(nevent, (list, np.ndarray)) else nevent

            for r, c, t, ne in zip(rows, cols, tots, nevent):
                if isinstance(r, (int, np.integer)) and isinstance(c, (int, np.integer)) and pd.notna(t):
                    key = (r, c)
                    if key not in pixel_data:
                        pixel_data[key] = {'nhits': 0, 'TOTs': [], 'nevent': []}
                    pixel_data[key]['nhits'] += 1
                    pixel_data[key]['TOTs'].append(float(t))
                    pixel_data[key]['nevent'].append(int(ne))
                    
                    # También guardar para DataFrame
                    hits_list.append({
                        'row': r,
                        'col': c,
                        'TOT': float(t),
                        'nevent': int(ne)
                    })


        self.pixel_data = pixel_data
        self.hits_df = pd.DataFrame(hits_list)  # Crear DataFrame con todos los hits
        logger.debug("Pixel hits analyzed: %d pixels found.", len(pixel_data))
        logger.debug("DataFrame created with %d hits.", len(self.hits_df))

        return pixel_data

    def get_dataframes(self) -> tuple[pd.DataFrame, pd.DataFrame]:
        """
        Get both DataFrames for external analysis.
        
        Returns:
            tuple: (df_hits, hits_df)
                - df_hits: Original DataFrame from ROOT with all events (awkward arrays)
                - hits_df: Processed DataFrame with individual hits (columns: row, col, TOT, nevent)
        """
        return self.df_hits, self.hits_df

    def noise_scan(self, save_summary_path: str | None = None):
        # The probability of two hits in the same pixel in one run is extremely low.
        noisy_pixels = {k: v for k, v in self.pixel_data.items() if v['nhits'] > 1}# and np.max(v['TOTs']) < 2}
        self.noisy_pixels = noisy_pixels

        save_summary_dict(noisy_pixels, output_file=save_summary_path, header="NOISY PIXELS (nhits>1)")

        return noisy_pixels

    def latency_scan(self, df_original: pd.DataFrame, groupSize: int | None = 10):
        # Verificar que el DataFrame de hits existe
        if self.hits_df is None or self.hits_df.empty:
            logger.error("No hits data available. Run analyze_pixels() first.")
            return None
        
        # Acceso directo a la columna de nevents desde el DataFrame!
        all_nevents = self.hits_df['nevent'].tolist()
        
        print(f"Total de eventos a analizar: {len(all_nevents)}")
        logger.debug("Total nevents: %d", len(all_nevents))
        
        position_in_group = [None] * len(all_nevents)
        
        for i in range(len(all_nevents)):
            # Obtener el valor del contador bc_id del evento dado
            bc_id = df_original['RD53_frame_event_bc_id'].iloc[all_nevents[i]]
            if hasattr(bc_id, 'to_list'):  # Convertir a lista si es un tipo awkward
                bc_id = bc_id.to_list()
            if isinstance(bc_id, list):
                bc_id = bc_id[0]  # Tomar el primer valor si es una lista

            end_idx = all_nevents[i]
            while end_idx < len(df_original) - 1:
                next_bc_id = df_original['RD53_frame_event_bc_id'].iloc[end_idx + 1]
                if hasattr(next_bc_id, 'to_list'):
                    next_bc_id = next_bc_id.to_list()
                if isinstance(next_bc_id, list):
                    next_bc_id = next_bc_id[0]
                if next_bc_id != bc_id + 1:  # Si no es consecutivo, detenerse
                    break
                bc_id += 1
                end_idx += 1
            logger.debug("Event %d: bc_id=%d, end_idx=%d", all_nevents[i], bc_id, end_idx)

            # Calcular el inicio del grupo (start_idx)
            #start_idx = max(0, end_idx - (groupSize - 1))

            # Calcular la posición dentro del grupo
            position_in_group[i] = groupSize - (end_idx - all_nevents[i])
        
        print(f"Posiciones en grupo: {position_in_group}")
        latency, sigma = self.__latency_analysis(position_in_group)
        logger.info("Latency analysis completed: Latency=%f, Sigma=%f", latency, sigma)

        self.latency_results = {
            'latency': latency,
            'sigma': sigma,
            'position_in_group': position_in_group
        }
        
        return self.latency_results

    def __latency_analysis(self, position_in_group):
        latency = stats.mean(position_in_group)
        nTrigEvent = stats.stdev(position_in_group) if len(position_in_group) > 1 else 0
        return latency, nTrigEvent



    def make_mask_from_noise(self, orgMask: Mask | None = None) -> Mask:
        mask = Mask()
        mask.preset(orgMask)  # empieza con todo '1'

        if orgMask:
            try:
                for row in range(NROWS):
                    for col in range(NCOLS):
                        if col >= len(orgMask.enable):
                            logger.error("Column %d out of range (orgMask has %d columns)", col, len(orgMask.enable))
                            break
                        if row >= len(orgMask.enable[col]):
                            logger.error("Row %d out of range in column %d (has %d rows)", row, col, len(orgMask.enable[col]))
                            break
                        if orgMask.enable[col][row] == '0':
                            mask.enable[col][row] = '0'
            except Exception as e:
                logger.warning("Error in the original mask: %s", e)
                logger.exception("Full exception details:")

        # Poner a 0 los píxeles ruidosos
        for (r, c) in self.noisy_pixels.keys():
            if 0 <= r < NROWS and 0 <= c < NCOLS:
                mask.enable[c][r] = '0'
            else:
                logger.warning("Pixel out of range: (%d,%d)", r, c)

        logger.info("Mask created from noisy pixels.")
        return mask
    
    def count_masked_pixels(self, mask: Mask, col_start: int, col_stop: int) -> tuple[int, int, float]:
        """
        Count masked pixels (ENABLE='0') in the active column range.
        
        Args:
            mask: The Mask object to analyze
            col_start: Starting column (inclusive)
            col_stop: Ending column (inclusive)
            
        Returns:
            Tuple of (masked_count, total_pixels, percentage)
        """
        masked_count = 0
        total_pixels = 0
        
        # Iterate through the active column range
        for col in range(col_start, col_stop + 1):
            if col >= len(mask.enable):
                logger.warning("Column %d out of range (mask has %d columns)", col, len(mask.enable))
                continue
                
            for row in range(NROWS):
                if row >= len(mask.enable[col]):
                    logger.warning("Row %d out of range in column %d (has %d rows)", 
                                 row, col, len(mask.enable[col]))
                    continue
                    
                total_pixels += 1
                if mask.enable[col][row] == '0':
                    masked_count += 1
        
        percentage = (masked_count / total_pixels * 100) if total_pixels > 0 else 0
        
        logger.info("Masked pixels count: %d / %d (%.2f%%)", masked_count, total_pixels, percentage)
        
        return masked_count, total_pixels, percentage
    
    def save_mask(self, mask, filename: str | None = None):
        """
        Guarda la máscara generada. Si 'filename' se proporciona, sobrescribe ese archivo.
        Si no, solicita un nuevo nombre al usuario.
        
        En modo LAB, guarda la máscara un nivel arriba de CONFIG_PATH.
        """
        try:
            if filename:
                # Sobrescribir directamente la máscara original
                file_path = Path(filename)
                logger.info("Overwriting existing mask file: %s", file_path)
            else:
                # Crear una nueva máscara con nombre elegido por el usuario
                mask_name_input = input("Enter the name for the new mask file: ").strip()
                if not mask_name_input.lower().endswith(".txt"):
                    mask_name_input += ".txt"
                
                # En modo LAB, guardar un nivel arriba de CONFIG_PATH
                if LAB_MODE:
                    output_dir = Path(CONFIG_PATH).parent
                    logger.info("LAB mode: Saving mask to parent directory: %s", output_dir)
                else:
                    output_dir = Path(CONFIG_PATH)
                
                output_dir.mkdir(parents=True, exist_ok=True)
                file_path = output_dir / mask_name_input
                logger.info("Saving new mask file: %s", file_path)

            saveCFGfile(str(file_path), mask)
            logger.info("Mask successfully saved to %s", file_path)

        except Exception as e:
            logger.error("[PIXEL] Error saving mask to %s: %s", file_path, e, exc_info=True)
            raise


__all__ = ["PixelAnalyzer"]