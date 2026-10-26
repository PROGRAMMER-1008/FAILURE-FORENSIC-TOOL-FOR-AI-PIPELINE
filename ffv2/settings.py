from typing import Literal
from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FF_", extra="ignore", hide_input_in_errors=True)
    database_url: str = "sqlite:///data/v2.db"
    mode: Literal["local", "demo", "private"] = "local"
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
        if self.mode == "demo" and self.provider != "fake":
            raise ValueError("Demo requires fake provider")
        return self
