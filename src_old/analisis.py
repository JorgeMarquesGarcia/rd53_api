from __future__ import annotations
import logging
import time
import subprocess
from pathlib import Path
from datetime import datetime
import matplotlib.pyplot as plt
import pandas as pd

# Import existing functions
from files import ROOTFileHandler, FileSelectionError
from runsummary import extract_data

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def analyze_root_file(root_file_path: str | Path):
    """
    Analyze a ROOT file to extract timing and event variables.
    
    Args:
        root_file_path: Path to the ROOT file to analyze
        
    Returns:
        Tuple of (df, df_hits) - two pandas DataFrames
    """
    root_file_path = Path(root_file_path)
    
    if not root_file_path.exists():
        raise FileNotFoundError(f"ROOT file not found: {root_file_path}")
    
    logger.info("=" * 80)
    logger.info("Analyzing ROOT file: %s", root_file_path.name)
    logger.info("=" * 80)
    
    # Get the directory containing the ROOT file
    root_dir = root_file_path.parent
    
    # Use ROOTFileHandler to open the file
    root_handler = ROOTFileHandler(root_dir)
    root_file, root_path = root_handler.open_file(filename=root_file_path.name)
    
    logger.info("Successfully opened ROOT file")
    
    # Extract data using runsummary.extract_data
    df, df_hits = extract_data(root_file)
    
    logger.info("Extracted data:")
    logger.info("  Total events: %d", len(df))
    logger.info("  Events with hits: %d", len(df_hits))
    
    # Display available columns
    logger.info("\nAvailable columns in df:")
    for col in df.columns:
        logger.info("  - %s", col)
    
    # Display basic statistics for timing-related columns
    timing_columns = [col for col in df.columns if 'time' in col.lower() or 
                     'tdc' in col.lower() or 'bc' in col.lower() or 
                     'l1a' in col.lower() or 'trigger' in col.lower()]
    
    if timing_columns:
        logger.info("\nTiming-related columns found:")
        for col in timing_columns:
            logger.info("  - %s", col)
            logger.info("    Type: %s", df[col].dtype)
            logger.info("    Range: %s to %s", df[col].min(), df[col].max())
            logger.info("    Mean: %s", df[col].mean() if pd.api.types.is_numeric_dtype(df[col]) else "N/A")
    
    return df, df_hits


def print_dataframe_summary(df: pd.DataFrame, name: str = "DataFrame"):
    """Print a summary of the DataFrame."""
    logger.info("\n" + "=" * 80)
    logger.info("%s Summary", name)
    logger.info("=" * 80)
    logger.info("Shape: %s", df.shape)
    logger.info("\nColumn types:")
    logger.info(df.dtypes)
    logger.info("\nFirst few rows:")
    logger.info(df.head())
    logger.info("\nBasic statistics:")
    logger.info(df.describe())


def inspect_root_file(root_file):
    """
    Inspect ROOT file structure to understand its contents.
    
    Args:
        root_file: Opened ROOT file object
    """
    logger.info("\n" + "=" * 80)
    logger.info("ROOT File Inspection")
    logger.info("=" * 80)
    
    # List all keys and their types
    logger.info("\nAvailable objects in file:")
    for key, classname in root_file.classnames().items():
        logger.info("  - %s: %s", key, classname)
    
    # Find TTrees
    ttrees = [key for key, classname in root_file.classnames().items() if classname == "TTree"]
    
    if ttrees:
        logger.info("\nTTree(s) found: %d", len(ttrees))
        for tree_name in ttrees:
            try:
                tree = root_file[tree_name]
                logger.info("\n  Tree: %s", tree_name)
                logger.info("    Entries: %d", tree.num_entries)
                logger.info("    Branches:")
                for branch_name in tree.keys():
                    logger.info("      - %s", branch_name)
            except Exception as e:
                logger.warning("    Error reading tree %s: %s", tree_name, e)
    else:
        logger.warning("No TTrees found in file!")
    
    return ttrees


