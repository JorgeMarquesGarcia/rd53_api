import logging
logging.basicConfig(level=logging.DEBUG)

from rd53_api.analysis.analysis_hit import HitAnalysis
from rd53_api.config.root.root_manager import RootManager
from rd53_api.plotter.plotter_trajectory import CoincidencePlotter
from rd53_api.plotter.trajectory_interactive import InteractiveCoincidencePlotter, InteractiveTrajectoryPlotter

from pathlib import Path



root_files_directory =  "/app/RD53_analysis/Data/ALL/20260508"
root_specific_file = root_files_directory + "/Run000554_Physics_Board000.root"
root_manager = RootManager(root_specific_file)
root_manager.load()
# Test loading the latest ROOT file
hit_analysis = HitAnalysis(root_manager)

# plotter = Plotter()
# plotter.add_hits_from_awkward(hit_analysis.hits, progressive=False)
# #plotter.save(Path("/app/RD53_analysis/heatmap.png"))

harryplotter = CoincidencePlotter(hit_analysis.plot_coord, hit_analysis.active_chips)
harryplotter.plot_single_event(0)
harryplotter.plot_multiple_events(max_events=28)
harryplotter.save()


ronweasley = InteractiveCoincidencePlotter(hit_analysis.plot_coord, hit_analysis.active_chips)
ronweasley.plot_single_event(0)
ronweasley.plot_multiple_events(max_events=20)
ronweasley.save()


