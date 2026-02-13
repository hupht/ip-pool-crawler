from pathlib import Path

from crawler.runtime import load_settings


def test_load_settings_with_explicit_env_path(monkeypatch, tmp_path):
    env_file = tmp_path / ".env.custom"
    env_file.write_text("HTTP_TIMEOUT=12\n", encoding="utf-8")

    called = {"path": None}

    def fake_load_dotenv(path=None):
        called["path"] = path

    monkeypatch.setattr("crawler.runtime.load_dotenv", fake_load_dotenv)
    monkeypatch.setattr("crawler.runtime.Settings.from_env", lambda: "ok")

    result = load_settings(str(env_file))

    assert result == "ok"
    assert str(called["path"]) == str(env_file)


def test_load_settings_without_existing_env_uses_default(monkeypatch):
    called = {"path": "not-called"}

    def fake_load_dotenv(path=None):
        called["path"] = path

    monkeypatch.setattr("crawler.runtime.load_dotenv", fake_load_dotenv)
    monkeypatch.setattr("crawler.runtime.Settings.from_env", lambda: "ok")
    monkeypatch.setattr(Path, "exists", lambda self: False)

    result = load_settings()

    assert result == "ok"
    assert called["path"] is None
