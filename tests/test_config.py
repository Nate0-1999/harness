from harness.config import HarnessSettings


def test_c5_model_default() -> None:
    settings = HarnessSettings(
        _env_file=None,
        spine_token=None,
        anthropic_api_key=None,
        openai_api_key=None,
        openrouter_api_key=None,
    )

    assert settings.chat_model == "anthropic:claude-sonnet-4-6"
