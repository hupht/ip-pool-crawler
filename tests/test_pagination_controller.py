from crawler.pagination_controller import PaginationController


def test_should_continue_respects_max_pages():
    controller = PaginationController(max_pages=2, max_pages_no_new_ip=3)

    assert controller.should_continue() is True
    controller.record_page_ips(1)
    assert controller.should_continue() is True
    controller.record_page_ips(1)
    assert controller.should_continue() is False


def test_should_continue_respects_no_new_ip_streak():
    controller = PaginationController(max_pages=10, max_pages_no_new_ip=2)

    controller.record_page_ips(0)
    assert controller.should_continue() is True
    controller.record_page_ips(0)
    assert controller.should_continue() is False


def test_mark_visited_and_next_url():
    controller = PaginationController(max_pages=5, max_pages_no_new_ip=3)

    assert controller.mark_visited("https://example.com/list") is True
    assert controller.mark_visited("https://example.com/list") is False

    next_url = controller.get_next_url("https://example.com/list", "?page=2")
    assert next_url == "https://example.com/list?page=2"

    controller.mark_visited("https://example.com/list?page=2")
    assert controller.get_next_url("https://example.com/list", "?page=2") is None


def test_stats_and_reset():
    controller = PaginationController(max_pages=5, max_pages_no_new_ip=3)
    controller.mark_visited("https://example.com/list")
    controller.record_page_ips(2)

    stats = controller.get_stats()
    assert stats["current_page"] == 1
    assert stats["visited_count"] == 1
    assert stats["ip_count_per_page"] == [2]

    controller.reset()
    stats = controller.get_stats()
    assert stats["current_page"] == 0
    assert stats["visited_count"] == 0
    assert stats["ip_count_per_page"] == []
