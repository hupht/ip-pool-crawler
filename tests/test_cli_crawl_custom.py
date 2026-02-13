from cli import build_parser
import cli
from crawler.config import Settings
from crawler.dynamic_crawler import DynamicCrawlResult


def test_crawl_custom_args_parse_with_url():
    parser = build_parser()

    args = parser.parse_args([
        "crawl-custom",
        "https://example.com/proxy",
        "--max-pages",
        "3",
        "--use-ai",
        "--render-js",
        "--no-store",
        "--verbose",
    ])

    assert args.command == "crawl-custom"
    assert args.url == "https://example.com/proxy"
    assert args.max_pages == 3
    assert args.use_ai is True
    assert args.render_js is True
    assert args.no_store is True
    assert args.verbose is True


def test_crawl_custom_args_parse_with_export_options():
    parser = build_parser()

    args = parser.parse_args(
        [
            "crawl-custom",
            "https://example.com/proxy",
            "--output-json",
            "result.json",
            "--output-csv",
            "result.csv",
        ]
    )

    assert args.command == "crawl-custom"
    assert args.output_json == "result.json"
    assert args.output_csv == "result.csv"


def test_crawl_custom_args_parse_without_url():
    parser = build_parser()

    args = parser.parse_args(["crawl-custom"])

    assert args.command == "crawl-custom"
    assert args.url is None


def test_crawl_custom_interactive_mode(monkeypatch):
    captured = {}

    settings = Settings.from_env()
    settings.dynamic_crawler_enabled = True
    settings.max_pages = 5
    settings.use_ai_fallback = False
    monkeypatch.setattr(cli, "load_settings", lambda env_path: settings)

    def fake_crawl_custom_url(settings, url, max_pages, use_ai, no_store, verbose, render_js):
        captured["url"] = url
        captured["max_pages"] = max_pages
        captured["use_ai"] = use_ai
        captured["no_store"] = no_store
        captured["verbose"] = verbose
        captured["render_js"] = render_js
        return object()

    monkeypatch.setattr(cli, "crawl_custom_url", fake_crawl_custom_url)

    responses = iter([
        "https://example.com/proxy",
        "3",
        "y",
        "y",
        "n",
    ])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(responses))

    exit_code = cli.main(["crawl-custom"])

    assert exit_code == 0
    assert captured["url"] == "https://example.com/proxy"
    assert captured["max_pages"] == 3
    assert captured["use_ai"] is True
    assert captured["render_js"] is True
    assert captured["no_store"] is True


def test_crawl_custom_interactive_mode_defaults(monkeypatch):
    captured = {}

    settings = Settings.from_env()
    settings.dynamic_crawler_enabled = True
    settings.max_pages = 5
    settings.use_ai_fallback = False
    monkeypatch.setattr(cli, "load_settings", lambda env_path: settings)

    def fake_crawl_custom_url(settings, url, max_pages, use_ai, no_store, verbose, render_js):
        captured["url"] = url
        captured["max_pages"] = max_pages
        captured["use_ai"] = use_ai
        captured["no_store"] = no_store
        captured["render_js"] = render_js
        return DynamicCrawlResult(
            url=url,
            pages_crawled=1,
            extracted=1,
            valid=1,
            invalid=0,
            stored=0,
        )

    monkeypatch.setattr(cli, "crawl_custom_url", fake_crawl_custom_url)

    responses = iter([
        "https://example.com/proxy",
        "",
        "",
        "",
        "",
    ])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(responses))

    exit_code = cli.main(["crawl-custom"])

    assert exit_code == 0
    assert captured["url"] == "https://example.com/proxy"
    assert captured["max_pages"] == 5
    assert captured["use_ai"] is False
    assert captured["render_js"] is False
    assert captured["no_store"] is False


