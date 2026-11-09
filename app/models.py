from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class JobCreate(BaseModel):
    workflow: str = Field(min_length=1, max_length=120)
    sample_id: str = Field(min_length=1, max_length=120)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    fail_step: Optional[Literal["ingest", "validate", "analyze", "publish"]] = None


class JobEvent(BaseModel):
    ts: str
    event: str
    detail: str


class JobRecord(BaseModel):
    id: str
    workflow: str
    sample_id: str
    parameters: Dict[str, Any]
    fail_step: Optional[str]
    status: JobStatus
    attempt: int
    created_at: str
    updated_at: str
    events: List[JobEvent] = Field(default_factory=list)
