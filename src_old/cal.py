"""
Calibration module for RD53A chip analysis.

This module contains all the calibration procedures including:
- Statistics calculation
- Noise scanning
- Latency scanning
- Mask generation from noise analysis
"""

from __future__ import annotations
import logging
from pathlib import Path
from runsummary import extract_data, calculate_statistics, add_masked_pixels_info
from pixel import PixelAnalyzer
from ManipulateITchipMask import readCFGfile
from files import XMLFileHandler

logger = logging.getLogger("CAL")


def run_calibration(
    root_file_object,
    root_filename: str,
    txt_file_path: str,
    vthreshold_lin: float,
    xml_file_path: Path,
    perform_latency_scan: bool = False
) -> None:
    """
    Execute full calibration procedure on the chip data.
    
    This includes:
    1. Extract data from ROOT file
    2. Calculate statistics
    3. Analyze pixels and perform noise scan
    4. Perform latency scan (optional, only if perform_latency_scan=True)
       - Calculates latency and sigma
       - Updates XML with: LATENCY_CONFIG = LATENCY_CONFIG + latency - sigma
    5. Generate and save mask from noise analysis
    
    Args:
        root_file_object: Opened ROOT file object (from uproot)
        root_filename: Path to the ROOT file as string
        txt_file_path: Path to the TXT configuration file
        vthreshold_lin: Vthreshold_LIN value from XML
        xml_file_path: Path to the XML configuration file
        perform_latency_scan: If True, perform latency scan (default: False)
    """
    logger.info("=" * 60)
    logger.info("Starting calibration procedure")
    logger.info("=" * 60)
    
    # Step 1: Extract data from ROOT file
    logger.info("[1/5] Extracting data from ROOT file...")
    df, df1 = extract_data(root_file_object)
    logger.info("✓ Data extraction complete")
    
    # Step 2: Calculate statistics
    logger.info("[2/5] Calculating statistics...")
    summary = calculate_statistics(
        root_file=root_filename,
        output_file=None,
        df=df,
        df1=df1,
        Vthreshold_LIN=vthreshold_lin
    )
    logger.info("✓ Statistics calculation complete")
    
    # Step 3: Analyze pixels and perform noise scan
    logger.info("[3/5] Performing noise scan...")
    pixel_analyzer = PixelAnalyzer(df1)
    pixel_data = pixel_analyzer.analyze_pixels()
    noisy_pixels = pixel_analyzer.noise_scan(save_summary_path=None)
    logger.info("✓ Noise scan complete")
    
    # Step 4: Perform latency scan (optional)
    if perform_latency_scan:
        logger.info("[4/5] Performing latency scan...")       
        xmlhandler = XMLFileHandler(xml_file_path.parent)
        # Read current LATENCY_CONFIG and nTRIGxEvent from XML
        current_latency_config, current_ntrig = xmlhandler.extract_latency_config(xml_file_path)
        logger.info("Actual LATENCY_CONFIG from XML: %s", current_latency_config)
        logger.info("Actual nTRIGxEvent from XML: %s", current_ntrig)
        latency_results = pixel_analyzer.latency_scan(df_original=df, groupSize=current_ntrig)

        if latency_results:
            latency = latency_results['latency']
            sigma = latency_results['sigma']
            logger.info("Latency scan results: latency = %.2f, sigma = %.2f", latency, sigma)

            if current_ntrig is not None:
                # Ensure nTRIGxEvent is at least 3 to avoid data loss
                sigma_int = int(sigma)
                if sigma_int < 3:
                    logger.warning("Sigma value (%.2f -> %d) is less than 3, setting nTRIGxEvent to 3", 
                                  sigma, sigma_int)
                    new_ntrig_event = 3
                else:
                    new_ntrig_event = sigma_int
                
                # Calculate new LATENCY_CONFIG
                # Formula: LATENCY_CONFIG = LATENCY_CONFIG + latency
                new_latency_config = int(current_latency_config - latency)# + new_ntrig_event)
                
                logger.info("Updating latency configuration:")
                logger.info("  Old LATENCY_CONFIG = %d", current_latency_config)
                logger.info("  Calculated: %d - %.2f = %d",
                           current_latency_config, latency, new_latency_config)
                logger.info("  New LATENCY_CONFIG = %d", new_latency_config)
                logger.info("  New nTRIGxEvent = %d (minimum: 3)", new_ntrig_event)
                
                # Update XML file
                if xmlhandler.update_latency_config(xml_file_path, new_latency_config, new_ntrig_event):
                    logger.info("✓ XML configuration updated successfully")
                else:
                    logger.error("✗ Failed to update XML configuration")
            else:
                logger.warning("Could not read current LATENCY_CONFIG from XML, skipping update")
        
        logger.info("✓ Latency scan complete")
    else:
        logger.info("[4/5] Skipping latency scan (use -L/--latency flag to enable)")
    
    # Step 5: Generate and save mask from noise
    logger.info("[5/5] Generating and saving mask...")
    logger.info("Reading original mask from: %s", txt_file_path)
    original_mask = readCFGfile(txt_file_path)
    mask = pixel_analyzer.make_mask_from_noise(orgMask=original_mask)
    pixel_analyzer.save_mask(mask)
    logger.info("✓ Mask generation complete")
    
    # Extract column range from XML and count masked pixels
    logger.info("Analyzing masked pixels in active region...")
    if not hasattr(locals(), 'xmlhandler') or xmlhandler is None:
        xmlhandler = XMLFileHandler(xml_file_path.parent)
    
    col_start, col_stop = xmlhandler.extract_column_range(xml_file_path)
    
    if col_start is not None and col_stop is not None:
        masked_count, total_pixels, percentage = pixel_analyzer.count_masked_pixels(
            mask, col_start, col_stop
        )
        
        # Update statistics summary with masked pixels info
        summary = add_masked_pixels_info(summary, masked_count, total_pixels, percentage)
        
        # Append masked pixels info to statistics file
        output_file = Path(__file__).resolve().parent / "statistics_summary.txt"
        try:
            with open(output_file, 'a', encoding='utf-8') as f:
                f.write("=== Masked Pixels Analysis ===\n\n")
                f.write(f"Active column range: COL {col_start} to COL {col_stop}\n")
                f.write(f"Masked pixels (absolute): {masked_count}\n")
                f.write(f"Total pixels in active region: {total_pixels}\n")
                f.write(f"Masked pixels (%): {percentage:.2f}\n")
                f.write("\n")
            logger.info("Masked pixels statistics saved to %s", output_file)
        except Exception as e:
            logger.error("Error saving masked pixels statistics: %s", e)
        
        # Display masked pixels info in terminal
        logger.info("=" * 60)
        logger.info("MASKED PIXELS STATISTICS:")
        logger.info("  Active column range: COL %d to COL %d", col_start, col_stop)
        logger.info("  Total pixels in active region: %d", total_pixels)
        logger.info("  Masked pixels: %d (%.2f%%)", masked_count, percentage)
        
        # Warning if more than 10% masked
        if percentage > 10.0:
            logger.warning("⚠ WARNING: More than 10%% of pixels are masked (%.2f%%)!", percentage)
            logger.warning("⚠ This may indicate a problem with the chip or configuration.")
        else:
            logger.info("✓ Masked pixel percentage is within acceptable range")
        logger.info("=" * 60)
    else:
        logger.warning("Could not extract column range from XML, skipping masked pixel analysis")
    
    logger.info("=" * 60)
    logger.info("Calibration procedure finished successfully")
    logger.info("=" * 60)
