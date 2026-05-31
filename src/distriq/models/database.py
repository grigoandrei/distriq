from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, Boolean, Integer, DateTime, func, ForeignKey, Text
from sqlalchemy import Enum as SAEnum
from uuid import UUID, uuid4
from datetime import datetime
from enum import Enum

class Status(Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    PERMANENTLY_FAILED = "PERMANENTLY_FAILED"

class Source(Enum):
    SCHEDULED = "SCHEDULED"
    MANUAL = "MANUAL"

class Base(DeclarativeBase):
    pass

class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    command: Mapped[str] = mapped_column(String(1024), nullable=False)
    cron_expression: Mapped[str] = mapped_column(String(128), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=3)
    base_delay_seconds: Mapped[int] = mapped_column(Integer, default=60)
    max_delay_seconds: Mapped[int] = mapped_column(Integer, default=3600)
    next_run_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class JobRun(Base):
    __tablename__ = "job_runs"

    id:  Mapped[UUID] = mapped_column(primary_key=True, nullable=False)
    job_id: Mapped[UUID] = mapped_column(ForeignKey("jobs.id"), nullable=True)
    worker_id: Mapped[UUID | None] = mapped_column(ForeignKey("workers.id"), default=uuid4, nullable=True)
    status: Mapped[Status] = mapped_column(SAEnum(Status), nullable=False)
    source: Mapped[Source] = mapped_column(SAEnum(Source), nullable=False)
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    scheduled_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    enqueued_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    start_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True),  nullable=True)
    end_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())