"""Well Surveillance Co-pilot — FastAPI server with memory backend."""

from pathlib import Path
import os
from typing import Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

from copilot.engine import HaqlEngine
from copilot.reservoir import ReservoirConfig, WellSpec
from copilot.scenario import ScenarioRunner, ScenarioResult
from copilot.memory import MemoryClient

app = FastAPI(title="haql Well Surveillance Co-pilot")

BASE = Path(__file__).parent
jinja_env = Environment(loader=FileSystemLoader(str(BASE / "templates")))

# Serve static assets (if any)
static_dir = BASE / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

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

# ── Memory backend (haql-memory C++ graph store) ──
try:
    mem = MemoryClient()
    mem.project_create("copilot", name="Well Surveillance", domain="oil-and-gas")
    for w in config.wells:
        mem.entity_add("copilot", w.name, kind="well", name=w.name)
        mem.entity_set("copilot", w.name, props={
            "x": str(w.x), "y": str(w.y), "kind": w.kind, "rate": str(w.rate),
        })
    mem.save()
    print("[memory] initialized")
except Exception as e:
    print(f"[memory] init skipped: {e}")
    mem = None


def log_run_to_memory(label: str, result: ScenarioResult):
    if mem is None:
        return
    try:
        safe = label.replace(" ", "_").replace("/", "_")
        mem.entity_add("copilot", f"run_{safe}", kind="scenario", name=label)
        mem.entity_set("copilot", f"run_{safe}", props={
            "p_inj_psi": str(round(result.p_inj_psi, 1)),
            "p_prod_psi": str(round(result.p_prod_psi, 1)),
            "sg_prod": str(round(result.sg_prod, 3)),
            "total_loss": str(round(result.total_loss, 4)),
            "train_time_s": str(round(result.train_time_s, 1)),
            "injector_rate": str(result.injector_rate),
            "producer_rate": str(result.producer_rate),
        })
        for w in config.wells:
            mem.relate("copilot", f"run_{safe}", w.name, kind="uses_well")
        mem.log("copilot", f"run_{safe}", action="simulation",
                props={"label": label})
        mem.save()
    except Exception as e:
        print(f"[memory] log failed: {e}")


def get_memory_entities():
    """Return structured list of entities from memory."""
    if mem is None:
        return []
    try:
        raw = mem.search("copilot", "")
        entities = []
        for line in raw.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split(" ", 2)
            if len(parts) >= 2:
                entities.append({"eid": parts[0], "rest": parts[1] if len(parts) > 1 else ""})
        return entities
    except Exception:
        return []


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    tmpl = jinja_env.get_template("dashboard.html")
    html = tmpl.render({
        "config": config,
        "baseline": baseline,
        "history": history[-10:],
    })
    return HTMLResponse(html)


@app.post("/train")
async def train(epochs: int = Form(200), interior: int = Form(500)):
    global baseline
    try:
        baseline = runner.run_baseline(epochs=epochs, interior=interior)
        log_run_to_memory("Baseline", baseline)
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
    try:
        sr = runner.run_whatif(
            label=label, epochs=epochs, interior=interior,
            injector_rate=injector_rate, producer_rate=producer_rate,
        )
        history.append(sr)
        log_run_to_memory(label, sr)

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


@app.post("/predict")
async def predict(
    x: float = Form(0.5),
    y: float = Form(0.5),
    t: float = Form(100.0),
    epochs: int = Form(50),
    interior: int = Form(200),
):
    try:
        result = engine.predict(x=x, y=y, t=t, epochs=epochs, interior=interior)
        return JSONResponse({
            "status": "ok",
            "pressure_psi": result.get("pressure_psi"),
            "sg_pct": result.get("sg_pct"),
        })
    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


@app.get("/status")
async def status():
    return JSONResponse({
        "baseline_ready": baseline is not None,
        "p_inj_psi": baseline.p_inj_psi if baseline else None,
        "p_prod_psi": baseline.p_prod_psi if baseline else None,
        "wells": [{"name": w.name, "x": w.x, "y": w.y, "kind": w.kind, "rate": w.rate}
                  for w in config.wells],
        "history_count": len(history),
        "memory_ready": mem is not None,
    })


# ── Memory query endpoints ──
@app.get("/memory/search")
async def memory_search(q: str = ""):
    if mem is None:
        return JSONResponse({"error": "Memory not available"}, status_code=503)
    try:
        if q:
            output = mem.search("copilot", q)
        else:
            output = ""
        return JSONResponse({"results": output})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/memory/history")
async def memory_history():
    if mem is None:
        return JSONResponse({"error": "Memory not available"}, status_code=503)
    try:
        output = mem.search("copilot", "run_")
        return JSONResponse({"results": output})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.get("/memory/entities")
async def memory_entities(pid: str = "copilot"):
    if mem is None:
        return JSONResponse({"error": "Memory not available"}, status_code=503)
    try:
        entities = []
        raw = mem.search(pid, "")
        for line in raw.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            eid = line.split()[0] if line.split() else line
            try:
                info = mem.entity_get(pid, eid)
            except Exception:
                info = ""
            entities.append({"eid": eid, "info": info})
        return JSONResponse({"entities": entities})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)