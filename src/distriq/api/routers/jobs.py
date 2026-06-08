from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from distriq.database import get_db
from distriq.models.schema import JobCreate, JobResponse, TriggerResponse, PaginatedResponse, JobRunResponse
from distriq.models.database import Job, JobRun, Status, Source
from sqlalchemy import select
from croniter import croniter
from datetime import datetime, timezone
from uuid import UUID
from distriq.redis import redis
from sqlalchemy import func

router = APIRouter(prefix="/jobs", tags=["jobs"])

@router.post("", response_model=JobResponse, status_code=201)
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

@router.get("", response_model=list[JobResponse], status_code=200)
async def get_all_jobs(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job))
    return result.scalars().all()

@router.get("/{job_id}", response_model=JobResponse, status_code=200)
async def get_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.delete("/{job_id}", response_model=JobResponse)
async def delete_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.is_active = False
    await db.commit()
    await db.refresh(job)
    return job

@router.post("/{job_id}/trigger", response_model=TriggerResponse, status_code=201)
async def trigger_job(job_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Job).where(Job.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if not job.is_active:
        raise HTTPException(status_code=409, detail="Job is not active")
    
    job_run = JobRun(
        job_id=job.id,
        status=Status.PENDING,
        source=Source.MANUAL,
        scheduled_time=datetime.now(timezone.utc),
        enqueued_time=datetime.now(timezone.utc),
    )

    db.add(job_run)
    await db.commit()
    await db.refresh(job_run)

    await redis.rpush("job_queue", str(job_run.id))
    return job_run

@router.get("/{job_id}/runs", response_model=PaginatedResponse)
async def list_job_runs(
    job_id: UUID,
    page: int = 1,
    page_size: int = 20,
    db: AsyncSession = Depends(get_db),
):
    # Verify job exists
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    # Count total runs
    total_result = await db.execute(
        select(func.count()).where(JobRun.job_id == job_id)
    )
    total = total_result.scalar()

    # Fetch paginated runs (most recent first)
    offset = (page - 1) * min(page_size, 100)
    result = await db.execute(
        select(JobRun)
        .where(JobRun.job_id == job_id)
        .order_by(JobRun.enqueued_time.desc())
        .limit(min(page_size, 100))
        .offset(offset)
    )
    runs = result.scalars().all()

    return PaginatedResponse(
        items=runs,
        total=total,
        page=page,
        page_size=min(page_size, 100),
    )

@router.get("/{job_id}/runs/{run_id}", response_model=JobRunResponse)
async def get_job_run(
    job_id: UUID,
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(JobRun).where(JobRun.id == run_id, JobRun.job_id == job_id)
    )
    job_run = result.scalar_one_or_none()
    if not job_run:
        raise HTTPException(status_code=404, detail="Run not found")
    return job_run