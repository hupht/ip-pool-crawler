from pathlib import Path


def test_readme_mentions_scheduler():
    text = Path("ip-pool-crawler/README.md").read_text(encoding="utf-8")
    assert "Task Scheduler" in text
    assert "cron" in text
