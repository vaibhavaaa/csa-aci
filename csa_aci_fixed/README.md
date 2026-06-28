# CSA-ACI: Cognitive Stability-Aware Autonomous Cloud Infrastructure

### Intent-Governed Stability Layer for AI Factory Autonomous Controllers

Modern cloud and AI infrastructure systems increasingly operate autonomously through
controllers such as:

- Autoscalers
- Load balancers
- GPU workload schedulers
- Network congestion agents

However, under noisy telemetry and bursty AI workloads, these controllers often become
**unstable**, rapidly switching decisions and causing:

- oscillation
- resource thrashing
- performance collapse

---

## ✅ Core Idea

**CSA-ACI introduces a missing stability layer: Persistent Intent Governance.**

Instead of reacting instantly to metric spikes, CSA-ACI enforces:

- stable intent persistence
- constraint-based intent switching
- multi-agent arbitration
- governed execution under uncertainty

This prevents chaotic autonomy and enables **cognitive stability** in infrastructure control planes.

---

## ✅ Key Contribution: Cognitive Constraint Engine (CCE)

CSA-ACI implements a Cognitive Constraint Engine that governs all agent decisions through:

### 1. Intent Inertia

Intent cannot flip instantly on short-term noise.

### 2. Minimum Dwell Time

The system must hold an intent for a minimum duration before switching.

### 3. Trend-over-Noise Arbitration

Decisions are based on evidence trends, not single spikes.

### 4. Multi-Agent Conflict Resolution

When controllers disagree (capacity vs network), CSA-ACI arbitrates a stable final intent.

---

## ✅ Why This Matters for AI Factories (NVIDIA Alignment)

AI Factories operate GPU-scale clusters where instability is expensive:

- rescheduling churn wastes GPU cycles
- oscillating capacity decisions cause latency collapse
- competing controllers amplify chaos

CSA-ACI provides an intent-governed autonomy layer relevant to:

- accelerated computing infrastructure
- HPC/AI cluster control stability
- observability-driven governance

---

## ✅ Experiments Implemented

### Experiment 1 — Baseline Thrashing Controller

Demonstrates instability when controllers react instantly to noisy telemetry.

### Experiment 2 — Intent Persistence Governance

Shows reduction in oscillation by enforcing dwell-time + evidence thresholds.

### Experiment 3 — Multi-Agent Arbitration Under Conflict

Simulates conflicting infrastructure intents and resolves them through CCE governance.

---

## ✅ Core Metrics Reported

CSA-ACI quantifies stability through:

- `intent_switch_count`
- intent persistence duration
- collapse/oscillation frequency
- arbitration conflict rate

These metrics empirically capture autonomous infrastructure stability.

---

## ✅ Repository Structure

```bash
csa-aci-governed-autonomy/
│
├── simulator/        # Telemetry + baseline controller loops
├── cce/              # Cognitive Constraint Engine implementation
├── experiments/      # Stability experiments (thrashing vs governed)
├── results/          # Traces, figures, metric summaries
└── docs/             # Architecture + NVIDIA AI Factory alignment
```

## Virtual GPU Autonomy Stability Evaluation

This repository includes a virtual GPU control environment used to evaluate
stability of autonomous controllers under noisy telemetry and multi-agent conflict.

**Baseline controller**
- Reacts immediately to agent recommendations
- No intent persistence, dwell time, or evidence gating

**CSA-ACI governed controller**
- Wraps agent outputs with a Cognitive Constraint Engine (CCE)
- Enforces intent inertia, minimum dwell time, evidence-based switching,
  and bounded minimal intervention on actions

### Key Findings

**Noise robustness**
- As telemetry noise increases, baseline intent switching grows unbounded
  (switch rate ≈ 0.34 → 0.47)
- CSA-ACI remains stable across all noise levels
  (switch rate ≈ 0.095–0.10)

**Conflict robustness**
- Under moderate conflict, baseline controllers degrade performance
  (latency spikes and backlog growth)
- Under severe conflict, baseline collapses into domination
  (zero switching, runaway queues)
- CSA-ACI prevents both oscillation and conflict collapse
  by governing intent arbitration rather than raw actions

These results show that **persistent intent governance is a necessary
architectural layer for stable autonomous infrastructure**.
