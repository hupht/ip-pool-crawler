from cli import build_parser
import cli


def test_check_docs_links_args_parse_defaults():
    parser = build_parser()

    args = parser.parse_args(["check-docs-links"])

    assert args.command == "check-docs-links"
    assert args.docs_dir == "docs"
    assert args.max_errors == 100


def test_check_docs_links_command_dispatch(monkeypatch):
    captured = {}

    def fake_main(argv=None):
        captured["argv"] = argv
        return 0

    monkeypatch.setattr(cli.check_docs_links, "main", fake_main)

    exit_code = cli.main(["check-docs-links", "--docs-dir", "docs", "--max-errors", "5"])

    assert exit_code == 0
    assert "--root" in captured["argv"]
    assert "--docs-dir" in captured["argv"]
    assert "docs" in captured["argv"]
    assert "--max-errors" in captured["argv"]
    assert "5" in captured["argv"]
