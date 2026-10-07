"""Configuration for the Naver Pay Securities discussion API.

The endpoint and response schema are private API details and can change. Override
these values (or the corresponding ``NAVER_STOCK_*`` environment variables)
after inspecting the current requests in the browser's Network panel.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Mapping


@dataclass(frozen=True)
class CrawlerConfig:
    api_url: str = field(
        default_factory=lambda: os.getenv(
            "NAVER_STOCK_DISCUSSION_API_URL",
            "https://m.stock.naver.com/front-api/discussion/list",
        )
    )
    default_filter: str = "excludeNews"
    default_exchange: str = "KRX"
    timeout: float = 15.0
    max_retries: int = 3
    retry_backoff: tuple[float, ...] = (1.0, 2.0, 4.0)
    request_interval: float = 0.75
    page_size: int = 20

    # These request keys are configurable because Naver's private API may change.
    stock_code_param: str = "itemCode"
    filter_param: str = "filter"
    exchange_param: str = "domesticStockExchange"
    discussion_type_param: str = "discussionType"
    discussion_type: str = "domesticStock"
    pagination_param: str = "offset"
    page_size_param: str = "pageSize"
    initial_cursor: str | int | None = "-9223372036854775807"

    # Dot-separated JSON paths; an empty path means the response root.
    posts_json_path: str = "result.posts"
    next_cursor_json_path: str = "result.lastOffset"
    pagination_key: str = "offset"

    # Candidate API field names, ordered by preference.
    post_field_mapping: Mapping[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "article_id": ("id", "articleId", "article_id"),
            "title": ("title", "subject"),
            "content": ("contentSwReplaced", "content", "contents", "body"),
            "created_at": ("writtenAt", "createdAt", "writeDate", "created_at", "date"),
        }
    )


DEFAULT_CONFIG = CrawlerConfig()
