from sqlalchemy import Column, Integer, String, Float, Boolean
from app.core.database import Base


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True, index=True)
    task_name = Column(String)
    status = Column(String, default="queued")

    # CCE decision fields
    selected_agent = Column(String, nullable=True)       # final_intent
    confidence = Column(Float, default=0.0)              # trust_score
    reason = Column(String, nullable=True)               # arbitration reason
    observed_latency = Column(Float, nullable=True)      # input latency (ms)
    conflict = Column(Boolean, default=False)            # agents conflicted?

    # Individual controller proposals
    capacity_agent = Column(String, nullable=True)       # what CapacityAgent wanted
    network_agent = Column(String, nullable=True)        # what NetworkAgent wanted