def plot_timing_variables(df: pd.DataFrame, save_path: Path | None = None, title_suffix: str = "", max_events: int = 10000):
    """
    Plot timing and trigger-related variables vs event number.
    
    Args:
        df: DataFrame with event data
        save_path: Optional path to save the figure
        title_suffix: Optional suffix to add to the title
        max_events: Maximum number of events to plot (default: 10000)
    """
    # Limit DataFrame to max_events
    if len(df) > max_events:
        logger.info("Limiting plot to first %d events (total: %d)", max_events, len(df))
        df_plot = df.head(max_events).copy()
    else:
        df_plot = df
    
    # Columns to plot (removed RD53_frame_event_status)
    columns_to_plot = [
        'FW_tlu_trigger_id',
        'FW_trigger_tag',
        'FW_l1a_counter',
        'FW_bx_counter',
        'RD53_frame_event_trigger_id',
        'RD53_frame_event_trigger_tag',
        'RD53_frame_event_bc_id'
    ]
    
    # Check which columns exist in the DataFrame
    available_columns = [col for col in columns_to_plot if col in df_plot.columns]
    
    if not available_columns:
        logger.warning("None of the requested columns are available in the DataFrame")
        return
    
    n_plots = len(available_columns)
    n_cols = 2  # 2 columns of subplots
    n_rows = (n_plots + 1) // 2  # Round up
    
    fig, axes = plt.subplots(n_rows, n_cols, figsize=(15, 4 * n_rows))
    
    # Create title with optional suffix and event count
    main_title = 'Timing and Trigger Variables vs Event Number'
    if title_suffix:
        main_title += f' ({title_suffix})'
    if len(df) > max_events:
        main_title += f' [Showing first {max_events:,} of {len(df):,} events]'
    fig.suptitle(main_title, fontsize=16, fontweight='bold')
    
    # Flatten axes array for easier indexing
    if n_rows == 1:
        axes = axes.reshape(1, -1)
    axes_flat = axes.flatten()
    
    for idx, col in enumerate(available_columns):
        ax = axes_flat[idx]
        
        # Check if column contains awkward arrays
        is_awkward = df_plot[col].dtype == 'object'
        
        if is_awkward:
            # For awkward arrays, we need to handle variable-length data
            # Extract first value from each event (if available)
            try:
                values = []
                events = []
                for i, val in enumerate(df_plot[col]):
                    if hasattr(val, '__len__') and len(val) > 0:
                        # If it's an array-like, take the first value
                        if hasattr(val, 'to_list'):
                            val_list = val.to_list()
                        else:
                            val_list = list(val)
                        
                        if len(val_list) > 0:
                            values.append(val_list[0])
                            events.append(df_plot['event'].iloc[i])
                
                if values:
                    ax.plot(events, values, 'o-', markersize=3, linewidth=1)
                    ax.set_title(f'{col}\n(First value per event)', fontsize=10)
                else:
                    ax.text(0.5, 0.5, 'No data available', 
                           ha='center', va='center', transform=ax.transAxes)
                    ax.set_title(f'{col}\n(No data)', fontsize=10)
            except Exception as e:
                logger.warning("Error plotting %s: %s", col, e)
                ax.text(0.5, 0.5, f'Error: {str(e)[:30]}', 
                       ha='center', va='center', transform=ax.transAxes)
                ax.set_title(f'{col}\n(Error)', fontsize=10)
        else:
            # For regular numeric columns
            ax.plot(df_plot['event'], df_plot[col], 'o-', markersize=3, linewidth=1)
            ax.set_title(col, fontsize=10)
        
        ax.set_xlabel('Event', fontsize=9)
        ax.set_ylabel('Value', fontsize=9)
        ax.grid(True, alpha=0.3)
        ax.tick_params(labelsize=8)
    
    # Hide unused subplots
    for idx in range(len(available_columns), len(axes_flat)):
        axes_flat[idx].set_visible(False)
    
    plt.tight_layout()
    
    if save_path:
        plt.savefig(save_path, dpi=150, bbox_inches='tight')
        logger.info("Figure saved to: %s", save_path)
    
    return fig


if __name__ == "__main__":
    # Example usage: analyze latest ROOT file in Results directory
    results_dir = Path("C:\\Users\\jmarques\\Containers\\RD53\\RD53A_GUI\\Results")

    try:
        # To analyze a specific file, uncomment and modify this line:
        specific_file = "Run000384_Physics_Board000.root"
        
        # Find latest ROOT file
        root_handler = ROOTFileHandler(results_dir)
        
        # Open specific file or latest
        if specific_file:
            logger.info("Opening specific file: %s", specific_file)
            root_file, root_path = root_handler.open_file(filename=specific_file)
        else:
            logger.info("Opening latest ROOT file")
            root_file, root_path = root_handler.open_file()  # Gets latest
        
        logger.info("Using ROOT file: %s", root_path)
        
        # Inspect file structure first
        logger.info("\n" + "=" * 80)
        logger.info("Inspecting ROOT file structure...")
        logger.info("=" * 80)
        ttrees = inspect_root_file(root_file)
        
        if not ttrees:
            logger.error("No TTrees found in file. Cannot proceed.")
            raise ValueError("No TTrees found in ROOT file")
        
        # Try to extract data
        try:
            df, df_hits = extract_data(root_file)
            
            # Print summaries
            print_dataframe_summary(df, "Full DataFrame (df)")
            print_dataframe_summary(df_hits, "Events with Hits (df_hits)")
            
            # Create timing plots for both DataFrames
            logger.info("\nGenerating timing variable plots...")
            output_dir = Path("C:\\Users\\jmarques\\Containers\\RD53\\RD53A_GUI\\Results")
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Plot for df (all events)
            logger.info("Creating plot for df (all events)...")
            fig1 = plot_timing_variables(
                df, 
                save_path=output_dir / "timing_variables_all_events.png",
                title_suffix="All Events"
            )
            
            # Plot for df_hits (events with hits)
            logger.info("Creating plot for df_hits (events with hits)...")
            fig2 = plot_timing_variables(
                df_hits, 
                save_path=output_dir / "timing_variables_with_hits.png",
                title_suffix="Events with Hits"
            )
            
            plt.show()
            
        except Exception as e:
            logger.error("Error extracting data (this may be a PixelAlive file): %s", e)
            logger.info("\nTrying to read raw tree data...")
            
            # Try to read the first tree directly
            tree = root_file[ttrees[0]]
            df = tree.arrays(library="pd")
            
            logger.info("\nSuccessfully read tree as DataFrame")
            logger.info("Available columns:")
            for col in df.columns:
                logger.info("  - %s (%s)", col, df[col].dtype)
            
            print_dataframe_summary(df, "Raw DataFrame from PixelAlive")
        
        # Keep variables in scope for interactive analysis
        logger.info("\n" + "=" * 80)
        logger.info("DataFrames 'df' and 'df_hits' are now available for analysis")
        logger.info("You can now interact with them in the Python interpreter.")
        logger.info("Run with: python -i analisis.py")
        logger.info("=" * 80)
        
    except FileSelectionError as e:
        logger.error("Error: %s", e)
    except Exception as e:
        logger.error("Unexpected error: %s", e, exc_info=True)