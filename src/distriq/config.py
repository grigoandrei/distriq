from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    test_database_url: str | None = None
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/distriq"
    redis_url: str = "redis://localhost:6379/0"
    scheduler_poll_intervals: int = 15
    lock_ttl: int = 300
    heartbeat_interval: int = 30
    worker_health_timeout: int = 90

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()