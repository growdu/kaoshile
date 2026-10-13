"""fetcher 单元测试：whitelist / 限速 / robots.txt。"""
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from app.services.fetcher import FetchError, FetchForbidden, Fetcher


@pytest.fixture
def fetcher() -> Fetcher:
    f = Fetcher(cooldown=0)  # 测试不限速
    yield f
    f.close()


class TestWhitelistGate:
    """非白名单 URL 直接拒。"""

    def test_non_whitelist_raises(self, fetcher: Fetcher):
        with pytest.raises(FetchError, match="not whitelisted"):
            fetcher.fetch("https://example.com/some-page")


class TestRobots:
    """robots.txt 检查。"""

    def test_robots_disallow_raises(self, fetcher: Fetcher):
        """robots.txt 拒绝路径 → FetchForbidden。"""
        fake_resp_robots = MagicMock(status_code=200, text="User-Agent: *\nDisallow: /private\n")
        with patch.object(fetcher.client, "get") as mock_get:
            mock_get.side_effect = [fake_resp_robots]
            with pytest.raises(FetchForbidden):
                fetcher.fetch("https://www.cpta.com.cn/private/page")
            assert mock_get.call_count == 1  # 仅 robots，未继续抓页面

    def test_robots_allow_passes(self, fetcher: Fetcher):
        fake_resp_robots = MagicMock(status_code=200, text="User-Agent: *\nDisallow: /private\n")
        fake_resp_page = MagicMock(status_code=200, text="hello body")
        with patch.object(fetcher.client, "get") as mock_get:
            mock_get.side_effect = [fake_resp_robots, fake_resp_page]
            text = fetcher.fetch("https://www.cpta.com.cn/notice/page")
            assert text == "hello body"

    def test_robots_404_skips_check(self, fetcher: Fetcher):
        """robots.txt 返回 404 → 不阻塞。"""
        fake_resp_robots = MagicMock(status_code=404, text="")
        fake_resp_page = MagicMock(status_code=200, text="body")
        with patch.object(fetcher.client, "get") as mock_get:
            mock_get.side_effect = [fake_resp_robots, fake_resp_page]
            text = fetcher.fetch("https://www.cpta.com.cn/notice/page")
            assert text == "body"


class TestCooldown:
    """限速。"""

    def test_cooldown_blocks_second_request(self):
        f = Fetcher(cooldown=60)
        try:
            fake_resp_robots = MagicMock(status_code=200, text="")
            fake_resp_page1 = MagicMock(status_code=200, text="1")
            with patch.object(f.client, "get") as mock_get:
                mock_get.side_effect = [fake_resp_robots, fake_resp_page1]
                f.fetch("https://www.cpta.com.cn/x1")
                # 第二次请求同一 host → cooldown 拒绝（即使 robots mock 不变）
                with pytest.raises(FetchError, match="cooldown"):
                    f.fetch("https://www.cpta.com.cn/x2")
        finally:
            f.close()

    def test_cooldown_different_hosts(self):
        f = Fetcher(cooldown=60)
        try:
            fake_resp_robots = MagicMock(status_code=200, text="")
            fake_resp_page1 = MagicMock(status_code=200, text="1")
            fake_resp_page2 = MagicMock(status_code=200, text="2")
            with patch.object(f.client, "get") as mock_get:
                mock_get.side_effect = [
                    fake_resp_robots,  # host1 robots
                    fake_resp_page1,
                    fake_resp_robots,  # host2 robots
                    fake_resp_page2,
                ]
                t1 = f.fetch("https://www.cpta.com.cn/x1")
                t2 = f.fetch("https://www.neea.edu.cn/x2")
                assert t1 == "1"
                assert t2 == "2"
        finally:
            f.close()


class TestNon200:
    """非 200 抛 FetchError。"""

    def test_404_raises(self, fetcher: Fetcher):
        fake_resp_robots = MagicMock(status_code=200, text="")
        fake_resp_page = MagicMock(status_code=404, text="not found")
        with patch.object(fetcher.client, "get") as mock_get:
            mock_get.side_effect = [fake_resp_robots, fake_resp_page]
            with pytest.raises(FetchError, match="non-200"):
                fetcher.fetch("https://www.cpta.com.cn/x")
