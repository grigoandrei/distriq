from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from distriq.database import get_db
from distriq.models.schema import JobCreate, JobResponse
from distriq.models.database import Job
from sqlalchemy import select
from croniter import croniter
from datetime import datetime, timezone

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("/", response_model=JobResponse, status_code=201)
async def create_job(job_data: JobCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.execute(
        select(Job).where(Job.name == job_data.name)
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Job '{job_data.name}' already exists")

    cron = croniter(job_data.cron_expression, datetime.now(timezone.utc))
    next_run = cron.get_next(datetime)

    job = Job(
        name=job_data.name,
        command=job_data.command,
        cron_expression=job_data.cron_expression,
        retry_count=job_data.retry_count,
        base_delay_seconds=job_data.base_delay_seconds,
        max_delay_seconds=job_data.max_delay_seconds,
        next_run_time=next_run,
    )

    db.add(job)
    await db.commit()
    await db.refresh(job)

    return job