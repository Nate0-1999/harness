"""Harness configuration limited to the C.4/C.5 seams."""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class HarnessSettings(BaseSettings):
    """Provider keys and model selection named by SPEC C.5."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    spine_token: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    openrouter_api_key: SecretStr | None = None
    chat_model: str = "anthropic:claude-sonnet-4-6"
