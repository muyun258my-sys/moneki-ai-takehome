from kbqa import config


def test_dotenv_config_and_environment_override(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "LLM_BASE_URL=https://api.deepseek.com\n"
        "LLM_API_KEY=file-key\n"
        "LLM_MODEL=deepseek-flash\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(config, "PROJECT_DIR", tmp_path)
    for name in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)

    settings = config.load_settings()
    assert settings.live
    assert settings.llm_base_url == "https://api.deepseek.com"
    assert settings.llm_api_key == "file-key"

    monkeypatch.setenv("LLM_API_KEY", "override-key")
    assert config.load_settings().llm_api_key == "override-key"
