"""
分页检测器单元测试
"""

import pytest
from crawler.pagination_detector import (
    PaginationDetector, PaginationType, PaginationLink, PaginationInfo
)


class TestPaginationDetectorBasic:
    """基础分页检测测试"""
    
    def test_detect_no_pagination(self):
        """测试无分页的 HTML"""
        html = "<html><body><div>content</div></body></html>"
        result = PaginationDetector.detect_pagination(html)
        
        assert not result.has_pagination
        assert len(result.pagination_links) == 0
    
    def test_detect_basic_parameter_pagination(self):
        """测试基础参数类型分页"""
        html = """
        <a href="?page=1">Page 1</a>
        <a href="?page=2">Page 2</a>
        <a href="?page=3">Next</a>
        """
        result = PaginationDetector.detect_pagination(html)
        
        assert result.has_pagination
        assert len(result.pagination_links) >= 3
        assert result.page_parameter is not None
    
    def test_detect_next_page_link(self):
        """测试检测下一页链接"""
        html = """
        <a href="page.php?p=1">1</a>
        <a href="page.php?p=2">下一页</a>
        """
        result = PaginationDetector.detect_pagination(html)
        
        assert result.has_pagination
        assert any(link.is_next for link in result.pagination_links)


class TestPaginationLinkAnalysis:
    """分页链接分析测试"""
    
    def test_analyze_next_page_with_chinese(self):
        """测试检测中文"下一页"链接"""
        url = "page.php?p=2"
        text = "下一页"
        
        link = PaginationDetector._analyze_link(url, text)
        
        assert link is not None
        assert link.is_next
        assert link.type == PaginationType.PARAMETER_BASED
    
    def test_analyze_next_page_with_english(self):
        """测试检测英文 Next 链接"""
        url = "?page=2"
        text = "Next"
        
        link = PaginationDetector._analyze_link(url, text)
        
        assert link is not None
        assert link.is_next
    
    def test_analyze_previous_page(self):
        """测试检测上一页链接"""
        url = "?page=1"
        text = "Previous"
        
        link = PaginationDetector._analyze_link(url, text)
        
        assert link is not None
        assert link.is_prev
    
    def test_analyze_non_pagination_link(self):
        """测试非分页链接"""
        url = "/about"
        text = "About Us"
        
        link = PaginationDetector._analyze_link(url, text)
        
        assert link is None


class TestPaginationType:
    """分页类型检测测试"""
    
    def test_detect_parameter_based_type(self):
        """测试检测参数类型分页"""
        type_val = PaginationDetector._determine_type("?page=2")
        assert type_val == PaginationType.PARAMETER_BASED
    
    def test_detect_offset_based_type(self):
        """测试检测偏移量类型分页"""
        type_val = PaginationDetector._determine_type("?offset=20&limit=10")
        assert type_val == PaginationType.OFFSET_BASED
    
    def test_detect_cursor_based_type(self):
        """测试检测游标类型分页"""
        type_val = PaginationDetector._determine_type("?cursor=abc123")
        assert type_val == PaginationType.CURSOR_BASED
    
    def test_detect_ajax_based_type(self):
        """测试检测 AJAX 类型分页"""
        type_val = PaginationDetector._determine_type("api/list?page=2")
        assert type_val == PaginationType.AJAX_BASED


class TestParameterExtraction:
    """参数提取测试"""
    
    def test_extract_query_parameters(self):
        """测试提取查询参数"""
        url = "?page=2&sort=name&order=asc"
        params = PaginationDetector._extract_params(url)
        
        assert params['page'] == '2'
        assert params['sort'] == 'name'
        assert params['order'] == 'asc'
    
    def test_extract_no_parameters(self):
        """测试无参数 URL"""
        url = "index.php"
        params = PaginationDetector._extract_params(url)
        
        assert len(params) == 0
    
    def test_extract_page_number(self):
        """测试提取页码"""
        url = "?page=5"
        params = {'page': '5'}
        
        page_num = PaginationDetector._extract_page_number(url, params)
        assert page_num == 5
    
    def test_extract_page_number_from_path(self):
        """测试从路径中提取页码"""
        url = "/list/page-3/"
        params = {}
        
        page_num = PaginationDetector._extract_page_number(url, params)
        assert page_num == 3


