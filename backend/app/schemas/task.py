from pydantic import BaseModel, Field
from typing import Optional


class TaskCreate(BaseModel):
    task_name: str
    observed_latency: float = 122.0
    cpu_utilisation: float = 0.75
    error_rate: float = 0.0        # 0.0–1.0, replaces throughput


class SimulationStep(BaseModel):
    observed_latency: float
    cpu_utilisation: float = 0.5
    error_rate: float = 0.0        # 0.0–1.0


class SimulationRequest(BaseModel):
    steps: list[SimulationStep] = Field(
        min_length=1,
        max_length=500,
    )


class StressTestRequest(BaseModel):
    # number of repeated runs for statistical aggregation
    n_runs: int = Field(default=30, ge=2, le=200)
    # None  -> synthetic clean signal (vary noise seed)
    # "google"/"wikipedia" -> real trace + measurement-jitter bootstrap
    dataset: Optional[str] = None


class TraceReplayRequest(BaseModel):
    dataset: str = "google"            # "google" | "wikipedia"
    n_steps: int = Field(default=200, ge=20, le=2000)