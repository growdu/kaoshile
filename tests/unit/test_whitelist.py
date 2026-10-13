"""白名单单元测试。"""
from __future__ import annotations

import pytest

from app.data_sources.whitelist import (
    WHITELIST,
    DataSource,
    find_by_name,
    find_by_url,
    get_whitelist,
    is_whitelisted,
)


class TestWhitelistStructure:
    """WHITELIST 结构正确。"""

    def test_at_least_8_sources(self):
        """与 docs/data_sources.md §3 同步：国家级 + 行业 ≥ 8。"""
        assert len(WHITELIST) >= 8

    def test_unique_names(self):
        names = [s.name for s in WHITELIST]
        assert len(names) == len(set(names)), f"重复 name: {names}"

    def test_unique_base_urls(self):
        urls = [s.base_url for s in WHITELIST]
        assert len(urls) == len(set(urls))

    def test_all_have_url_match(self):
        for s in WHITELIST:
            assert len(s.url_match) > 0

    def test_required_categories_present(self):
        cats = {s.category for s in WHITELIST}
        # docs/data_sources.md §3 涵盖：财经 / 教育 / 公务员 / 法律 / 医药 / 翻译
        for required in {"财经", "教育", "公务员", "法律", "医药", "翻译"}:
            assert required in cats, f"缺失类别: {required}"


class TestFrozenDataclass:
    """DataSource 不可变。"""

    def test_data_source_is_frozen(self):
        src = WHITELIST[0]
        with pytest.raises(Exception):  # FrozenInstanceError 或 AttributeError
            src.name = "changed"  # type: ignore[misc]


class TestWhitelist:
    """get_whitelist 返回只读快照。"""


def test_get_whitelist_returns_tuple():
    wl = get_whitelist()
    assert isinstance(wl, tuple)
    assert len(wl) == len(WHITELIST)


class TestFindByUrl:
    """按 URL 命中数据源。"""

    def test_cpta_match(self):
        src = find_by_url("https://www.cpta.com.cn/exam/2026/")
        assert src is not None
        assert src.name == "cpta"

    def test_neea_match(self):
        src = find_by_url("https://www.neea.edu.cn/notice/123")
        assert src is not None
        assert src.name == "neea"

    def test_unknown_returns_none(self):
        assert find_by_url("https://example.com/random") is None


class TestFindByName:
    """按 name 取源。"""

    def test_known(self):
        assert find_by_name("cpta") is not None

    def test_unknown_returns_none(self):
        assert find_by_name("nope") is None


class TestIsWhitelisted:
    """录入校验：URL 必须来自白名单。"""

    def test_whitelisted_url(self):
        assert is_whitelisted("https://www.cpta.com.cn/somewhere") is True

    def test_unlisted_url(self):
        assert is_whitelisted("https://example.com/foo") is False


def test_documentation_sync_marker():
    """提醒测试：与 docs/data_sources.md §3 保持同步。

    修改白名单时务必同时更新文档，并加一条过程记录。
    """
    # 此测试断言的意图：每次新增 source 后，记得 push 到 docs。
    # 它本身不检查内容，但是是「必须修改」的提示。
    assert len(WHITELIST) > 0
