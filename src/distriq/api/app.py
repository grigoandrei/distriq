from fastapi import FastAPI
from distriq.api.routers.jobs import router as jobs_router

app = FastAPI(title="Distriq", description="Distributed Job Scheduler")
app.include_router(jobs_router)