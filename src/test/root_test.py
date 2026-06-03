from src.config.root.root_manager import RootManager



root_files_directory =  "/app/RD53_analysis/Data/ALL/20260211"
root_specific_file = root_files_directory + "/Run000554_Physics_Board000.root"


# Test loading the latest ROOT file
root1 = RootManager(root_files_directory)

# Test loading a specific ROOT fi
root1.load(root_specific_file)

root2= RootManager(root_specific_file)
root2.load()


print(root1.arrays.RD53_frame_event_nhits)

print(root2.arrays.RD53_frame_event_nhits)
