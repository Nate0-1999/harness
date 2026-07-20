import pytest
from pydantic import ValidationError

from harness.config import HarnessSettings


def test_c5_defaults_are_local_minimax_with_bounded_runs_and_spine(monkeypatch) -> None:
    for name in (
        "CHAT_MODEL",
        "SPINE_URL",
        "RUN_REQUEST_LIMIT",
        "RUN_TOTAL_TOKENS_LIMIT",
        "LABEL_MAX",
    ):
        monkeypatch.delenv(name, raising=False)
    settings = HarnessSettings(
        _env_file=None,
        spine_token=None,
        anthropic_api_key=None,
        openai_api_key=None,
        openrouter_api_key=None,
    )

    assert settings.chat_model == "openrouter:minimax/minimax-m3"
    assert settings.spine_url == "http://localhost:8000"
    assert settings.run_request_limit == 40
    assert settings.run_total_tokens_limit == 500_000
    assert settings.label_max == 64


def test_settings_accept_environment_model_spine_and_limit_overrides(monkeypatch) -> None:
    monkeypatch.setenv("CHAT_MODEL", "anthropic:claude-sonnet-4-6")
    monkeypatch.setenv("SPINE_URL", "https://spine.example.test")
    monkeypatch.setenv("RUN_REQUEST_LIMIT", "12")
    monkeypatch.setenv("RUN_TOTAL_TOKENS_LIMIT", "3456")

    settings = HarnessSettings(_env_file=None)

    assert settings.chat_model == "anthropic:claude-sonnet-4-6"
    assert settings.spine_url == "https://spine.example.test"
    assert settings.run_request_limit == 12
    assert settings.run_total_tokens_limit == 3456


@pytest.mark.parametrize("field", ["run_request_limit", "run_total_tokens_limit", "label_max"])
def test_positive_configured_limits_are_enforced(field: str) -> None:
    with pytest.raises(ValidationError):
        HarnessSettings(_env_file=None, **{field: 0})