def test_crawl_custom_uses_settings_defaults(monkeypatch):
    captured = {}

    settings = Settings.from_env()
    settings.max_pages = 7
    settings.use_ai_fallback = True
    settings.dynamic_crawler_enabled = True
    monkeypatch.setattr(cli, "load_settings", lambda env_path: settings)

    def fake_crawl_custom_url(settings, url, max_pages, use_ai, no_store, verbose, render_js):
        captured["max_pages"] = max_pages
        captured["use_ai"] = use_ai
        captured["render_js"] = render_js
        return DynamicCrawlResult(
            url=url,
            pages_crawled=1,
            extracted=1,
            valid=1,
            invalid=0,
            stored=0,
        )

    monkeypatch.setattr(cli, "crawl_custom_url", fake_crawl_custom_url)

    exit_code = cli.main(["crawl-custom", "https://example.com/proxy"])

    assert exit_code == 0
    assert captured["max_pages"] == 7
    assert captured["use_ai"] is True
    assert captured["render_js"] is False


def test_crawl_custom_disabled_by_setting(monkeypatch):
    settings = Settings.from_env()
    settings.dynamic_crawler_enabled = False
    monkeypatch.setattr(cli, "load_settings", lambda env_path: settings)

    try:
        cli.main(["crawl-custom", "https://example.com/proxy"])
        assert False
    except SystemExit as exc:
        assert exc.code == 2


def test_crawl_custom_auto_triggers_check_when_stored(monkeypatch):
    settings = Settings.from_env()
    settings.dynamic_crawler_enabled = True
    monkeypatch.setattr(cli, "load_settings", lambda env_path: settings)

    monkeypatch.setattr(
        cli,
        "crawl_custom_url",
        lambda **kwargs: DynamicCrawlResult(
            url=kwargs["url"],
            pages_crawled=1,
            extracted=10,
            valid=8,
            invalid=2,
            stored=8,
        ),
    )

    called = {"n": 0}
    monkeypatch.setattr(
        cli.check_pool,
        "run_check_batch",
        lambda _settings: called.__setitem__("n", called["n"] + 1),
    )

    exit_code = cli.main(["crawl-custom", "https://example.com/proxy"])

    assert exit_code == 0
    assert called["n"] == 1


def test_crawl_custom_no_store_skips_auto_check(monkeypatch):
    settings = Settings.from_env()
    settings.dynamic_crawler_enabled = True
    monkeypatch.setattr(cli, "load_settings", lambda env_path: settings)

    monkeypatch.setattr(
        cli,
        "crawl_custom_url",
        lambda **kwargs: DynamicCrawlResult(
            url=kwargs["url"],
            pages_crawled=1,
            extracted=10,
            valid=8,
            invalid=2,
            stored=0,
        ),
    )

    called = {"n": 0}
    monkeypatch.setattr(
        cli.check_pool,
        "run_check_batch",
        lambda _settings: called.__setitem__("n", called["n"] + 1),
    )

    exit_code = cli.main(["crawl-custom", "https://example.com/proxy", "--no-store"])

    assert exit_code == 0
    assert called["n"] == 0


def test_crawl_custom_exports_json_and_csv(monkeypatch, tmp_path):
    settings = Settings.from_env()
    settings.dynamic_crawler_enabled = True
    monkeypatch.setattr(cli, "load_settings", lambda env_path: settings)

    monkeypatch.setattr(
        cli,
        "crawl_custom_url",
        lambda **kwargs: DynamicCrawlResult(
            url=kwargs["url"],
            pages_crawled=2,
            extracted=10,
            valid=8,
            invalid=2,
            stored=0,
            session_id=None,
        ),
    )

    json_path = tmp_path / "crawl_result.json"
    csv_path = tmp_path / "crawl_result.csv"

    exit_code = cli.main(
        [
            "crawl-custom",
            "https://example.com/proxy",
            "--output-json",
            str(json_path),
            "--output-csv",
            str(csv_path),
        ]
    )

    assert exit_code == 0
    assert json_path.exists()
    assert csv_path.exists()
    assert "https://example.com/proxy" in json_path.read_text(encoding="utf-8")
    assert "url" in csv_path.read_text(encoding="utf-8")
