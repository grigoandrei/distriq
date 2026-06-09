import asyncio
from datetime import datetime, timezone, timedelta
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

            # --- Schedule due jobs ---
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
                    enqueued_time=now,
                )
                db.add(job_run)

                cron = croniter(job.cron_expression, now)
                job.next_run_time = cron.get_next(datetime)

                await db.commit()
                await db.refresh(job_run)

                await redis.rpush("job_queue", str(job_run.id))
                print(f"Scheduled run {job_run.id} for job '{job.name}'")

            # --- Retry failed jobs ---
            failed_runs = await db.execute(
                select(JobRun).where(JobRun.status == Status.FAILED)
            )
            for run in failed_runs.scalars().all():
                job = await db.get(Job, run.job_id)

                if run.attempt_number >= job.retry_count:
                    run.status = Status.PERMANENTLY_FAILED
                    await db.commit()
                    continue

                delay = min(
                    job.base_delay_seconds * (2 ** (run.attempt_number - 1)),
                    job.max_delay_seconds,
                )
                retry_after = run.end_time + timedelta(seconds=delay)
                if datetime.now(timezone.utc) < retry_after:
                    continue

                retry_run = JobRun(
                    job_id=job.id,
                    status=Status.PENDING,
                    source=run.source,
                    attempt_number=run.attempt_number + 1,
                    scheduled_time=retry_after,
                    enqueued_time=datetime.now(timezone.utc),
                )
                db.add(retry_run)
                run.status = Status.PERMANENTLY_FAILED
                await db.commit()
                await db.refresh(retry_run)

                await redis.rpush("job_queue", str(retry_run.id))
                print(f"Retry #{retry_run.attempt_number} for job '{job.name}'")

        await asyncio.sleep(15)


if __name__ == "__main__":
    asyncio.run(scheduler_loop())