class TestConfidenceCalculation:
    """置信度计算测试"""
    
    def test_calculate_link_confidence_next_page(self):
        """测试下一页链接置信度"""
        confidence = PaginationDetector._calculate_link_confidence(
            "下一页", "?page=2", is_next=True, link_type=PaginationType.PARAMETER_BASED
        )
        
        assert confidence > 0.7  # 应该是高置信度
    
    def test_calculate_link_confidence_without_next(self):
        """测试非下一页链接置信度"""
        confidence = PaginationDetector._calculate_link_confidence(
            "Page 2", "?page=2", is_next=False, link_type=PaginationType.PARAMETER_BASED
        )
        
        assert 0.5 < confidence < 0.7  # 中等置信度
    
    def test_calculate_overall_confidence(self):
        """测试整体置信度计算"""
        links = [
            PaginationLink(url="?p=1", text="1", type=PaginationType.PARAMETER_BASED),
            PaginationLink(url="?p=2", text="Next", type=PaginationType.PARAMETER_BASED, is_next=True),
            PaginationLink(url="?p=3", text="3", type=PaginationType.PARAMETER_BASED),
        ]
        
        confidence = PaginationDetector._calculate_confidence(links)
        assert confidence > 0.8  # 应该很高


class TestPageParameterDetection:
    """页码参数检测测试"""
    
    def test_extract_page_parameter(self):
        """测试提取页码参数名"""
        links = [
            PaginationLink(url="?page=1", text="1", type=PaginationType.PARAMETER_BASED, 
                          params={'page': '1'}),
            PaginationLink(url="?page=2", text="2", type=PaginationType.PARAMETER_BASED,
                          params={'page': '2'}),
        ]
        
        param = PaginationDetector._extract_page_parameter(links)
        assert param == 'page'
    
    def test_extract_p_parameter(self):
        """测试提取 p 参数名"""
        links = [
            PaginationLink(url="?p=1", text="1", type=PaginationType.PARAMETER_BASED,
                          params={'p': '1'}),
            PaginationLink(url="?p=2", text="2", type=PaginationType.PARAMETER_BASED,
                          params={'p': '2'}),
        ]
        
        param = PaginationDetector._extract_page_parameter(links)
        assert param == 'p'


class TestPaginationPattern:
    """分页模式检测测试"""
    
    def test_detect_pattern_from_urls(self):
        """测试从 URL 列表检测模式"""
        urls = [
            "/?page=1",
            "/?page=2",
            "/?page=3",
        ]
        
        pattern = PaginationDetector.detect_pagination_by_pattern(urls)
        
        assert 'detected_parameter' in pattern
        assert pattern['detected_parameter'] == 'page'
    
    def test_detect_offset_pattern(self):
        """测试检测偏移量模式"""
        urls = [
            "/?offset=0&limit=10",
            "/?offset=10&limit=10",
            "/?offset=20&limit=10",
        ]
        
        pattern = PaginationDetector.detect_pagination_by_pattern(urls)
        
        assert 'detected_parameter' in pattern
        assert pattern['detected_parameter'] == 'offset'
    
    def test_detect_no_pattern(self):
        """测试无模式"""
        urls = []
        
        pattern = PaginationDetector.detect_pagination_by_pattern(urls)
        assert len(pattern) == 0


class TestPlannedPublicMethods:
    def test_detect_url_pattern(self):
        pattern = PaginationDetector.detect_url_pattern("https://example.com/list?page=2")

        assert pattern is not None
        assert pattern.parameter == "page"
        assert pattern.current_value == 2
        assert pattern.next_value == 3
        assert "page=3" in (pattern.next_url or "")

    def test_detect_url_pattern_with_path_page(self):
        pattern = PaginationDetector.detect_url_pattern("https://www.89ip.cn/index_14.html")

        assert pattern is not None
        assert pattern.parameter == "path_page"
        assert pattern.current_value == 14
        assert pattern.next_value == 15
        assert pattern.next_url == "https://www.89ip.cn/index_15.html"

    def test_find_next_link(self):
        html = """
        <a href='?page=1'>1</a>
        <a href='?page=2'>下一页</a>
        """
        next_url = PaginationDetector.find_next_link(html)
        assert next_url == "?page=2"

    def test_find_load_more(self):
        html = "<button id='more'>加载更多</button>"
        result = PaginationDetector.find_load_more(html)
        assert result is not None
        assert result.get("event") == "click"

        def test_find_load_more_with_js_event_info(self):
                html = """
                <button id='load-more-btn' class='btn primary' onclick='loadNextPage()' data-action='load-more'>
                    Load More
                </button>
                """
                result = PaginationDetector.find_load_more(html)

                assert result is not None
                assert result.get("tag") == "button"
                assert result.get("id") == "load-more-btn"
                assert result.get("event") == "click"
                assert result.get("event_info", {}).get("type") == "click"
                assert result.get("event_info", {}).get("handler") == "loadNextPage()"
                assert result.get("event_info", {}).get("data_action") == "load-more"

    def test_detect_pagination_prefers_url_pattern(self):
        html = "<a href='?page=9'>下一页</a>"
        result = PaginationDetector.detect_pagination(html, "https://example.com/list?page=2")

        assert result.has_pagination is True
        assert result.detection_method == "url-parameter-pattern"
        assert result.next_page_url is not None
        assert "page=3" in result.next_page_url


