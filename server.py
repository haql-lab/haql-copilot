"""Well Surveillance Co-pilot — FastAPI server."""

from pathlib import Path
import os
from typing import Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from jinja2 import Environment, FileSystemLoader

from copilot.engine import HaqlEngine
from copilot.reservoir import ReservoirConfig, WellSpec
from copilot.scenario import ScenarioRunner, ScenarioResult

app = FastAPI(title="haql Well Surveillance Co-pilot")

BASE = Path(__file__).parent
jinja_env = Environment(loader=FileSystemLoader(str(BASE / "templates")))

config = ReservoirConfig(
    p_init=4800.0, porosity=0.242, permeability=215.0,
    thickness=100.0, t_max=150.0, eval_time=100.0,
    wells=[
        WellSpec(name="Injector-1", x=0.05, y=0.05, kind="injector", rate=10000.0),
        WellSpec(name="Producer-1", x=0.95, y=0.95, kind="producer", rate=20000.0),
    ],
)

engine = HaqlEngine()
runner = ScenarioRunner(engine, config)
baseline: Optional[ScenarioResult] = None
history: list = []


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Main dashboard page."""
    tmpl = jinja_env.get_template("dashboard.html")
    html = tmpl.render({
        "config": config,
        "baseline": baseline,
        "history": history[-5:],
    })
    return HTMLResponse(html)


@app.post("/train")
async def train(epochs: int = Form(200), interior: int = Form(500)):
    """Train the baseline model."""
    global baseline
    try:
        baseline = runner.run_baseline(epochs=epochs, interior=interior)
        return JSONResponse({
            "status": "ok",
            "p_inj_psi": baseline.p_inj_psi,
            "p_prod_psi": baseline.p_prod_psi,
            "sg_prod": baseline.sg_prod,
            "total_loss": baseline.total_loss,
            "inj_rate": baseline.injector_rate,
            "prod_rate": baseline.producer_rate,
            "train_time_s": round(baseline.train_time_s, 1),
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.post("/whatif")
async def whatif(
    label: str = Form(...),
    epochs: int = Form(100),
    interior: int = Form(300),
    injector_rate: Optional[float] = Form(None),
    producer_rate: Optional[float] = Form(None),
):
    """Run a what-if scenario with modified well parameters."""
    try:
        sr = runner.run_whatif(
            label=label, epochs=epochs, interior=interior,
            injector_rate=injector_rate, producer_rate=producer_rate,
        )
        history.append(sr)

        return JSONResponse({
            "status": "ok",
            "label": sr.label,
            "p_inj_psi": sr.p_inj_psi,
            "p_prod_psi": sr.p_prod_psi,
            "sg_prod": sr.sg_prod,
            "inj_rate": sr.injector_rate,
            "prod_rate": sr.producer_rate,
            "train_time_s": round(sr.train_time_s, 1),
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/status")
async def status():
    """Return current model status."""
    return JSONResponse({
        "baseline_ready": baseline is not None,
        "p_inj_psi": baseline.p_inj_psi if baseline else None,
        "p_prod_psi": baseline.p_prod_psi if baseline else None,
        "wells": [{"name": w.name, "x": w.x, "y": w.y, "kind": w.kind, "rate": w.rate}
                  for w in config.wells],
        "history_count": len(history),
    })