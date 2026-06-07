import asyncio
from datetime import datetime, timezone
from sqlalchemy import select
from croniter import croniter

from distriq.database import async_session
from distriq.redis import redis
from distriq.models.database import Job, JobRun, Status, Source

async def scheduler_loop():
    print("Scheduler started...")
    
    while True:
        async with async_session() as db:
            now = datetime.now(timezone.utc)
            result = await db.execute(
                select(Job).where(Job.is_active, Job.next_run_time <= now)
            )
            due_jobs = result.scalars().all()

            for job in due_jobs:
                existing_run = await db.execute(
                    select(JobRun).where(
                        JobRun.job_id == job.id,
                        JobRun.status.in_([Status.PENDING, Status.RUNNING]),
                    )
                )
                if existing_run.scalar_one_or_none():
                    continue

                job_run = JobRun(
                    job_id=job.id,
                    status=Status.PENDING,
                    source=Source.SCHEDULED,
                    scheduled_time=job.next_run_time,
                    enqueued_time=now
                )
                db.add(job_run)

                cron = croniter(job.cron_expression, now)
                job.next_run_time = cron.get_next(datetime)

                await db.commit()
                await db.refresh(job_run)

                await redis.rpush("job_queue", str(job_run.id))
                print(f"Scheduled run {job_run.id} for job '{job.name}'")

        await asyncio.sleep(15)

if __name__ == "__main__":
    asyncio.run(scheduler_loop())