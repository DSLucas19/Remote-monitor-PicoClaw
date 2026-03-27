from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_host: str = "0.0.0.0"
    app_port: int = 8080
    app_name: str = "Remote Monitor Dashboard"
    app_log_buffer_size: int = 5000

    database_url: str = "sqlite:///./dashboard.db"
    jwt_secret: str = "change-this-secret"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 120
    initial_admin_key: str = "change-me-now"

    health_poll_seconds: float = 2.0
    startup_wait_seconds: float = 45.0
    stop_timeout_seconds: float = 8.0

    metaclaw_workdir: str = r"C:\Users\Chi Minh Gay\Downloads\MetaClaw-0.3.3\MetaClaw-0.3.3"
    metaclaw_command: str = "py -m metaclaw start"
    metaclaw_port: int = 30000
    metaclaw_log_file: str = ""

    picoclaw_workdir: str = r"C:\Users\Chi Minh Gay\Downloads\picoclaw_Windows_x86_64"
    picoclaw_command: str = "picoclaw-launcher.exe"
    picoclaw_port: int = 18800
    picoclaw_log_file: str = ""

    gateway_auto_connect_enabled: bool = True
    gateway_url: str = ""
    gateway_method: str = "POST"
    gateway_headers_json: str = "{}"
    gateway_body_json: str = "{}"
    gateway_timeout_seconds: float = 8.0
    gateway_retries: int = 3
    gateway_backoff_seconds: float = 2.0
    gateway_min_interval_seconds: float = 20.0


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

