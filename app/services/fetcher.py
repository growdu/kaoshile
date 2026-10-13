"""受限 HTTP 抓取器：robots.txt 检查 + User-Agent + 限速。

约定：
- 每个 host 一次抓取后 6 小时内不再请求（v1 简化限速）；
- robots.txt 解析结果按 host 缓存；
- Disallow 命中 → 抛 FetchForbidden；
- 仅抓取白名单内源（whitelist.is_whitelisted）；
- 不重试、不跟随非 200；
- 失败抛 FetchError。

依赖：httpx（已在 dev deps）。
"""
from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from app.data_sources.whitelist import is_whitelisted
from app.infra.logging import get_logger

log = get_logger(__name__)

USER_AGENT = "Kaoshile-Verifier/0.1 (+https://kaoshile.example)"
COOLDOWN_SECONDS = 6 * 3600  # 每源 6 小时一次
ROBOTS_TTL_SECONDS = 6 * 3600


class FetchError(Exception):
    """抓取失败（网络 / 解析 / 拒绝）。"""


class FetchForbidden(FetchError):
    """robots.txt 拒绝。"""


@dataclass
class _CacheEntry:
    text: str
    expires_at: float


class Fetcher:
    """受限抓取器（线程安全）。"""

    def __init__(self, *, cooldown: int = COOLDOWN_SECONDS) -> None:
        self._lock = threading.Lock()
        self._robots_cache: dict[str, _CacheEntry] = {}
        self._last_request_at: dict[str, float] = {}
        self.cooldown = cooldown
        self.client = httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=10.0, follow_redirects=True
        )

    def close(self) -> None:
        self.client.close()

    def fetch(self, url: str) -> str:
        """抓取 URL 文本。Raises: FetchForbidden / FetchError."""
        if not is_whitelisted(url):
            raise FetchError(f"url not whitelisted: {url}")

        parsed = urlparse(url)
        host_key = f"{parsed.scheme}://{parsed.netloc}"
        now = time.monotonic()

        with self._lock:
            last = self._last_request_at.get(host_key, 0.0)
            if now - last < self.cooldown:
                raise FetchError(
                    f"cooldown: {host_key} rate-limited for "
                    f"{self.cooldown - (now - last):.0f}s"
                )
            self._last_request_at[host_key] = now

        self._check_robots(url)

        try:
            resp = self.client.get(url)
        except httpx.HTTPError as e:
            raise FetchError(f"http error: {e}") from e
        if resp.status_code != 200:
            raise FetchError(f"non-200: {resp.status_code}")
        return resp.text

    def _check_robots(self, url: str) -> None:
        """按需加载 robots.txt 并检查。"""
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        now = time.time()
        entry = self._robots_cache.get(base)
        if entry is None or entry.expires_at < now:
            try:
                resp = self.client.get(f"{base}/robots.txt")
            except httpx.HTTPError as e:
                log.warning("robots_fetch_failed", base=base, error=str(e))
                return  # 拿不到 robots 不阻塞（很多站点没有）
            if resp.status_code != 200:
                # 没 robots → 默认允许
                self._robots_cache[base] = _CacheEntry(
                    text="", expires_at=now + ROBOTS_TTL_SECONDS
                )
                return
            self._robots_cache[base] = _CacheEntry(
                text=resp.text, expires_at=now + ROBOTS_TTL_SECONDS
            )
            entry = self._robots_cache[base]

        if not entry.text:
            return
        rp = RobotFileParser()
        rp.parse(entry.text.splitlines())
        if not rp.can_fetch(USER_AGENT, url):
            raise FetchForbidden(f"robots.txt disallows: {url}")


_DEFAULT_FETCHER: Optional[Fetcher] = None


def get_fetcher() -> Fetcher:
    """进程级默认 fetcher（测试可替换）。"""
    global _DEFAULT_FETCHER
    if _DEFAULT_FETCHER is None:
        _DEFAULT_FETCHER = Fetcher()
    return _DEFAULT_FETCHER


def reset_for_test() -> None:
    global _DEFAULT_FETCHER
    if _DEFAULT_FETCHER is not None:
        _DEFAULT_FETCHER.close()
        _DEFAULT_FETCHER = None
