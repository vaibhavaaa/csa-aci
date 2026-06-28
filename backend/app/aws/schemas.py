from pydantic import BaseModel


class AWSRunRequest(BaseModel):
    task_name: str
    instance_id: str
    observed_latency: float
    throughput: float = 100.0