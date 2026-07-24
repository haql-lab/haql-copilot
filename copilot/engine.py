"""Thin wrapper around haql-rs binary."""
import subprocess
import json
import os
import re
from pathlib import Path
from typing import Optional

HAQL_BIN = os.environ.get("HAQL_BIN", str(Path.home() / "Desktop" / "haql" / "build" / "src" / "haql-rs"))

# Strip ANSI escape sequences
_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')


def strip_ansi(text: str) -> str:
    return _ANSI_RE.sub('', text)


class HaqlEngine:
    """Calls haql-rs binary for PINN training and prediction."""

    def __init__(self, bin_path: str = HAQL_BIN):
        self.bin = Path(bin_path)
        if not self.bin.exists():
            raise FileNotFoundError(f"haql-rs not found at {self.bin}")

    def run(self,
            epochs: int = 200,
            interior: int = 500,
            boundary: int = 100,
            initial: int = 50,
            lr: float = 0.001,
            t_max: float = 150.0,
            eval_time: float = 100.0,
            lambda_oil: float = 1.0,
            lambda_gas: float = 1.0,
            lambda_bc: float = 2.0,
            lambda_ic: float = 5.0,
            lambda_well: float = 0.5,
            weight_well: float = 50.0,
            well_pde: int = 50,
            injector_rate: Optional[float] = None,
            producer_rate: Optional[float] = None,
            disable_idw: bool = False,
            output: Optional[str] = None,
            quiet: bool = True) -> dict:
        """Train PINN and return parsed results from stdout."""
        cmd = [
            str(self.bin), "run",
            "--epochs", str(epochs),
            "--interior", str(interior),
            "--boundary", str(boundary),
            "--initial", str(initial),
            "--lr", str(lr),
            "--t-max", str(t_max),
            "--eval-time", str(eval_time),
            "--lambda-oil", str(lambda_oil),
            "--lambda-gas", str(lambda_gas),
            "--lambda-bc", str(lambda_bc),
            "--lambda-ic", str(lambda_ic),
            "--lambda-well", str(lambda_well),
            "--weight-well", str(weight_well),
            "--well-pde", str(well_pde),
        ]
        if quiet:
            cmd.append("--quiet")
        if output:
            cmd.extend(["--output", output])
        if injector_rate is not None:
            cmd.extend(["--injector-rate", str(injector_rate)])
        if producer_rate is not None:
            cmd.extend(["--producer-rate", str(producer_rate)])
        if disable_idw:
            cmd.append("--disable-idw")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if result.returncode != 0:
            raise RuntimeError(f"haql-rs failed:\n{result.stderr}")

        return self._parse_output(result.stdout)

    def predict(self,
                x: float = 0.5,
                y: float = 0.5,
                t: float = 100.0,
                epochs: int = 100,
                interior: int = 500,
                quiet: bool = True) -> dict:
        """Train and predict at a single point."""
        cmd = [
            str(self.bin), "predict",
            "--x", str(x),
            "--y", str(y),
            "--t", str(t),
            "--epochs", str(epochs),
            "--interior", str(interior),
            "--dim",
        ]
        if quiet:
            cmd.append("--quiet")

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if result.returncode != 0:
            raise RuntimeError(f"haql-rs predict failed:\n{result.stderr}")

        return self._parse_predict(result.stdout)

    @staticmethod
    def _parse_output(text: str) -> dict:
        data = {}
        clean = strip_ansi(text)
        # Match box-drawing char │ (U+2502) or regular pipe
        sep = r'[│|]'
        patterns = [
            ("p_inj_psi", r"Injector\s+pressure\s*" + sep + r"\s*(-?\d+)"),
            ("p_prod_psi", r"Producer\s+pressure\s*" + sep + r"\s*(-?\d+)"),
            ("sg_prod", r"Producer\s+Sg\s*" + sep + r"\s*(-?[\d.]+)%"),
        ]
        for key, pat in patterns:
            m = re.search(pat, clean)
            if m:
                data[key] = float(m.group(1))

        # Also try the well-results table format
        if "p_inj_psi" not in data:
            m = re.search(rf"Injector\s*{sep}\s*(-?\d+)\s*{sep}\s*(-?[\d.]+)%", clean)
            if m:
                data["p_inj_psi"] = float(m.group(1))

        if "p_prod_psi" not in data:
            m = re.search(rf"Producer\s*{sep}\s*(-?\d+)\s*{sep}\s*(-?[\d.]+)%", clean)
            if m:
                data["p_prod_psi"] = float(m.group(1))
                if "sg_prod" not in data:
                    data["sg_prod"] = float(m.group(2))

        # Total loss
        m = re.search(r"Total\s+([\d.eE+-]+)", clean)
        if m:
            data["total_loss"] = float(m.group(1))

        return data

    @staticmethod
    def _parse_predict(text: str) -> dict:
        clean = strip_ansi(text)
        data = {}
        m = re.search(r"Pressure\s+([\d.]+)\s+psi", clean)
        if m:
            data["pressure_psi"] = float(m.group(1))
        m = re.search(r"Sg\s+([\d.]+)%", clean)
        if m:
            data["sg_pct"] = float(m.group(1))
        return data