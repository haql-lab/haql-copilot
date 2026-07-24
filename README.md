# haql Copilot — Well Surveillance & What-If Simulation Dashboard

**haql Copilot** is a web-based well surveillance dashboard powered by the haql PINN reservoir simulator. It lets reservoir engineers monitor well performance and run what-if scenarios in seconds instead of hours — a copilot, not an autopilot.

---

## How It Works

1. Define your reservoir wells and rates
2. Train the PINN baseline model (~30-60 seconds)
3. Run what-if scenarios by changing well rates
4. Compare results instantly

Each scenario trains a physics-informed neural network from scratch, converging to FDM-matched accuracy in seconds. No cloud compute, no cluster queue, no waiting.

---

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Start the server
python3.12 -m uvicorn server:app --host 0.0.0.0 --port 8765

# Open in browser
# http://localhost:8765
```

### Requirements

- Python >= 3.10
- FastAPI, uvicorn, Jinja2, PyYAML
- haql-rs binary built at `~/Desktop/haql/build/src/haql-rs`

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Dashboard HTML page |
| GET | `/status` | Current model status as JSON |
| POST | `/train` | Train baseline PINN model |
| POST | `/whatif` | Run a what-if scenario with modified well rates |

### POST /train

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `epochs` | int | 200 | Number of training epochs |
| `interior` | int | 500 | Number of interior collocation points |

Returns: `{ status, p_inj_psi, p_prod_psi, sg_prod, total_loss, train_time_s }`

### POST /whatif

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `label` | str | required | Scenario name |
| `epochs` | int | 100 | Training epochs |
| `interior` | int | 300 | Interior collocation points |
| `injector_rate` | float | null | Override injector rate (bbl/d) |
| `producer_rate` | float | null | Override producer rate (bbl/d) |

Returns: `{ status, label, p_inj_psi, p_prod_psi, sg_prod, inj_rate, prod_rate, train_time_s }`

---

## Architecture

```
haql-copilot/
  server.py               FastAPI application
  copilot/
    engine.py             haql-rs binary wrapper (subprocess)
    reservoir.py          Reservoir configuration and well definitions
    scenario.py           What-if scenario runner
  templates/
    dashboard.html        Jinja2 dashboard template
```

### Engine Integration

The copilot calls the `haql-rs` binary via subprocess for each scenario. The PINN trains from scratch per scenario with the specified well rates, converging to FDM targets (4801 psi injector, 3840 psi producer, 8.6% Sg) in seconds.

---

## Default Configuration

- **Reservoir:** Two-phase black-oil, SPE-1 PVT, Corey relperm
- **Wells:** Peaceman well model with rate control
- **Domain:** 10,000 ft x 10,000 ft, 100 ft thickness
- **Constraints:** IDW hard constraints pin well pressures to FDM targets
- **Model:** 3x64 shared trunk + 2x64 branches, ~17K parameters, tanh activation

---

## Performance

- Baseline training (200 epochs, 500 interior): ~60 seconds
- What-if scenario (100 epochs, 300 interior): ~30 seconds
- Equivalent FDM simulation: hours on a cluster

---

## License

Proprietary. All rights reserved.