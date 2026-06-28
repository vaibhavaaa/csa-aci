# CSA-ACI — Cognitive Constraint Engine (CCE)

**A multi-signal, explainable, stability-bounded governor for cloud autoscaling.**

Reactive autoscalers (threshold, hysteresis, EMA, PID, even Kubernetes HPA) tend to
*thrash* — flipping scale-up/scale-down decisions on noisy telemetry and burning
capacity churn. CSA-ACI sits one layer above the controllers as an **arbitration
governor**: it reconciles competing CPU and latency signals through an **evidence
gate** and a **minimum dwell time**, so a scaling decision only fires once the
evidence persists — eliminating noise-induced capacity thrash while keeping every
decision auditable and bounded by checkable operating guarantees.

> **What's actually novel here.** The per-signal agents are deliberately *simple
> rules* — the contribution is **not** "two AI agents." The contribution is the
> **arbitration governor** (evidence gate + dwell + magnitude bound) and its formal
> operating guarantees. See [Honest scope & limitations](#honest-scope--limitations)
> before reading the results — the win is real but bounded.

[![CI](https://github.com/vaibhavaaa/csa-aci/actions/workflows/ci.yml/badge.svg)](https://github.com/vaibhavaaa/csa-aci/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-blue)](https://www.python.org/)
[![Backend: FastAPI](https://img.shields.io/badge/backend-FastAPI-009688)](https://fastapi.tiangolo.com/)
[![Frontend: React + Vite](https://img.shields.io/badge/frontend-React%20%2B%20Vite-61dafb)](https://vitejs.dev/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green)](#license)

---

## How it works — the CCE pipeline

Each step in [`csa_aci_fixed/src/csa_aci/cce.py`](csa_aci_fixed/src/csa_aci/cce.py)
takes the raw per-signal intents and gates them down to one safe, explainable action:

1. **Intent Arbitration** — reconcile the CPU agent and the latency agent into a
   single proposed intent (`SCALE_UP` / `HOLD` / `SCALE_DOWN`), flagging conflicts.
2. **Evidence Persistence Gate** — a proposed change must hold for a window of
   consistent readings before it's accepted; transient noise is rejected.
   *(`HOLD` always bypasses the gate.)*
3. **Minimum Dwell Constraint** — after acting, the governor must wait a dwell
   period before reversing, damping rapid back-and-forth.
   *(An emergency override at ≥300 ms latency bypasses both the gate and dwell.)*
4. **Magnitude-Bounded Execution** — the executed action is clamped so a single
   decision can't over-correct.

Every decision is logged with its `final_intent`, `reason`, a `trust_score`
(internal proxy), and a conflict flag — so the *why* is always inspectable.

### Operating guarantees
The governor ships with **checkable** guarantees (e.g. emergency override always
fires, dwell is always respected, `HOLD` is never blocked), audited automatically by
`run_guarantee_audit()` in
[`supervisor_engine.py`](backend/app/services/supervisor_engine.py) — each check
carries the `lemma` id it validates.

---

## Results (honest and bounded)

All baselines run on the **identical** telemetry sequence as CCE (same seed, same
steps, same thresholds) for a fair comparison.

| Comparison | Outcome |
|---|---|
| **vs single-signal baselines** (Threshold, Hysteresis, EMA, PID) | CCE **wins on capability** — it's the only controller that handles every conflict regime (4/4), because single-signal controllers are blind to whichever signal they don't read. |
| **vs a *fair* multi-signal baseline** (Multi-Metric HPA) | **Capability ties.** CCE wins on **stability** — near-zero intent thrash — at a **bounded responsiveness cost** (it reacts a little slower because it waits for evidence). |

The headline metric is **CSI** (Constraint Stability Index), a composite of trust,
intent-switching, and conflict. Secondary metrics: precision / recall / **F1**,
average response lag, intent-switch count, conflict count, intervention distance.

### Honest scope & limitations
This is a **research prototype**, and the claim is deliberately modest:

- The result is **stability at a bounded responsiveness cost** — *not* a clean sweep.
  Against a fair multi-signal baseline, CCE trades a little reactivity for a lot less
  thrash. If your workload has no telemetry noise, there's nothing for CCE to suppress.
- Evaluation is mostly **simulation + one genuinely-measured latency trace**. Only
  results sourced from real traces (`source == "real"`) are treated as paper-valid;
  the loader explicitly labels any synthetic fallback as **not** paper-valid.
- Single author; the `trust_score` normalization is an empirically-measured constant,
  not a derived one (a thesis-deferred derivation).

These limitations are stated plainly and up front — that honesty is the point, not a
footnote.

---

## Architecture

```
            ┌──────────────┐     WebSocket + REST      ┌─────────────────────┐
  Browser ──│  React + Vite│◄─────────(nginx)─────────►│  FastAPI backend     │
            │  dashboard   │                           │  app/services/       │
            └──────────────┘                           │  supervisor_engine.py│
                                                        └──────────┬──────────┘
                                                                   │ imports
                                                        ┌──────────▼──────────┐
                                                        │  csa_aci package     │
                                                        │  Supervisor + CCE    │
                                                        └─────────────────────┘
        PostgreSQL (one row per CCE decision)   ·   Redis (WebSocket pub/sub)
```

**Stack:** FastAPI · PostgreSQL · Redis · React + Vite · Recharts · Docker · Kubernetes
Core engine is the standalone Python package **`csa_aci`** (source in
[`csa_aci_fixed/src/csa_aci/`](csa_aci_fixed/src/csa_aci/)).

---

## Quickstart

### Run the full stack with Docker (recommended)

```bash
# 1. Provide config (placeholders are fine for local dev)
cp .env.example backend/.env

# 2. Bring up backend + frontend + postgres + redis + nginx
docker compose -f infra/docker-compose.yml up --build
```

Then open:
- **Dashboard** → http://localhost  (served through nginx)
- **Interactive API docs** → http://localhost:8000/docs  (FastAPI / Swagger; endpoints
  are JWT-protected — authenticate there)

### Local dev (without Docker)

```bash
# Backend  (Python 3.9+).  Tests fall back to an in-memory SQLite, no DB needed.
cd backend
pip install -r requirements.txt
pip install -e ../csa_aci_fixed         # installs the csa_aci package
uvicorn app.main:app --reload           # http://localhost:8000

# Frontend
cd frontend
npm install
npm run dev                             # http://localhost:5173
```

### Run the tests

```bash
cd backend
pytest                                  # CCE invariants + research harness + app import
```

---

## Reproducing the experiments

Every experiment uses an explicit random seed (reported in the API response) and is
exposed as an endpoint under `/tasks`:

| Endpoint | What it runs | Paper section |
|---|---|---|
| `POST /tasks/ablation` | Single-signal ablation study | 5.1 |
| `POST /tasks/compare` · `POST /tasks/trace-replay` | Controller comparison on real traces | 5.2 |
| `POST /tasks/conflict-experiment` | Multi-signal conflict + stability verdict | 5.2b |
| `POST /tasks/conflict-stress` · `POST /tasks/stress-test` | Statistical validation (30 seeds, paired Wilcoxon) | 5.3 |
| `POST /tasks/sensitivity` | Hyperparameter sensitivity sweep | 5.4 |
| `POST /tasks/multi-sim` | Multi-scenario generalization | 5.5 |
| `POST /tasks/guarantee-audit` | Formal guarantee lemmas | §4 |
| `GET  /tasks/datasets` | Available traces + `source` provenance | — |

All experiment logic lives in
[`backend/app/services/supervisor_engine.py`](backend/app/services/supervisor_engine.py).

### Real traces
Three datasets load as `source == "real"`: **Google Cluster**, **Wikipedia
projectviews**, and a **measured** wall-clock-latency trace. Raw/processed data is
*not* checked in (large + reproducible) — loaders in [`data/loaders/`](data/loaders/)
regenerate it, and the loader labels any missing data `synthetic_fallback` so results
are never silently mislabelled.

---

## Repository layout

```
csa_aci_fixed/   Core CCE algorithm + Supervisor (the csa_aci Python package)
backend/         FastAPI service, experiment harness, tests
frontend/        React + Vite dashboard (multi-page, glass UI)
infra/           docker-compose + Kubernetes manifests (incl. HPA baseline)
data/            Real-trace loaders (raw/processed data fetched, not tracked)
```

---

## Research paper
This work is written up as an IEEE-format paper — **currently unpublished and kept
private pending submission**, so it is intentionally not in this repository. The code →
paper-section mapping in the table above mirrors its structure; the draft is available
on request.

## License
MIT — see the `license` field in
[`csa_aci_fixed/pyproject.toml`](csa_aci_fixed/pyproject.toml). *(A standalone `LICENSE`
file can be added on request.)*
