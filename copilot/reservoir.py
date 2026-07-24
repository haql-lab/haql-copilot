"""Reservoir configuration and well management."""
from dataclasses import dataclass, field
from typing import List, Optional
import yaml


@dataclass
class WellSpec:
    name: str
    x: float
    y: float
    kind: str  # "injector" or "producer"
    rate: float = 0.0
    bhp: Optional[float] = None


@dataclass
class ReservoirConfig:
    p_init: float = 4800.0
    porosity: float = 0.242
    permeability: float = 215.0
    thickness: float = 100.0
    t_max: float = 150.0
    eval_time: float = 100.0
    wells: List[WellSpec] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: str) -> "ReservoirConfig":
        with open(path) as f:
            raw = yaml.safe_load(f)
        wells = []
        for w in raw.get("wells", []):
            wells.append(WellSpec(**w))
        return cls(
            p_init=raw.get("p_init", 4800.0),
            porosity=raw.get("porosity", 0.242),
            permeability=raw.get("permeability", 215.0),
            thickness=raw.get("thickness", 100.0),
            t_max=raw.get("t_max", 150.0),
            eval_time=raw.get("eval_time", 100.0),
            wells=wells,
        )

    def to_yaml(self, path: str):
        raw = {
            "p_init": self.p_init,
            "porosity": self.porosity,
            "permeability": self.permeability,
            "thickness": self.thickness,
            "t_max": self.t_max,
            "eval_time": self.eval_time,
            "wells": [{"name": w.name, "x": w.x, "y": w.y,
                        "kind": w.kind, "rate": w.rate} for w in self.wells],
        }
        with open(path, "w") as f:
            yaml.dump(raw, f, default_flow_style=False)