from pydantic import BaseModel, Field, field_validator
from croniter import croniter

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