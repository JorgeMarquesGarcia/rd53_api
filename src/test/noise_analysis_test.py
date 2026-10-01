from src.config.root.root_manager import RootManager
from src.analysis.analysis_noise import NoiseAnalysis


def events_with_chip_tot_above(data, active_chips, chip_key, tot_threshold=1):
    """Devuelve hits por evento para un chip con ToT estrictamente superior al umbral."""
    if chip_key not in active_chips:
        raise ValueError(f"Chip {chip_key} no está entre los chips activos: {active_chips}")

    chip_index = active_chips.index(chip_key)
    selected_events = {}

    for event in data:
        hits_by_chip = [int(value) for value in event.RD53_frame_event_nhits]
        if chip_index >= len(hits_by_chip):
            continue

        hit_start = sum(hits_by_chip[:chip_index])
        hit_end = hit_start + hits_by_chip[chip_index]
        rows = event.RD53_hit_row[hit_start:hit_end]
        cols = event.RD53_hit_col[hit_start:hit_end]
        tots = event.RD53_hit_tot[hit_start:hit_end]

        hits = [
            (int(row), int(col), int(tot))
            for row, col, tot in zip(rows, cols, tots)
            if float(tot) > tot_threshold
        ]

        if hits:
            selected_events[int(event.event)] = hits

    return selected_events


def print_chip_events(chip_key, events):
    """Imprime los IDs de evento y sus hits seleccionados."""
    print(f"\nEventos del chip {chip_key} con ToT > 1: {len(events)}")
    for event_id, hits in events.items():
        print(f"Evento {event_id} - hits (row, col, ToT): {hits}")


root_files_directory = r"C:\Users\jmarques\Containers\RD53\RD53A_GUI\Results"
root_specific_file = root_files_directory + r"\Run000197_Physics_Board000.root"

# Abrir el ROOT concreto.
root1 = RootManager(root_files_directory)
root1.load(root_specific_file)

# Extraer eventos y ruido.
NS = NoiseAnalysis(root1)

noise_events = NS.noisy_events
noisy_pixels = NS.noisy_pixels

print(f"Eventos ruidosos: {len(noise_events)}")
print(f"Pixeles ruidosos por chip: {noisy_pixels}")
print(f"Estadisticas de ruido: {NS.stats}")

print(f"Datos crudos: {len(NS.raw_data)}")
for i in range(min(5, len(NS.raw_data))):
    print(f"Evento crudo {i}: {NS.raw_data.event[i]}")

for i in range(min(5, len(NS.clean_data))):
    print(f"Evento limpio {i}: {NS.clean_data.event[i]}")
print(f"Clean events: {len(NS.clean_data)}")

for i in range(min(5, len(noise_events))):
    print(f"Evento ruidoso {i}: {noise_events[i].event}")

chip0_events = events_with_chip_tot_above(
    NS.clean_data, NS.active_chips, (0, 0), tot_threshold=1
)
chip20_events = events_with_chip_tot_above(
    NS.clean_data, NS.active_chips, (2, 0), tot_threshold=1
)

print_chip_events((0, 0), chip0_events)
print_chip_events((2, 0), chip20_events)

common_event_ids = sorted(set(chip0_events) & set(chip20_events))
print(f"\nEventos comunes en (0, 0) y (2, 0), con ToT > 1: {len(common_event_ids)}")
print(common_event_ids)



