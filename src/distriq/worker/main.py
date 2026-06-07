import asyncio
import uuid
from datetime import datetime, timezone

from distriq.redis import redis
from distriq.database import async_session
from distriq.models.database import JobRun, Status, Job

worker_id = str(uuid.uuid4())


async def worker_loop():
    print(f"Worker {worker_id} started, waiting for jobs...")

    while True:
        # 1. Block until a job appears in the queue
        result = await redis.blpop("job_queue", timeout=0)
        run_id = result[1]

        # 2. Try to acquire the lock
        locked = await redis.set(f"lock:job_run:{run_id}", worker_id, nx=True, ex=300)
        if not locked:
            continue

        # 3. Process the job
        async with async_session() as db:
            job_run = await db.get(JobRun, run_id)
            if not job_run:
                await redis.delete(f"lock:job_run:{run_id}")
                continue

            # Update to RUNNING
            job_run.status = Status.RUNNING
            job_run.start_time = datetime.now(timezone.utc)
            await db.commit()

            # TODO: Execute the script (executor.py)
            try:
                job = await db.get(Job, job_run.job_id)
                process = await asyncio.create_subprocess_shell(
                    f"python {job.command}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, stderr = await process.communicate()

                if process.returncode == 0:
                    job_run.status = Status.COMPLETED
                    job_run.output = stdout.decode()[:1_048_576]
                else:
                    job_run.status = Status.FAILED
                    job_run.error = stderr.decode()[:10_000]

            except Exception as e:
                job_run.status = Status.FAILED
                job_run.error = str(e)[:10_000]
            
            job_run.end_time = datetime.now(timezone.utc)
            await db.commit()

            await redis.delete(f"lock:job_run:{run_id}")


if __name__ == "__main__":
    asyncio.run(worker_loop())
