"""What-if scenario runner."""
import time
import math
from dataclasses import dataclass, field
from typing import List, Optional
from .engine import HaqlEngine
from .reservoir import ReservoirConfig


@dataclass
class ScenarioResult:
    label: str
    p_inj_psi: float = 0.0
    p_prod_psi: float = 0.0
    sg_prod: float = 0.0
    total_loss: float = 0.0
    train_time_s: float = 0.0
    injector_rate: float = 0.0
    producer_rate: float = 0.0
    profile: List[dict] = field(default_factory=list)


class ScenarioRunner:
    def __init__(self, engine: HaqlEngine, config: ReservoirConfig):
        self.engine = engine
        self.config = config
        self._baseline: Optional[ScenarioResult] = None

    def run_baseline(self, epochs: int = 200, interior: int = 500) -> ScenarioResult:
        t0 = time.time()
        result = self.engine.run(
            epochs=epochs, interior=interior,
            eval_time=self.config.eval_time, t_max=self.config.t_max,
            injector_rate=None, producer_rate=None,
        )
        elapsed = time.time() - t0
        self._baseline = ScenarioResult(
            label="Baseline",
            p_inj_psi=result.get("p_inj_psi", 0),
            p_prod_psi=result.get("p_prod_psi", 0),
            sg_prod=result.get("sg_prod", 0),
            total_loss=result.get("total_loss", 0),
            train_time_s=elapsed,
            injector_rate=self.config.wells[0].rate,
            producer_rate=self.config.wells[1].rate,
        )
        return self._baseline

    def run_whatif(self,
                   label: str,
                   epochs: int = 100,
                   interior: int = 300,
                   injector_rate: Optional[float] = None,
                   producer_rate: Optional[float] = None) -> ScenarioResult:
        if not self._baseline:
            raise RuntimeError("Run baseline first")

        t0 = time.time()
        result = self.engine.run(
            epochs=epochs, interior=interior,
            eval_time=self.config.eval_time, t_max=self.config.t_max,
            injector_rate=injector_rate,
            producer_rate=producer_rate,
        )
        elapsed = time.time() - t0

        return ScenarioResult(
            label=label,
            p_inj_psi=result.get("p_inj_psi", 0),
            p_prod_psi=result.get("p_prod_psi", 0),
            sg_prod=result.get("sg_prod", 0),
            total_loss=result.get("total_loss", 0),
            train_time_s=elapsed,
            injector_rate=injector_rate or self.config.wells[0].rate,
            producer_rate=producer_rate or self.config.wells[1].rate,
        )