import uuid
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field
from pathlib import Path


class Settings(BaseSettings):
    agent_id: str = Field(str(uuid.uuid4()), env="AGENT_ID")
    agent_name: str = Field("AGENT-1", env="AGENT_NAME")
    nats_url: List[str] = Field(default=["nats://127.0.0.1:4222"], env="NATS_URL")
    modules_path: Path = Field(default=Path("modules"))
    error_log_dir: Path = Field(default=Path(".errors"))
    message_log_dir: Path = Field(default=Path(".messages"))
    crash_state_file: Path = Field(default=Path(".errors/crash_state.json"))
    max_crash_retries: int = 3

    class Config:
        env_file = ".env"


settings = Settings()

settings.modules_path.mkdir(parents=True, exist_ok=True)
settings.error_log_dir.mkdir(parents=True, exist_ok=True)
settings.message_log_dir.mkdir(parents=True, exist_ok=True)
settings.crash_state_file.touch()
