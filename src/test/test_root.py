import ROOT
ROOT.gROOT.SetBatch(True)

#f= ROOT.TFile("/app/RD53_analysis/Data/CALIBRATION/threqu/Run000010_ThrEqualization.root", "READ")
#canvas = f.Get("Detector/Board_0/OpticalGroup_0/Hybrid_0/Chip_0/D_B(0)_O(0)_H(0)_SCurves_Chip(0)")
#f.ls()
 

f = ROOT.TFile("Data/CALIBRATION/threqu/Run000010_ThrEqualization.root", "READ")
d = f.Get("Detector/Board_0/OpticalGroup_0/Hybrid_2/Chip_0")


for key in d.GetListOfKeys():
    obj = key.ReadObj()
    if not isinstance(obj, ROOT.TCanvas):
        continue
    print(f"\n=== {key.GetName()} ===")
    for p in obj.GetListOfPrimitives():
        cn = p.ClassName()
        if cn.startswith("TH") or cn.startswith("TGraph"):
            nbins_x = p.GetNbinsX() if hasattr(p, "GetNbinsX") else "N/A"
            print(f"  {cn} | X: '{p.GetXaxis().GetTitle()}' ({nbins_x}) | Y: '{p.GetYaxis().GetTitle()}'")

f.Close()

# Nivel 1
# det = f.Get("Detector")
# print(type(det))
# det.ls()

#Nivel 2 
# board = det.Get("Board_0")
# board.ls()

#Nivel 3
# optical_group = board.Get("OpticalGroup_0")
# optical_group.ls()

#Nivel 4
# hybrid = optical_group.Get("Hybrid_2")
# hybrid.ls()








#for p in canvas.GetListOfPrimitives():
#    if p.ClassName().startswith("TH2"):
#        print("X:", p.GetXaxis().GetTitle(), "bins:", p.GetNbinsX())
#        print("Y:", p.GetYaxis().GetTitle(), "bins:", p.GetNbinsY())
#        print("Z:", p.GetZaxis().GetTitle())
#        print("Entries:", p.GetEntries())

# ROOT.gROOT.SetBatch(True)
# f = ROOT.TFile("/app/RD53_analysis/Data/CALIBRATION/scurve/Run000025_SCurve.root", "READ")
# canvas = f.Get("Detector/Board_0/OpticalGroup_0/Hybrid_0/Chip_0/D_B(0)_O(0)_H(0)_SCurves_Chip(0)")
# for p in canvas.GetListOfPrimitives():
#     print(p.ClassName(), p.GetName())



