from crawler.sources import get_sources


def test_sources_include_all():
    sources = get_sources()
    assert len(sources) == 5
    assert any(s.name == "proxy-list-download-http" for s in sources)
