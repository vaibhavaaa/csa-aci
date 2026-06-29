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
[![License: BSD-3-Clause](https://img.shields.io/badge/license-BSD--3--Clause-green)](#license)

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

Every decision is logged with its `final_intent`, `reason` (the final gate
outcome), `conflict_reason` (how a conflict was arbitrated, kept separate so it's
never overwritten), a `trust_score` (internal proxy), and a conflict flag — so the
*why* is always inspectable.

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

**Stack:** FastAPI · PostgreSQL · Redis · React + Vite · Recharts · Docker · Kubernetes · Prometheus · Grafana · GitHub Actions
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

### Deploy to Kubernetes (Minikube)

```bash
# Builds images into Minikube, applies every manifest + the monitoring stack,
# waits for rollout, runs the DB migration.  Use --down to tear it all back down.
bash infra/deployment/deploy.sh          # Windows: infra/deployment/deploy.ps1
```

Then open the **dashboard** at `http://$(minikube ip):30080` and **Grafana** at
`http://$(minikube ip):30030`. The same manifests are exercised on every push by the
CI deploy smoke test (see [Deployment, CI/CD & observability](#deployment-cicd--observability)).

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
pytest                                  # CCE invariants · research harness · app import · observability
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

---

## Deployment, CI/CD & observability

**CI/CD** ([`.github/workflows/`](.github/workflows/)) runs on every push to `main`:

- **Tests** — backend `pytest` on Python 3.11 + 3.12; frontend ESLint + Vite build.
- **Images** — builds the backend and frontend images and publishes them to the GitHub
  Container Registry (`ghcr.io/vaibhavaaa/csa-aci-{backend,frontend}`).
- **Deploy smoke test** — stands up an ephemeral **kind** Kubernetes cluster, deploys
  the *full* manifest set, and verifies it end-to-end: every workload rolls out Ready,
  the backend serves `/healthz` + `/metrics`, and Prometheus is actually scraping the
  backend. So the manifests are proven to deploy on every push — no external cluster
  needed.
- **CD** ([`cd.yml`](.github/workflows/cd.yml)) — a manual, gated deploy to a *real*
  cluster via a `KUBECONFIG` secret. It cleanly no-ops until a cluster is wired up, so
  it never reports a fake "deployed".

**Observability** ([`infra/deployment/monitoring/`](infra/deployment/monitoring/)) — the
backend exposes Prometheus metrics at `/metrics`; an in-cluster Prometheus (annotation-
based pod discovery, no Operator/CRDs — runs on plain Minikube) scrapes it, and Grafana
ships a provisioned **"CSA-ACI Backend"** dashboard (request rate, p95 latency, per-handler
rate) on NodePort `30030`.

**Config & secrets** — 12-factor via env (`.env.example`); k8s Secrets templated as
`secrets.example.yaml` (real values never committed). `SECRET_KEY` is required when
`ENV=production` (the app refuses to start without it).

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
backend/         FastAPI service (incl. /metrics, /healthz), experiment harness, tests
frontend/        React + Vite dashboard (multi-page, glass UI)
infra/           docker-compose + Kubernetes manifests (HPA + Prometheus/Grafana) + deploy scripts
data/            Real-trace loaders (raw/processed data fetched, not tracked)
.github/         CI/CD workflows (tests · GHCR images · kind deploy smoke test · gated CD)
```

---

## Hardening & code review (ECC-assisted)

The CCE engine and the dashboard's reason contract were recently audited and hardened
using the review and test-driven workflow patterns from **ECC — "Everything Claude
Code"** (<https://github.com/affaan-m/ECC>), an agent-harness operating system of
reusable review agents, skills, and TDD/verification workflows. Two patterns were
applied directly here: ECC's `python-reviewer` / `code-review` lens — *check the code
against the project's own rule files and cross-file contracts* — and its
`tdd-workflow` — *reproduce each issue with a failing test (RED), fix, then lock the
behavior in (GREEN)*.

**What it surfaced and fixed:**

| Area | Issue found | Fix |
|---|---|---|
| Emergency override | The ≥300 ms / ≥95 % CPU emergency override was silently skipped when arbitration resolved to `SCALE_DOWN`, so the "always force `SCALE_UP`" guarantee could be violated. | Override now fires on any critical reading regardless of arbitrated direction. Pinned by two new invariant tests. |
| Telemetry contract | Conflict-resolution reasons (`CAPACITY_DEFERRED` / `NETWORK_DEFERRED` / safety override) were computed, then overwritten by the evidence gate — so *how* a conflict resolved never reached the output. | Added a separate, never-overwritten `conflict_reason` on `CCEOutput` / `StepRecord` / `GovernanceDecision`. Existing `arbitration_reason` values are unchanged → **no metric drift**. |
| Reason vocabulary | Two enum values were dead (never emitted) and the multi-signal safety override was mislabeled. | Removed dead values; renamed the safety reason to `SAFETY_OVERRIDE`. Every enum value is now reachable. |
| Frontend ↔ backend drift | The dashboard's reason→colour map listed reasons the backend never emits and omitted ones it does (silent grey fallback). | `REASON_COLORS` now mirrors the backend `ArbitrationReason` enum exactly. |
| Docs accuracy | The "unified evidence + dwell" docstring held only when `min_dwell_time ≥ evidence_window`. | Corrected to the actual `max(min_dwell_time, evidence_window)` relationship (matters for the sensitivity sweep). |

**How ECC helped:** it turned an ad-hoc "look it over" into a repeatable loop —
review the engine against this repo's own rule files, prove each issue with a failing
test, fix, and re-verify. That loop is what caught the emergency-override and
telemetry-contract bugs a single-file read would miss. Every fix is verified: the
backend suite is green (incl. four new invariant tests), an enumeration probe confirms
zero dead reason values, and the `arbitration_reason` output is byte-for-byte
unchanged so published metrics are unaffected. ECC: <https://github.com/affaan-m/ECC>

---

## Research paper
This work is written up as an IEEE-format paper — **currently unpublished and kept
private pending submission**, so it is intentionally not in this repository. The code →
paper-section mapping in the table above mirrors its structure; the draft is available
on request.

## License
BSD-3-Clause — see [`LICENSE`](LICENSE). The same identifier is declared in the
`license` field of [`csa_aci_fixed/pyproject.toml`](csa_aci_fixed/pyproject.toml).
