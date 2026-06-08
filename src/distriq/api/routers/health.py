from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select, func
from datetime import datetime, timezone, timedelta

from distriq.database import get_db
from distriq.models.database import Worker
from distriq.models.schema import HealthResponse

router = APIRouter(tags=["health"])

@router.get("/health", response_model=HealthResponse)
async def health_check(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "unreachable"

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=90)
    healthy_result = await db.execute(
        select(func.count()).select_from(Worker).where(Worker.last_seen_at >= cutoff)
    )
    healthy_count = healthy_result.scalar() or 0

    total_result = await db.execute(
        select(func.count()).select_from(Worker)
    )
    total_count = total_result.scalar()

    is_healthy = db_status == "connected" and healthy_count > 0
    status = "healthy" if is_healthy else "degraded"
    status_code = 200 if is_healthy else 503

    response = HealthResponse(
        status=status,
        database=db_status,
        healthy_worker_count=healthy_count,
        total_worker_count=total_count,
    )

    return JSONResponse(content=response.model_dump(), status_code=status_code)