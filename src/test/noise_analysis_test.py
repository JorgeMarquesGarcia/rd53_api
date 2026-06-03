import sys
from pathlib import Path
from src.config.root.root_manager import RootManager
from src.analysis.analysis_noise import NoiseAnalysis
# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

root_files_directory =  "/app/RD53_analysis/Data/ALL/20260327"
root_specific_file = root_files_directory + "/Run000695_Physics_Board000.root"

#open specific file 
root1 = RootManager(root_files_directory)
root1.load(root_specific_file)

#Extraemos eventos y ruido
NS = NoiseAnalysis(root1)

noise_events = NS.noisy_events
noisy_pixels = NS.noisy_pixels
hits = NS.hits

print(f"Eventos ruidosos: {len(noise_events)}")

print(f"Datos crudos: {len(NS.raw_data)}")
print(f"Primer evento crudo: {NS.raw_data.event[0]}")

for i in range(min(5, len(NS.raw_data))):
    print(f"Evento crudo {i}: {NS.raw_data.event[i]}")

for i in range(min(5, len(NS.clean_data))):
    print(f"Evento limpio {i}: {NS.clean_data.event[i]}")
print(f"Clean events: {len(NS.clean_data)}")
print(18%5)
print(f"Primer evento limpio: {NS.clean_data.event[0]}")

print(f"Eventos con trigger: {len(NS.trigger_data)}")

print(f"Píxeles ruidosos: {len(noisy_pixels)}")
print(f"Eventos con hits: {len(hits)}")





#for noise_event in noise_events:
    #print(noise_event.event)



