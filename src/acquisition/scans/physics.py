from __future__ import annotations
from src.acquisition.maps import PhysicsMap
from src.acquisition.scans.acquisition_scan import AcquisitionScan
from src.chip.register_map import ChipSettings


class PhysicsScan(AcquisitionScan):
    def __init__(self, *args, triggers: int = 0,
                 vthresh_per_chip: dict[tuple[int, int], int] | None = None, **kwargs):
        super().__init__(*args, **kwargs)
        self._triggers          = triggers
        self._vthresh_per_chip  = vthresh_per_chip or {}

    @property
    def acquisition_name(self) -> str:
        return "physics"

    def get_map(self) -> PhysicsMap:
        m = PhysicsMap()
        m.triggers     = self._triggers
        return m

    def _setup_xml(self):
        super()._setup_xml()
        for (h, r), vt in self._vthresh_per_chip.items():
            self.xml.set_chip_setting(h, r, ChipSettings.VTHRESHOLD_LIN, vt)
        self.xml.save()