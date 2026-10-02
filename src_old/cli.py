# cli.py
import argparse

def build_parser():
    """
    Build and configure the argument parser for the RD53A data analyzer.
    
    Returns:
        argparse.ArgumentParser: Configured argument parser
    """
    parser = argparse.ArgumentParser(
        description="RD53A Data Analyzer - Analysis of ROOT files and chip masks",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  CALIBRATION MODE:
    python main.py
    python main.py -r rootfile.root -t txtfile.txt
    python main.py --root Run000145_Physics_Board000.root --txt CMSIT_RD53A.txt
    python main.py -r rootfile.root -t txtfile.txt -x config.xml
    python main.py --convert-raw Run000145.raw
    python main.py --convert-raw Run000145.raw --txt CMSIT_RD53A.txt --latency
    python main.py --convert-raw Run000145.raw --conversion-timeout 600
  
  REMOTE DAQ MODE:
    python main.py --remote --max-iterations 10
    python main.py --remote --max-iterations 5 --verbose
        """
    )
    
    parser.add_argument(
        '-r', '--root',
        type=str,
        help='ROOT file name (e.g., Run000145_Physics_Board000.root). If not provided, uses latest file.',
        required=False
    )
    
    parser.add_argument(
        '-t', '--txt',
        type=str,
        help='Config TXT file name (e.g., CMSIT_RD53A.txt). If not provided, uses latest file.',
        required=False
    )
    
    parser.add_argument(
        '-x', '--xml',
        type=str,
        help='Config XML file name (e.g., CMSIT_RD53A.xml) to extract Vthreshold_LIN. If not provided, uses latest file.',
        required=False
    )
    
    parser.add_argument(
        '-L', '--latency',
        action='store_true',
        help='Perform latency scan calibration (only needed on first run or when recalibrating)'
    )
    
    parser.add_argument(
        '--convert-raw',
        type=str,
        metavar='RAW_FILE',
        help='Convert a .raw file to .root format before analysis (e.g., Run000145.raw)',
        required=False
    )
    
    parser.add_argument(
        '--conversion-timeout',
        type=float,
        default=300.0,
        metavar='SECONDS',
        help='Timeout for RAW conversion in seconds (default: 300 = 5 minutes)',
        required=False
    )
    
    parser.add_argument(
        '--stats',
        type=str,
        help='File path to save statistics summary',
        required=False
    )
    
    parser.add_argument(
        '--mask',
        type=str,
        help='Original mask file path',
        required=False
    )
    
    parser.add_argument(
        '--overwrite',
        action='store_true',
        help='Overwrite the original mask file'
    )
    
    # ========================================================================
    # Remote DAQ arguments
    # ========================================================================
    parser.add_argument(
        '--remote',
        action='store_true',
        help='Enable remote DAQ mode (LAB only)'
    )
    
    parser.add_argument(
        '--max-iterations',
        type=int,
        default=None,
        metavar='N',
        help='Number of DAQ iterations to run in remote mode (default: None = infinite, max: 99)'
    )
    
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Show detailed output (for remote DAQ mode)'
    )
    
    return parser


def parse_arguments():
    """
    Parse command line arguments.
    
    Returns:
        argparse.Namespace: Parsed arguments
    """
    parser = build_parser()
    return parser.parse_args()

