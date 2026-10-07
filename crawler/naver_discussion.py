"""Collect discussion posts from Naver Pay Securities' JSON API."""

from __future__ import annotations

import html
import random
import re
import time
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from .config import CrawlerConfig, DEFAULT_CONFIG

_USER_AGENT = (
    "Mozilla/5.0 (Linux; Android 10) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36"
)
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
_VALID_FILTERS = {"excludeNews", "all"}
_HTML_TAG_PATTERN = re.compile(r"<[^>]*>")


def _at_path(value: Any, path: str) -> Any:
    """Resolve a dot-separated path through dictionaries and numeric list indexes."""
    if not path:
        return value
    for part in path.split("."):
        if isinstance(value, Mapping):
            if part not in value:
                return None
            value = value[part]
        elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
            try:
                value = value[int(part)]
            except (ValueError, IndexError):
                return None
        else:
            return None
    return value


def _find_posts(payload: Any) -> list[Mapping[str, Any]]:
    """Fallback discovery for common response wrappers when the configured path misses."""
    if isinstance(payload, list):
        return [post for post in payload if isinstance(post, Mapping)]
    if isinstance(payload, Mapping):
        for key in ("posts", "articles", "items", "discussionList", "contents"):
            value = payload.get(key)
            if isinstance(value, list):
                return [post for post in value if isinstance(post, Mapping)]
        for value in payload.values():
            found = _find_posts(value)
            if found:
                return found
    return []


def extract_posts(payload: Any, config: CrawlerConfig = DEFAULT_CONFIG) -> list[Mapping[str, Any]]:
    """Extract the post array using configured JSON path with common-key fallback."""
    posts = _at_path(payload, config.posts_json_path)
    if not isinstance(posts, list):
        posts = _find_posts(payload)
    return [post for post in posts if isinstance(post, Mapping)]


def extract_next_cursor(payload: Any, config: CrawlerConfig = DEFAULT_CONFIG) -> Any:
    """Read the next-page cursor; use a returned page when present."""
    cursor = _at_path(payload, config.next_cursor_json_path)
    if cursor is not None:
        return cursor
    if isinstance(payload, Mapping):
        for container in (payload, payload.get("result"), payload.get("data")):
            if isinstance(container, Mapping):
                for key in ("nextCursor", "nextPage", "nextPageToken", "cursor"):
                    if container.get(key) is not None:
                        return container[key]
                if config.pagination_key in container:
                    current = container[config.pagination_key]
                    if isinstance(current, int):
                        return current + 1
    return None


def normalize_post(
    post: Mapping[str, Any], stock_code: str, config: CrawlerConfig = DEFAULT_CONFIG
) -> dict[str, Any]:
    """Map an API post to the stable public data model."""
    normalized: dict[str, Any] = {"stock_code": stock_code}
    for target, candidates in config.post_field_mapping.items():
        value = next((post[key] for key in candidates if key in post), None)
        if target == "author" and isinstance(value, Mapping):
            value = value.get("nickname")
        if target in {"title", "content"} and isinstance(value, str):
            value = html.unescape(_HTML_TAG_PATTERN.sub(" ", value))
        normalized[target] = value
    return normalized


def _request_params(
    stock_code: str,
    filter: str,
    exchange: str,
    cursor: Any,
    config: CrawlerConfig,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        config.stock_code_param: stock_code,
        config.filter_param: filter,
        config.exchange_param: exchange,
        config.discussion_type_param: config.discussion_type,
        config.page_size_param: config.page_size,
    }
    if cursor is not None:
        params[config.pagination_param] = cursor
    return params


def fetch_page(
    client: httpx.Client,
    stock_code: str,
    filter: str,
    exchange: str,
    cursor: Any,
    config: CrawlerConfig = DEFAULT_CONFIG,
) -> Any:
    """Fetch one API page, retrying transient HTTP failures with bounded backoff."""
    params = _request_params(stock_code, filter, exchange, cursor, config)
    for attempt in range(config.max_retries + 1):
        try:
            response = client.get(config.api_url, params=params)
            if response.status_code in _RETRYABLE_STATUS_CODES:
                if attempt >= config.max_retries:
                    response.raise_for_status()
                delay = config.retry_backoff[min(attempt, len(config.retry_backoff) - 1)]
                time.sleep(delay + random.uniform(0, 0.25))
                continue
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.NetworkError):
            if attempt >= config.max_retries:
                raise
            delay = config.retry_backoff[min(attempt, len(config.retry_backoff) - 1)]
            time.sleep(delay + random.uniform(0, 0.25))
    raise RuntimeError("Request failed after retries")


def crawl_discussions(
    stock_code: str,
    filter: str = "excludeNews",
    exchange: str = "KRX",
    max_pages: int | None = None,
    *,
    config: CrawlerConfig = DEFAULT_CONFIG,
    client: httpx.Client | None = None,
) -> list[dict[str, Any]]:
    """Return unique discussion posts for a stock code.

    ``client`` is injectable to support callers that manage HTTP lifecycle or tests.
    The initial API endpoint/schema is private and should be verified against current
    browser Network requests; configure its URL and JSON paths via ``CrawlerConfig``.
    """
    code = str(stock_code).strip()
    if not code:
        raise ValueError("stock_code must not be empty")
    if filter not in _VALID_FILTERS:
        raise ValueError(f"filter must be one of {sorted(_VALID_FILTERS)}")
    if max_pages is not None and max_pages < 0:
        raise ValueError("max_pages must be non-negative or None")
    if max_pages == 0:
        return []

    owns_client = client is None
    session = client or httpx.Client(
        timeout=config.timeout,
        headers={
            "User-Agent": _USER_AGENT,
            "Referer": f"https://m.stock.naver.com/domestic/stock/{code}/discussion",
            "Accept": "application/json, text/plain, */*",
        },
        follow_redirects=True,
    )
    posts: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_cursors: set[str] = set()
    cursor = config.initial_cursor

    try:
        for page_number in range(max_pages if max_pages is not None else 2**31):
            if page_number:
                time.sleep(max(0.0, config.request_interval))
            payload = fetch_page(session, code, filter, exchange, cursor, config)
            raw_posts = extract_posts(payload, config)
            if not raw_posts:
                break

            new_posts = 0
            for raw_post in raw_posts:
                post = normalize_post(raw_post, code, config)
                article_id = post.get("article_id")
                if article_id is None:
                    # Keep records without an API ID, but avoid repeating identical rows.
                    identity = repr(sorted(post.items()))
                else:
                    identity = str(article_id)
                if identity in seen_ids:
                    continue
                seen_ids.add(identity)
                posts.append(post)
                new_posts += 1
            if new_posts == 0:
                break

            next_cursor = extract_next_cursor(payload, config)
            if next_cursor is None or str(next_cursor) == str(cursor):
                break
            cursor_identity = str(next_cursor)
            if cursor_identity in seen_cursors:
                break
            seen_cursors.add(cursor_identity)
            cursor = next_cursor
    finally:
        if owns_client:
            session.close()
    return posts
