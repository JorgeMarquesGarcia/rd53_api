from matplotlib.pyplot import plot

from src.analysis.analysis_hit import HitAnalysis
from src.config.root.root_manager import RootManager
import awkward as ak
import json

import logging
logging.basicConfig(level=logging.INFO)

root_files_directory = r"C:\Users\jmarques\Containers\RD53\RD53A_GUI\Results"
root_specific_file = root_files_directory + r"\Run000197_Physics_Board000.root"
root_manager = RootManager(root_files_directory)
root_manager.load(root_specific_file)
# Test loading the latest ROOT file
hit_analysis = HitAnalysis(root_manager)

print(f"Number of hits extracted: {len(hit_analysis.hits)}")
if len(hit_analysis.hits) > 0:
	print(f"\nFirst hit (complete):")
	first_hit = ak.to_list(hit_analysis.hits[0])
	print(json.dumps(first_hit, indent=2))

	print(f"\nFirst track coordinates:")
	print(hit_analysis.plot_coord[0])
else:
	print("\nNo hits passed the trigger, coincidence and ToT filters.")


print(f"\n\nActive chips: {hit_analysis.active_chips}")