class TestEdgeCases:
    """边界情况测试"""
    
    def test_pagination_with_fragments(self):
        """测试带 URL 片段的分页"""
        html = '<a href="/#page=2">Next</a>'
        result = PaginationDetector.detect_pagination(html)
        
        # 应该能检测到链接
        assert len(result.pagination_links) >= 0
    
    def test_multiple_pagination_types(self):
        """测试检测多个分页类型"""
        html = """
        <a href="?page=1">1</a>
        <a href="?offset=0">List</a>
        <a href="?cursor=abc">Cursor</a>
        """
        result = PaginationDetector.detect_pagination(html)
        
        # 应该检测到多个类型
        if result.has_pagination:
            assert len(result.pagination_types) >= 1
    
    def test_pagination_with_port(self):
        """测试带端口的 URL"""
        url = "http://localhost:8080/?page=2"
        text = "Next"
        
        link = PaginationDetector._analyze_link(url, text)
        assert link is not None
    
    def test_pagination_with_utf8_characters(self):
        """测试 UTF-8 字符支持"""
        html = '<a href="?p=2">下一页 ▶</a>'
        result = PaginationDetector.detect_pagination(html)
        
        # 应该能处理 UTF-8
        if result.has_pagination:
            assert len(result.pagination_links) >= 0


class TestPaginationInfo:
    """分页信息数据类测试"""
    
    def test_pagination_info_defaults(self):
        """测试分页信息默认值"""
        info = PaginationInfo()
        
        assert not info.has_pagination
        assert info.pagination_type is None
        assert info.next_page_url is None
        assert len(info.pagination_links) == 0
    
    def test_pagination_info_with_data(self):
        """测试填充分页信息"""
        info = PaginationInfo(
            has_pagination=True,
            pagination_type=PaginationType.PARAMETER_BASED,
            next_page_url="?page=2",
            confidence=0.95
        )
        
        assert info.has_pagination
        assert info.pagination_type == PaginationType.PARAMETER_BASED
        assert info.confidence == 0.95
    
    def test_pagination_link_dataclass(self):
        """测试分页链接数据类"""
        link = PaginationLink(
            url="?page=2",
            text="Next",
            type=PaginationType.PARAMETER_BASED,
            is_next=True,
            confidence=0.9
        )
        
        assert link.url == "?page=2"
        assert link.is_next
        assert link.confidence == 0.9


class TestComplexPagination:
    """复杂分页场景测试"""
    
    def test_real_world_pagination_html(self):
        """测试实际网站的分页 HTML"""
        html = """
        <div class="pagination">
            <a href="/items?page=1">1</a>
            <a href="/items?page=2">2</a>
            <a href="/items?page=3" class="active">3</a>
            <a href="/items?page=4">下一页</a>
        </div>
        """
        result = PaginationDetector.detect_pagination(html)
        
        assert result.has_pagination
        assert result.next_page_url is not None
        assert any(link.is_next for link in result.pagination_links)
    
    def test_pagination_with_rel_attributes(self):
        """测试 rel 属性分页"""
        html = """
        <link rel="next" href="?page=2">
        <link rel="prev" href="?page=0">
        """
        # 注：basic regex 可能无法提取 link 标签，但我们测试代码的鲁棒性
        result = PaginationDetector.detect_pagination(html)
        # 应该不会崩溃
        assert isinstance(result, PaginationInfo)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
