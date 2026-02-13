from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from urllib.parse import urljoin


@dataclass
class PaginationController:
    max_pages: int = 5
    max_pages_no_new_ip: int = 3
    current_page: int = 0
    visited_urls: Set[str] = field(default_factory=set)
    ip_count_per_page: List[int] = field(default_factory=list)
    no_new_ip_streak: int = 0

    def should_continue(self) -> bool:
        if self.max_pages > 0 and self.current_page >= self.max_pages:
            return False
        if self.no_new_ip_streak >= self.max_pages_no_new_ip:
            return False
        return True

    def mark_visited(self, url: str) -> bool:
        if url in self.visited_urls:
            return False
        self.visited_urls.add(url)
        return True

    def record_page_ips(self, new_ip_count: int) -> None:
        self.current_page += 1
        self.ip_count_per_page.append(new_ip_count)
        if new_ip_count > 0:
            self.no_new_ip_streak = 0
        else:
            self.no_new_ip_streak += 1

    def get_next_url(self, current_url: str, detected_next_url: Optional[str]) -> Optional[str]:
        if not detected_next_url:
            return None
        next_url = urljoin(current_url, detected_next_url)
        if next_url in self.visited_urls:
            return None
        return next_url

    def get_stats(self) -> Dict[str, object]:
        return {
            "current_page": self.current_page,
            "visited_count": len(self.visited_urls),
            "ip_count_per_page": list(self.ip_count_per_page),
            "no_new_ip_streak": self.no_new_ip_streak,
            "max_pages": self.max_pages,
            "max_pages_no_new_ip": self.max_pages_no_new_ip,
        }

    def reset(self) -> None:
        self.current_page = 0
        self.visited_urls.clear()
        self.ip_count_per_page.clear()
        self.no_new_ip_streak = 0
