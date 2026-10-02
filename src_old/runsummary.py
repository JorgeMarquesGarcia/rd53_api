from __future__ import annotations
import os 
import pandas as pd
import numpy as np
import logging
from pathlib import Path 

""""Index(['event', 'FW_block_size', 'FW_tlu_trigger_id', 'FW_trigger_tag',
       'FW_tdc', 'FW_l1a_counter', 'FW_bx_counter', 'FW_event_status',
       'FW_nframes', 'FW_frame_event_error_code', 'FW_frame_event_hybrid_id',
       'FW_frame_event_chip_lane', 'FW_frame_event_l1a_size',
       'FW_frame_event_chip_type', 'FW_frame_event_frame_delay',
       'RD53_frame_event_chip_id_mod4', 'RD53_frame_event_trigger_id',
       'RD53_frame_event_trigger_tag', 'RD53_frame_event_bc_id',
       'RD53_frame_event_status', 'RD53_frame_event_nhits', 'RD53_hit_row',
       'RD53_hit_col', 'RD53_hit_tot'],
      dtype='object')
      
        COLUMNS NAMES"""


logger = logging.getLogger("STATS")


def extract_data(file): 
    """Extract data from ROOT file in two Dataframe, one with all information 
    and other only with events with hits."""
    try: 
        ttrees = [key for key, classname in file.classnames().items() if classname == "TTree"]
        if not ttrees: 
            raise ValueError("No TTree found in the ROOT file.")
        tree = file[ttrees[0]]
        df = tree.arrays(library="pd")

        if 'RD53_frame_event_nhits' not in df.columns:
            raise ValueError("The required column 'RD53_frame_event_nhits' is missing in the data. Corrupted file")
        
        df1 = df[df["RD53_frame_event_nhits"] > 0]
    
    except Exception as e:
        logger.error("Error extrayendo datos del ROOT: %s", e, exc_info=True)
        raise

    return df, df1


def extract_all_data(file):
    """Extract all data from ROOT file into a single DataFrame.
    
    Args:
        file: uproot file object
        
    Returns:
        DataFrame with all events (including events with no hits)
    """
    try:
        ttrees = [key for key, classname in file.classnames().items() if classname == "TTree"]
        if not ttrees:
            raise ValueError("No TTree found in the ROOT file.")
        tree = file[ttrees[0]]
        df = tree.arrays(library="pd")
        
        if 'RD53_frame_event_nhits' not in df.columns:
            raise ValueError("The required column 'RD53_frame_event_nhits' is missing in the data. Corrupted file")
        
        if len(df) == 0:
            logger.warning("No events found in ROOT file")
        
        return df
    
    except Exception as e:
        logger.error("Error extrayendo todos los datos del ROOT: %s", e, exc_info=True)
        raise


def extract_hits(file):
    """Extract only events with hits from ROOT file.
    
    Args:
        file: uproot file object
        
    Returns:
        DataFrame containing only events with hits (RD53_frame_event_nhits > 0)
    """
    try:
        ttrees = [key for key, classname in file.classnames().items() if classname == "TTree"]
        if not ttrees:
            raise ValueError("No TTree found in the ROOT file.")
        tree = file[ttrees[0]]
        df = tree.arrays(library="pd")
        
        if 'RD53_frame_event_nhits' not in df.columns:
            raise ValueError("The required column 'RD53_frame_event_nhits' is missing in the data. Corrupted file")
        
        df_hits = df[df["RD53_frame_event_nhits"] > 0]
        
        if len(df_hits) == 0:
            logger.warning("No events with hits found in ROOT file")
        
        return df_hits
    
    except Exception as e:
        logger.error("Error extrayendo hits del ROOT: %s", e, exc_info=True)
        raise

