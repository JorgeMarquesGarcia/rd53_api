from matplotlib.pyplot import plot

from rd53_api.analysis.analysis_hit import HitAnalysis
from rd53_api.config.root.root_manager import RootManager
import awkward as ak
import json

import logging
logging.basicConfig(level=logging.INFO)

root_files_directory =  "/app/RD53_analysis/Data/ALL/20260508"
root_specific_file = root_files_directory + "/Run000554_Physics_Board000.root"
root_manager = RootManager(root_specific_file)
root_manager.load()
# Test loading the latest ROOT file
hit_analysis = HitAnalysis(root_manager)

print(f"Number of hits extracted: {len(hit_analysis.hits)}")
print(f"\nFirst hit (complete):")
first_hit = ak.to_list(hit_analysis.hits[0])
print(json.dumps(first_hit, indent=2))

#plot_data = ak.to_list(hit_analysis.plot_coord[0]) plot_data ahora es una lista
print(f"\nFirst track coordinates:")
print(hit_analysis.plot_coord[0]) # plot_coord  ahora es una lista, no un awkward array, así que accedemos al primer elemento directamente


print(f"\n\nActive chips: {hit_analysis.active_chips}")

