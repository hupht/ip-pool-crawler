"""
分页检测器 - 自动检测网页分页模式和"下一页"链接
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class PaginationType(Enum):
    """分页类型"""
    PARAMETER_BASED = "parameter_based"      # URL 参数类型分页 (page=1, p=1)
    OFFSET_BASED = "offset_based"            # 偏移量类型分页 (offset=0, start=0)
    CURSOR_BASED = "cursor_based"            # 游标类型分页 (cursor=abc)
    AJAX_BASED = "ajax_based"                # AJAX 类型分页
    REL_PAGINATION = "rel_pagination"        # HTML rel="" 属性分页


@dataclass
class PaginationLink:
    """分页链接信息"""
    url: str                                  # 完整链接
    text: str                                 # 链接文本
    type: PaginationType                      # 分页类型
    page_num: Optional[int] = None            # 页码（如果可提取）
    confidence: float = 0.0                   # 置信度 0.0-1.0
    is_next: bool = False                     # 是否为"下一页"链接
    is_prev: bool = False                     # 是否为"上一页"链接
    params: Dict[str, Any] = field(default_factory=dict)  # 分页参数
    

@dataclass
class PaginationInfo:
    """分页信息"""
    has_pagination: bool = False              # 是否存在分页
    pagination_type: Optional[PaginationType] = None  # 分页类型
    pagination_types: List[PaginationType] = field(default_factory=list)  # 检测到的所有分页类型
    next_page_url: Optional[str] = None       # 下一页 URL
    prev_page_url: Optional[str] = None       # 上一页 URL
    page_parameter: Optional[str] = None      # 页码参数名 (page, p, pagenum等)
    current_page: Optional[int] = None        # 当前页码
    total_pages: Optional[int] = None         # 总页数（如果可提取）
    pagination_links: List[PaginationLink] = field(default_factory=list)
    confidence: float = 0.0                   # 分页检测置信度
    detection_method: str = ""                # 检测方法描述


@dataclass
class URLPattern:
    parameter: str
    current_value: Optional[int]
    next_value: Optional[int]
    next_url: Optional[str]
    confidence: float = 0.9


class PaginationDetector:
    """分页检测器 - 静态方法只"""
    
    # 常见的分页参数名
    PAGINATION_PARAMS = {
        'page', 'p', 'pagenum', 'page_no', 'pageindex', 'page_idx',
        'offset', 'start', 'begin', 'pos', 'index', 'item',
        'cursor', 'token', 'marker', 'id', 'after', 'before'
    }
    
    # 常见的"下一页"文本模式
    NEXT_PAGE_PATTERNS = [
        r'(?:下一页|next|后一页|next\s+page|more|继续|show\s+more)',
        r'(?:>|→|»|next\s*\d+)',
        r'(?:查看更多|加载更多|load\s+more)'
    ]
    
    # 常见的"上一页"文本模式
    PREV_PAGE_PATTERNS = [
        r'(?:上一页|previous|前一页|prev|上|<<|←)',
        r'(?:<|←)',
    ]
    
    @staticmethod
    def detect_pagination(html: str, base_url: str = '') -> PaginationInfo:
        """
        检测HTML中的分页信息
        
        Args:
            html: HTML 内容
            base_url: 基础 URL（用于生成完整链接）
            
        Returns:
            分页信息对象
        """
        info = PaginationInfo()

        # 优先级 1：URL 参数推断（需要页面内存在分页线索）
        url_pattern = PaginationDetector.detect_url_pattern(base_url) if base_url else None
        if url_pattern and url_pattern.next_url and PaginationDetector._has_pagination_hint(html):
            info.has_pagination = True
            info.pagination_type = PaginationType.PARAMETER_BASED
            info.pagination_types = [PaginationType.PARAMETER_BASED]
            info.next_page_url = url_pattern.next_url
            info.page_parameter = url_pattern.parameter
            info.current_page = url_pattern.current_value
            info.confidence = url_pattern.confidence
            info.detection_method = "url-parameter-pattern"
            return info
        
        # 提取所有链接（优先级 2：链接检测）
        links = PaginationDetector._extract_links(html)
        
        if not links:
            return info
        
        # 分析链接
        pagination_links = []
        detected_types = set()
        next_links = []
        
        for url, text in links:
            link_info = PaginationDetector._analyze_link(url, text, base_url)
            if link_info:
                pagination_links.append(link_info)
                detected_types.add(link_info.type)
                if link_info.is_next:
                    next_links.append(link_info)
        
        if not pagination_links:
            # 优先级 3：加载更多按钮检测
            load_more = PaginationDetector.find_load_more(html)
            if load_more:
                info.has_pagination = True
                info.pagination_type = PaginationType.AJAX_BASED
                info.pagination_types = [PaginationType.AJAX_BASED]
                info.confidence = float(load_more.get("confidence", 0.7))
                info.detection_method = "load-more-button"
            return info
        
        # 更新信息
        info.has_pagination = True
        info.pagination_links = pagination_links
        info.pagination_types = list(detected_types)
        info.pagination_type = detected_types.pop() if detected_types else None
        
        # 提取下一页链接
        if next_links:
            best_next = max(next_links, key=lambda x: x.confidence)
            info.next_page_url = best_next.url
            info.current_page = best_next.page_num
        
        # 提取页码参数
        info.page_parameter = PaginationDetector._extract_page_parameter(pagination_links)
        
        # 计算置信度
        info.confidence = PaginationDetector._calculate_confidence(pagination_links)
        
        # 生成检测方法描述
        if next_links:
            info.detection_method = f"Found {len(pagination_links)} pagination links with {len(next_links)} next page candidates"
        
        return info

    @staticmethod
    def _has_pagination_hint(html: str) -> bool:
        html_lower = html.lower()
        hint_patterns = [
            r'下一页|下页|next|next\s+page|load\s*more|加载更多|查看更多|page\s*\d+',
            r'<a[^>]+href=',
            r'rel\s*=\s*["\']next["\']',
        ]
        return any(re.search(pattern, html_lower, re.IGNORECASE) for pattern in hint_patterns)

    @staticmethod
    def detect_url_pattern(url: str) -> Optional[URLPattern]:
        if not url:
            return None

        path_match = re.search(r'(.*?)(\d+)(\.(?:html?|php|aspx?)?)$', url, re.IGNORECASE)
        if path_match:
            prefix = path_match.group(1)
            raw_value = path_match.group(2)
            suffix = path_match.group(3) or ""
            try:
                current_value = int(raw_value)
            except (TypeError, ValueError):
                current_value = None
            if current_value is not None:
                next_value = current_value + 1
                padded_next = str(next_value).zfill(len(raw_value))
                return URLPattern(
                    parameter="path_page",
                    current_value=current_value,
                    next_value=next_value,
                    next_url=f"{prefix}{padded_next}{suffix}",
                    confidence=0.9,
                )

        if "?" not in url:
            return None

        params = PaginationDetector._extract_params(url)
        ordered_candidates = ["page", "p", "page_no", "pageindex", "offset", "start"]

        for parameter in ordered_candidates:
            if parameter not in params:
                continue
            raw_value = params.get(parameter)
            try:
                current_value = int(str(raw_value))
            except (TypeError, ValueError):
                continue

            next_value = current_value + 1
            next_url = re.sub(
                rf'([?&]{re.escape(parameter)}=){re.escape(str(raw_value))}',
                rf'\g<1>{next_value}',
                url,
                count=1,
            )
            return URLPattern(
                parameter=parameter,
                current_value=current_value,
                next_value=next_value,
                next_url=next_url,
                confidence=0.95,
            )

        return None

    @staticmethod
    def find_next_link(html: str) -> Optional[str]:
        links = PaginationDetector._extract_links(html)
        best_url: Optional[str] = None
        best_score = -1.0
        for url, text in links:
            link = PaginationDetector._analyze_link(url, text)
            if link is None:
                continue
            if link.is_next and link.confidence > best_score:
                best_score = link.confidence
                best_url = link.url
        return best_url

    @staticmethod
    def find_load_more(html: str) -> Optional[dict]:
        patterns = [
            r'(?P<tag>button|a)\b(?P<attrs>[^>]*)>(?P<text>[^<]*(?:加载更多|查看更多|load\s*more|show\s*more)[^<]*)</\1>',
        ]

        for pattern in patterns:
            match = re.search(pattern, html, re.IGNORECASE)
            if not match:
                continue

            attrs = match.group("attrs") or ""
            text = (match.group("text") or "").strip()
            onclick_match = re.search(r'onclick\s*=\s*["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            data_action_match = re.search(r'data-action\s*=\s*["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            id_match = re.search(r'id\s*=\s*["\']([^"\']+)["\']', attrs, re.IGNORECASE)
            class_match = re.search(r'class\s*=\s*["\']([^"\']+)["\']', attrs, re.IGNORECASE)

            event_info: Dict[str, Any] = {
                "type": "click",
                "handler": onclick_match.group(1).strip() if onclick_match else None,
                "data_action": data_action_match.group(1).strip() if data_action_match else None,
            }

            return {
                "tag": match.group("tag").lower(),
                "id": id_match.group(1).strip() if id_match else None,
                "class": class_match.group(1).strip() if class_match else None,
                "text": text,
                "confidence": 0.8 if (event_info["handler"] or event_info["data_action"]) else 0.7,
                "event": "click",
                "event_info": event_info,
            }
        return None
    
    @staticmethod
    def _extract_links(html: str) -> List[tuple]:
        """
        从HTML中提取所有链接
        返回 [(url, text), ...]
        """
        # 简单的链接提取
        link_pattern = r'<a\s+(?:[^>]*?\s+)?href=["\']([^"\']*)["\'](?:[^>]*)>([^<]*)<\/a>'
        matches = re.findall(link_pattern, html, re.IGNORECASE)
        return matches
    
    @staticmethod
    def _analyze_link(url: str, text: str, base_url: str = '') -> Optional[PaginationLink]:
        """
        分析单个链接是否为分页链接
        """
        text_lower = text.lower().strip()
        url_lower = url.lower()
        
        # 检查是否为分页链接
        if not PaginationDetector._is_pagination_link(url):
            return None
        
        # 确定分页类型
        pagination_type = PaginationDetector._determine_type(url)
        
        # 检查是否为下一页链接
        is_next = PaginationDetector._is_next_page(text_lower, url_lower)
        is_prev = PaginationDetector._is_prev_page(text_lower, url_lower)
        
        # 提取参数
        params = PaginationDetector._extract_params(url)
        
        # 提取页码
        page_num = PaginationDetector._extract_page_number(url, params)
        
        # 计算置信度
        confidence = PaginationDetector._calculate_link_confidence(
            text_lower, url_lower, is_next, pagination_type
        )
        
        return PaginationLink(
            url=url,
            text=text,
            type=pagination_type,
            page_num=page_num,
            confidence=confidence,
            is_next=is_next,
            is_prev=is_prev,
            params=params
        )
    
    @staticmethod
    def _is_pagination_link(url: str) -> bool:
        """检查URL是否可能为分页链接"""
        url_lower = url.lower()
        
        # 检查是否包含分页参数
        for param in PaginationDetector.PAGINATION_PARAMS:
            if f'{param}=' in url_lower or f'/{param}/' in url_lower:
                return True
        
        # 检查是否为 AJAX 请求
        if 'ajax' in url_lower or 'api' in url_lower:
            return True

        # 检查路径型分页（如 index_14.html、/page/2、-p3）
        path_patterns = [
            r'index[_\-/]?\d+\.(?:html?|php|aspx?)',
            r'/page[_\-/]?\d+',
            r'[_\-/]p\d+(?:\.|/|$)',
        ]
        if any(re.search(pattern, url_lower, re.IGNORECASE) for pattern in path_patterns):
            return True
        
        return False
    
    @staticmethod
    def _determine_type(url: str) -> PaginationType:
        """确定分页类型"""
        url_lower = url.lower()
        
        if 'offset' in url_lower or 'start' in url_lower:
            return PaginationType.OFFSET_BASED
        elif 'cursor' in url_lower or 'token' in url_lower:
            return PaginationType.CURSOR_BASED
        elif 'ajax' in url_lower or 'api' in url_lower:
            return PaginationType.AJAX_BASED
        else:
            return PaginationType.PARAMETER_BASED
    
    @staticmethod
    def _is_next_page(text: str, url: str) -> bool:
        """检查是否为下一页链接"""
        # 检查文本
        for pattern in PaginationDetector.NEXT_PAGE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        # 检查 URL 中的 rel 属性（如果HTML包含）
        if 'rel=next' in url or 'next' in url:
            return True
        
        return False
    
    @staticmethod
    def _is_prev_page(text: str, url: str) -> bool:
        """检查是否为上一页链接"""
        for pattern in PaginationDetector.PREV_PAGE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        
        if 'rel=prev' in url or 'previous' in url:
            return True
        
        return False
    
    @staticmethod
    def _extract_params(url: str) -> Dict[str, Any]:
        """从URL中提取参数"""
        params = {}
        
        # 简单的查询参数提取
        if '?' in url:
            query_string = url.split('?', 1)[1]
            for param_pair in query_string.split('&'):
                if '=' in param_pair:
                    key, value = param_pair.split('=', 1)
                    params[key] = value
        
        return params
    
    @staticmethod
    def _extract_page_number(url: str, params: Dict[str, Any]) -> Optional[int]:
        """从URL中提取页码"""
        # 优先从参数中提取
        for page_param in ['page', 'p', 'pagenum', 'page_no', 'pageindex']:
            if page_param in params:
                try:
                    return int(params[page_param])
                except (ValueError, TypeError):
                    pass
        
        # 从 URL 路径中提取
        match = re.search(r'/p(?:age)?[\/-]?(\d+)', url, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except ValueError:
                pass
        
        return None
    
    @staticmethod
    def _calculate_link_confidence(text: str, url: str, is_next: bool, link_type: PaginationType) -> float:
        """
        计算单个链接的置信度
        
        Returns:
            0.0-1.0 的置信度
        """
        confidence = 0.5
        
        # 如果明确标记为下一页，增加置信度
        if is_next:
            confidence += 0.3
        
        # 基于链接类型调整
        if link_type == PaginationType.PARAMETER_BASED:
            confidence += 0.1
        elif link_type == PaginationType.CURSOR_BASED:
            confidence += 0.05
        elif link_type == PaginationType.AJAX_BASED:
            confidence -= 0.1  # AJAX 链接不太可靠
        
        # 确保在 0-1 范围内
        return min(1.0, max(0.0, confidence))
    
    @staticmethod
    def _extract_page_parameter(links: List[PaginationLink]) -> Optional[str]:
        """
        从分页链接中提取常见的页码参数名
        
        Returns:
            参数名或 None
        """
        param_counts = {}
        
        for link in links:
            for param in link.params:
                if param.lower() in PaginationDetector.PAGINATION_PARAMS:
                    param_counts[param] = param_counts.get(param, 0) + 1
        
        if param_counts:
            return max(param_counts, key=param_counts.get)
        
        return None
    
    @staticmethod
    def _calculate_confidence(links: List[PaginationLink]) -> float:
        """
        计算整体分页检测置信度
        
        Returns:
            0.0-1.0 的置信度
        """
        if not links:
            return 0.0
        
        # 基于下一页链接数量
        next_links_count = sum(1 for l in links if l.is_next)
        
        if next_links_count == 0:
            base_confidence = 0.6  # 没有明确的下一页链接
        elif next_links_count == 1:
            base_confidence = 0.9  # 一个明确的下一页链接
        else:
            base_confidence = 0.85  # 多个下一页链接（可能重复）
        
        # 基于链接数量
        if len(links) >= 3:
            base_confidence += 0.05
        
        return min(1.0, base_confidence)
    
    @staticmethod
    def detect_pagination_by_pattern(urls: List[str]) -> Dict[str, Any]:
        """
        通过 URL 列表检测分页模式
        
        Args:
            urls: URL 列表
            
        Returns:
            检测到的分页模式字典
        """
        if not urls:
            return {}
        
        pattern = {
            'urls': urls,
            'param_changes': {},
            'detected_parameter': None,
        }
        
        # 分析参数变化
        for i, url in enumerate(urls):
            params = PaginationDetector._extract_params(url)
            if i > 0:
                prev_params = PaginationDetector._extract_params(urls[i-1])
                
                # 找到变化的参数
                for key in params:
                    if key in prev_params and params[key] != prev_params[key]:
                        if key not in pattern['param_changes']:
                            pattern['param_changes'][key] = []
                        pattern['param_changes'][key].append({
                            'prev': prev_params[key],
                            'curr': params[key],
                            'index': i
                        })
        
        # 确定最可能的分页参数
        if pattern['param_changes']:
            # 选择变化最频繁的参数
            param_change_count = {
                k: len(v) for k, v in pattern['param_changes'].items()
            }
            pattern['detected_parameter'] = max(param_change_count, key=param_change_count.get)
        
        return pattern