def calculate_statistics(root_file, output_file, df, df1, Vthreshold_LIN):
    """
    Calculate statistics from ROOT file data.
    
    Args:
        root_file: Run identifier or filename
        output_file: Path to save statistics summary
        df: DataFrame with all events OR HitAccumulator instance
        df1: DataFrame with hits only (ignored if df is HitAccumulator)
        Vthreshold_LIN: Threshold voltage value
        
    Returns:
        Dictionary with calculated statistics
        
    Note:
        If df is a HitAccumulator instance, df1 parameter is ignored and
        data is extracted from the accumulator automatically.
    """
    # Detectar si df es un HitAccumulator
    from hit_accumulator import HitAccumulator
    
    if isinstance(df, HitAccumulator):
        # Extraer DataFrames desde el accumulator
        logger.info("Detected HitAccumulator, extracting data...")
        df_all = df.get_dataframe()
        
        # Para df1, necesitamos el DataFrame completo (con RD53_frame_event_nhits)
        # pero HitAccumulator solo guarda hits, así que df1 = df_all (todos son hits)
        df1 = df_all
        
        # df completo: en este caso no tenemos eventos sin hits,
        # así que total_events = events con hits
        df = df_all
        
        logger.info(f"Extracted {len(df)} events from HitAccumulator")
    
    stats_summary = {
        "Run number":  root_file, 
        "Vthreshold_LIN": Vthreshold_LIN,
        "Total events": len(df),
        "Events with hits": len(df1),
        "Hit efficiency (%)": (len(df1) / len(df) * 100) if len(df) > 0 else 0,
    }

    if len(df1) > 0:
        try:
            stats_summary.update(_calculate_hit_stats(df1))
            if "RD53_hit_tot" in df1.columns:
                stats_summary.update(_calculate_tot_stats(df1))
        except Exception as e:
            logger.warning("Error calculating statistics: %s", e)

    _save_summary(stats_summary,output_file=output_file)
    logger.info("Statistics calculation completed & recorded.")
    return stats_summary


def _calculate_hit_stats(df1):
    nhits = df1["RD53_frame_event_nhits"].to_numpy()
    if nhits.size == 0:
        raise {}
    
    hit_stats = {
        "Total hits": np.sum(nhits),
        "Average hits per event with hits": np.mean(nhits),
        "Max hits in a single event": np.max(nhits),
        "Min hits in a single event": np.min(nhits),
    }
    logger.debug("Hit statistics calculated: %s", hit_stats)
    return hit_stats


def _calculate_tot_stats(df1):
    all_tot = []
    for tot_data in df1["RD53_hit_tot"]:
        if hasattr(tot_data, 'to_list'):
            tot_data = tot_data.to_list()
        if not isinstance(tot_data, (list, np.ndarray)):
            tot_data = [tot_data]
        all_tot.extend([t for t in tot_data if pd.notna(t)])
    
    if not all_tot:
        return {}
    
    tot_array = np.array(all_tot)
    tot_stats = {
        "Average TOT": np.mean(tot_array),
        "Max TOT": np.max(tot_array),
        "Min TOT": np.min(tot_array),
        "Std Dev TOT": np.std(tot_array),
    }
    logger.debug("TOT statistics calculated: %s", tot_stats)
    return tot_stats

def _save_summary(stats_summary, output_file: Path | None = None):
    try: 
        if output_file is None:
            output_file = Path(__file__).resolve().parent / "statistics_summary.txt"

        with open(output_file, "a", encoding="utf-8") as f:
            logger.info("Saving statistics summary to %s.", output_file)
            f.write("=== Statistics Summary === \n\n")
            for key, value in stats_summary.items():
                if isinstance(value, float):
                    f.write(f"{key}: {value:.2f}\n")
                else: 
                    f.write(f"{key}: {value}\n")
            f.write("\n")
        logger.info("Statistics summary saved successfully in %s.", output_file)

    except Exception as e:
        logger.error("Error saving statistics summary: %s", e, exc_info=True)
        raise

def save_summary_dict(summary_dict: dict, output_file: Path, header: str = "RESUMEN"):
    try: 
        if output_file is None:
            output_file = Path(__file__).resolve().parent / "statistics_summary.txt"

        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"=== {header} ===\n\n")
            for key, value in summary_dict.items():
                f.write(f"{key}: {value}\n")
            f.write("\n")
        logger.info("Noise Summary '%s' saved to %s", header, output_file)

    except Exception as e:
        logger.error("Error saving noise summary: %s", e, exc_info=True)
        raise


def add_masked_pixels_info(stats_summary: dict, masked_count: int, total_pixels: int, percentage: float) -> dict:
    """
    Add masked pixels information to the statistics summary.
    
    Args:
        stats_summary: Existing statistics dictionary
        masked_count: Number of masked pixels
        total_pixels: Total number of pixels in active region
        percentage: Percentage of masked pixels
        
    Returns:
        Updated statistics dictionary
    """
    stats_summary["Masked pixels (absolute)"] = masked_count
    stats_summary["Total pixels in active region"] = total_pixels
    stats_summary["Masked pixels (%)"] = round(percentage, 2)
    
    logger.info("Added masked pixels info to statistics: %d / %d (%.2f%%)", 
               masked_count, total_pixels, percentage)
    
    return stats_summary


__all__ = [
    "extract_data",
    "extract_all_data",
    "extract_hits",
    "calculate_statistics",
    "save_summary_dict",
    "add_masked_pixels_info",
]

