from typing import Literal
from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FF_", extra="ignore", hide_input_in_errors=True)
    database_url: str = Field(default="sqlite:///data/v2.db", repr=False)
    mode: Literal["local", "demo", "private", "hosted"] = "local"
    provider: Literal["fake", "ollama", "groq"] = "fake"
    groq_api_key: SecretStr = Field(default=SecretStr(""), repr=False)
    producer_model: str = "llama3.1:8b"
    judge_model: str = "llama3.1:8b"
    ollama_url: str = "http://127.0.0.1:11434"
    deadline_seconds: float = Field(default=45, gt=0, le=120)
    max_characters: int = Field(default=20000, ge=100, le=100000)
    max_upload_bytes: int = Field(default=2_000_000, gt=0)
    lease_seconds: int = Field(default=180, ge=150)
    max_job_attempts: int = Field(default=3, ge=1, le=5)
    trusted_proxy_ips: list[str] = Field(default_factory=list)
    authorized_subject: str = ""
    owner_password_hash: SecretStr = Field(default=SecretStr(""), repr=False)
    public_origin: str = ""
    session_seconds: int = Field(default=3600, ge=300, le=86400)

    @field_validator("database_url", mode="before")
    @classmethod
    def postgres_driver(cls, value):
        if isinstance(value, str):
            if value.startswith("postgres://"):
                return value.replace("postgres://", "postgresql+psycopg://", 1)
            if value.startswith("postgresql://"):
                return value.replace("postgresql://", "postgresql+psycopg://", 1)
        return value

    mutations_per_minute: int = Field(default=30, ge=1, le=1000)
    groq_daily_calls: int = Field(default=100, ge=1, le=100000)
    groq_max_completion_tokens: int = Field(default=4096, ge=256, le=16384)
    parser_memory_mb: int = Field(default=256, ge=128, le=1024)

    @property
    def ai_ready(self) -> bool:
        """Configuration presence only; never claims live authentication succeeded."""
        return self.provider != "groq" or bool(self.groq_api_key.get_secret_value().strip())

    @model_validator(mode="after")
    def boundaries(self):
        if self.mode == "private" and (not self.trusted_proxy_ips or not self.authorized_subject):
            raise ValueError(
                "Private hosting requires trusted proxy IPs and one authorized OIDC subject"
            )
        if self.mode == "hosted":
            from urllib.parse import urlsplit
            from ffv2.auth import valid_hash

            origin = urlsplit(self.public_origin)
            if (
                origin.scheme != "https"
                or not origin.hostname
                or origin.path
                or origin.query
                or origin.fragment
                or origin.username
                or origin.password
            ):
                raise ValueError("Hosted mode requires an exact HTTPS public origin without a path")
            if not valid_hash(self.owner_password_hash.get_secret_value()):
                raise ValueError("Hosted mode requires a generated owner password hash")
        if self.mode == "demo" and self.provider != "fake":
            raise ValueError("Demo requires fake provider")
        return self
