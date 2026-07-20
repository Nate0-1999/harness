"""Harness configuration for the C.4 client and C.5 agent limits."""

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class HarnessSettings(BaseSettings):
    """Spine access, provider keys, model selection, and bounded-run defaults."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    spine_url: str = "http://localhost:8000"
    spine_token: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    chat_model: str = "openrouter:minimax/minimax-m3"
    run_request_limit: int = Field(default=40, ge=1)
    run_total_tokens_limit: int = Field(default=500_000, ge=1)
    label_max: int = Field(default=64, ge=1)
