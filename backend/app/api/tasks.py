import asyncio
from app.websocket.manager import manager
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.schemas.task import TaskCreate
from app.models.task import Task
from app.core.database import get_db
from app.auth.dependencies import get_current_user

from app.services.supervisor_engine import (
    run_supervised_task, run_simulation, run_ablation, reset_live_supervisor,
    run_controller_comparison, run_multi_simulation,
    run_stress_test, run_sensitivity_sweep, run_trace_replay,
    run_conflict_experiment, run_conflict_stress_test, run_guarantee_audit,
    run_closed_loop,
)
from app.services.trace_loader import list_datasets
from app.schemas.task import (
    TaskCreate, SimulationRequest, StressTestRequest, TraceReplayRequest,
)

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("/run")
async def run_task(
    data: TaskCreate,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    result = await asyncio.to_thread(
        run_supervised_task,
        data.task_name,
        data.observed_latency,
        data.cpu_utilisation,
        data.error_rate,
    )

    task = Task(
        task_name=data.task_name,
        status="done",
        selected_agent=result["final_intent"],
        confidence=result["trust_score"],
        reason=result.get("reason"),
        observed_latency=data.observed_latency,
        conflict=result.get("conflict", False),
        capacity_agent=result.get("capacity_agent"),
        network_agent=result.get("network_agent"),
    )

    try:
        db.add(task)
        db.commit()
        db.refresh(task)
        task_id = task.id
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to save task")

    await manager.broadcast({
        "event": "task_completed",
        "task": data.task_name,
        "result": result,
    })

    return {
        "user": str(user),
        "task_id": task_id,
        "result": result,
    }


@router.get("/history")
def get_history(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    tasks = db.query(Task).order_by(Task.id.asc()).limit(200).all()
    return [
        {
            "id": t.id,
            "task_name": t.task_name,
            "status": t.status,
            "final_intent": t.selected_agent,
            "trust_score": t.confidence,
            "reason": t.reason,
            "observed_latency": t.observed_latency,
            "conflict": t.conflict if t.conflict is not None else False,
            "capacity_agent": t.capacity_agent,
            "network_agent": t.network_agent,
        }
        for t in tasks
    ]


@router.post("/simulate")
async def simulate(
    data: SimulationRequest,
    user=Depends(get_current_user),
):
    result = await asyncio.to_thread(run_simulation, data.steps)

    await manager.broadcast({
        "event": "simulation_completed",
        "result": result,
    })

    return result


@router.get("/metrics")
def get_metrics(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    total = db.query(Task).count()

    if total == 0:
        return {
            "total_runs": 0,
            "intent_distribution": {},
            "average_trust_score": 0.0,
            "high_trust_runs": 0,
            "low_trust_runs": 0,
            "high_trust_percent": 0.0,
            "governance_health": "NO DATA",
        }

    intent_counts = (
        db.query(Task.selected_agent, func.count(Task.selected_agent))
        .group_by(Task.selected_agent)
        .all()
    )
    distribution = {intent: count for intent, count in intent_counts}

    avg_trust = db.query(func.avg(Task.confidence)).scalar() or 0.0
    high_trust = db.query(Task).filter(Task.confidence >= 0.8).count()
    low_trust = db.query(Task).filter(Task.confidence < 0.5).count()

    if avg_trust >= 0.85:
        health = "STABLE"
    elif avg_trust >= 0.65:
        health = "MODERATE"
    else:
        health = "DEGRADED"

    return {
        "total_runs": total,
        "intent_distribution": distribution,
        "average_trust_score": round(float(avg_trust), 3),
        "high_trust_runs": high_trust,
        "low_trust_runs": low_trust,
        "high_trust_percent": round((high_trust / total) * 100, 1),
        "governance_health": health,
    }


@router.post("/ablation")
async def ablation(
    data: SimulationRequest,
    user=Depends(get_current_user),
):
    result = await asyncio.to_thread(run_ablation, data.steps)

    await manager.broadcast({
        "event": "ablation_completed",
        "result": result,
    })

    return result


@router.post("/reset")
async def reset_supervisor(
    user=Depends(get_current_user),
):
    """Reset the persistent live supervisor. Clears evidence window and dwell timer."""
    reset_live_supervisor()
    return {"status": "reset", "message": "Live supervisor reset. Evidence window cleared."}


@router.delete("/history/flush")
async def flush_history(
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Delete ALL run history from DB and reset the live supervisor."""
    deleted = db.query(Task).delete()
    db.commit()
    reset_live_supervisor()
    return {
        "status": "flushed",
        "records_deleted": deleted,
        "message": f"Deleted {deleted} run records. Live supervisor reset.",
    }


@router.post("/compare")
async def compare_controllers(
    user=Depends(get_current_user),
):
    """Compare CSA-ACI CCE against three reactive controller paradigms."""
    result = await asyncio.to_thread(run_controller_comparison)
    await manager.broadcast({"event": "comparison_completed", "winner": result["winner"]})
    return result

@router.post("/conflict-experiment")
async def conflict_experiment(
    seed: int = 42,
    user=Depends(get_current_user),
):
    """
    The multi-signal conflict experiment — CSA-ACI's core differentiator.
    Runs latency-only controllers, a CPU-only Kubernetes-HPA archetype, and the
    multi-signal CSA-ACI CCE on identical two-signal (CPU + latency) telemetry
    across four regimes (two are conflicts). Single-signal controllers each fail
    one conflict direction; only CCE handles all four. Returns per-step decisions
    + per-regime correctness for the headline paper figure.
    """
    result = await asyncio.to_thread(run_conflict_experiment, seed)
    await manager.broadcast({
        "event": "conflict_experiment_completed",
        "winner": result["winner"],
        "cce_regimes_handled": result["analysis"]["cce_regimes_handled"],
    })
    return result


@router.post("/guarantee-audit")
async def guarantee_audit(
    user=Depends(get_current_user),
):
    """
    Empirically certify CSA-ACI's formal operating guarantees across seeds:
    bounded switching, bounded per-step intervention, bounded response lag
    (with 1-step emergency liveness), and deterministic auditable arbitration.
    These are the properties that distinguish a governance layer from a tuned
    heuristic. Passes only if every bound holds on every seed.
    """
    result = await asyncio.to_thread(run_guarantee_audit)
    await manager.broadcast({
        "event": "guarantee_audit_completed",
        "all_passed": result["all_passed"],
    })
    return result


@router.post("/closed-loop")
async def closed_loop(
    seed: int = 42,
    steps: int = 200,
    transients: bool = True,
    user=Depends(get_current_user),
):
    """
    Closed-loop control experiment (paper Section 5.6). Unlike the open-loop
    ablation/conflict experiments, each controller's scaling decision changes
    the server count, which changes the latency it observes next (M/M/1 feedback).
    With transient measurement spikes, CCE's actuation is invariant (evidence
    gate rejects the glitches) while reactive/HPA baselines churn — the
    noise-rejection result survives feedback, at the documented SLO-lag cost.
    """
    result = await asyncio.to_thread(run_closed_loop, seed, steps, transients)
    await manager.broadcast({
        "event": "closed_loop_completed",
        "stability_winner": result["stability_winner"],
        "thrash_reduction_pct": result["thrash_reduction_pct"],
    })
    return result


@router.post("/multi-sim")
async def multi_simulation(
    user=Depends(get_current_user),
):
    """
    Runs 5 predefined simulations with different seeds and load patterns.
    Each is 100 steps with Gaussian noise σ=20ms.
    Returns full traces + CSI for each simulation.
    Use this to demonstrate CCE consistency across different load scenarios.
    """
    result = await asyncio.to_thread(run_multi_simulation)
    return result


@router.post("/stress-test")
async def stress_test(
    data: StressTestRequest,
    user=Depends(get_current_user),
):
    """
    Statistical robustness. Repeats the controller comparison n_runs times and
    returns per-controller mean/std/95% CI plus a Mann-Whitney U test of CCE vs
    the best reactive controller. dataset=None uses the synthetic signal with a
    fresh seed per run; a dataset name uses a real trace + measurement jitter.
    """
    result = await asyncio.to_thread(run_stress_test, data.n_runs, data.dataset)
    await manager.broadcast({
        "event": "stress_test_completed",
        "n_runs": result["n_runs"],
    })
    return result


@router.post("/conflict-stress")
async def conflict_stress(
    data: StressTestRequest,
    user=Depends(get_current_user),
):
    """
    Statistical robustness of the multi-signal STABILITY result. Repeats the
    conflict experiment across n_runs seeds and returns per-controller mean/std/
    95% CI for the stability metrics plus a PAIRED Wilcoxon signed-rank test of
    CCE's thrash vs the strongest fair multi-signal baseline (with the honest
    SLO-lag cost reported alongside).
    """
    result = await asyncio.to_thread(run_conflict_stress_test, data.n_runs)
    await manager.broadcast({
        "event": "conflict_stress_completed",
        "n_runs": result["n_runs"],
    })
    return result


@router.post("/sensitivity")
async def sensitivity(
    user=Depends(get_current_user),
):
    """
    Hyperparameter sensitivity sweep over evidence_window x required-fraction x
    dwell-time. Returns CSI per configuration to justify the CCE defaults.
    """
    result = await asyncio.to_thread(run_sensitivity_sweep)
    return result


@router.post("/trace-replay")
async def trace_replay(
    data: TraceReplayRequest,
    user=Depends(get_current_user),
):
    """
    Replay a REAL production trace (Google/Wikipedia) through all five
    controllers. The response carries `source` ("real" vs "synthetic_fallback")
    so results are never mislabelled — only source=="real" is paper-valid.
    """
    result = await asyncio.to_thread(run_trace_replay, data.dataset, data.n_steps)
    await manager.broadcast({
        "event": "trace_replay_completed",
        "dataset": data.dataset,
        "source": result["source"],
    })
    return result


@router.get("/datasets")
def datasets(
    user=Depends(get_current_user),
):
    """List trace datasets and whether real data is present on disk."""
    return {"datasets": list_datasets()}


@router.get("/history/export")
def export_history(
    db: Session = Depends(get_db),
    user=Depends(get_current_user),
):
    """Stream all run history as CSV (for paper figures / external analysis)."""
    import csv
    import io
    from fastapi.responses import StreamingResponse

    tasks = db.query(Task).order_by(Task.id.asc()).all()

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "id", "task_name", "status", "final_intent", "trust_score",
            "reason", "observed_latency", "conflict",
            "capacity_agent", "network_agent",
        ])
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
        for t in tasks:
            writer.writerow([
                t.id, t.task_name, t.status, t.selected_agent, t.confidence,
                t.reason, t.observed_latency, t.conflict,
                t.capacity_agent, t.network_agent,
            ])
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=csa_aci_history.csv"},
    )