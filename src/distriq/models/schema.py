from pydantic import BaseModel, Field, field_validator, ConfigDict
from croniter import croniter
from datetime import datetime
from uuid import UUID
from distriq.models.database import Status, Source

class JobCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
    command: str = Field(min_length=1, max_length=1024)
    cron_expression: str
    retry_count: int = Field(default=3, ge=0, le=10)
    base_delay_seconds: int = Field(default=60, ge=1, le=3600)
    max_delay_seconds: int = Field(default=3600, ge=1, le=7200)

    @field_validator("command")
    @classmethod
    def must_be_python_script(cls, v: str) -> str:
        if not v.strip().endswith(".py"):
            raise ValueError("Command must be a Python script (ending in .py)")
        return v.strip()

    

    @field_validator("cron_expression")
    @classmethod
    def must_be_valid_cron(cls, v: str) -> str:
        if not croniter.is_valid(v):
            raise ValueError(f"Invalid cron expression: '{v}'")
        return v

class JobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    command: str
    cron_expression: str
    is_active: bool
    retry_count: int
    base_delay_seconds: int
    max_delay_seconds: int
    next_run_time: datetime | None
    created_at: datetime
    updated_at: datetime

class JobRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    job_id: UUID
    worker_id: UUID | None
    status: Status
    source: Source
    attempt_number: int
    scheduled_time: datetime
    enqueued_time: datetime
    start_time: datetime | None
    end_time: datetime | None
    output: str | None
    error: str | None
    created_at: datetime

class TriggerResponse(BaseModel):
    id: UUID
    status: Status

class HealthResponse(BaseModel):
    status: str
    database: str
    healthy_worker_count: int
    total_worker_count: int

class PaginatedResponse(BaseModel):
    items: list[JobRunResponse]
    total: int
    page: int
    page_size: int