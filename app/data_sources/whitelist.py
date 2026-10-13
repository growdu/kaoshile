"""数据源白名单代码侧。

与 docs/data_sources.md §3 一一对应。代码与文档必须同步：
新增源需同时修改本文档与本模块，并在 commit 中说明。

约定：
- 列表只读快照（get_whitelist 返回新 dict，避免外部 mutation）；
- name 唯一；category 用于管理员后台分类展示；
- 解析助手可按 url_match 命中。
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DataSource:
    """单个权威数据源。

    Attributes:
        name: 唯一短名（如 "cpta"），用于日志与配置。
        title: 人类可读名称，用于 UI。
        category: 类别（IT / 工程 / 财经 / 医药 / 教育 / 法律 / 翻译 / 公务员 / 其他）
        base_url: 权威源首页
        entry_url: 公告入口栏目（解析助手应从此处开始）
        url_match: 用于解析助手判定「公告来自此源」的子串列表
        regions: 适用地区（"national" / 省名）
    """

    name: str
    title: str
    category: str
    base_url: str
    entry_url: str
    url_match: tuple[str, ...]
    regions: tuple[str, ...] = ("national",)


WHITELIST: tuple[DataSource, ...] = (
    DataSource(
        name="cpta",
        title="中国人事考试网",
        category="多类别",
        base_url="https://www.cpta.com.cn/",
        entry_url="https://www.cpta.com.cn/",
        url_match=("cpta.com.cn",),
    ),
    DataSource(
        name="neea",
        title="教育部考试中心",
        category="教育",
        base_url="https://www.neea.edu.cn/",
        entry_url="https://www.neea.edu.cn/",
        url_match=("neea.edu.cn",),
    ),
    DataSource(
        name="moa_kzp",
        title="财政部会计资格评价中心",
        category="财经",
        base_url="http://kzp.mof.gov.cn/",
        entry_url="http://kzp.mof.gov.cn/",
        url_match=("kzp.mof.gov.cn",),
    ),
    DataSource(
        name="scs",
        title="国家公务员局",
        category="公务员",
        base_url="http://www.scs.gov.cn/",
        entry_url="http://www.scs.gov.cn/",
        url_match=("scs.gov.cn",),
    ),
    DataSource(
        name="cicpa",
        title="中国注册会计师协会",
        category="财经",
        base_url="https://www.cicpa.org.cn/",
        entry_url="https://www.cicpa.org.cn/",
        url_match=("cicpa.org.cn",),
    ),
    DataSource(
        name="moj",
        title="司法部",
        category="法律",
        base_url="https://www.moj.gov.cn/",
        entry_url="https://www.moj.gov.cn/",
        url_match=("moj.gov.cn",),
    ),
    DataSource(
        name="21wecan",
        title="国家卫健委人才交流服务中心",
        category="医药",
        base_url="http://www.21wecan.com/",
        entry_url="http://www.21wecan.com/",
        url_match=("21wecan.com",),
    ),
    DataSource(
        name="tac",
        title="中国翻译协会（CATTI）",
        category="翻译",
        base_url="http://www.tac-online.org.cn/",
        entry_url="http://www.tac-online.org.cn/",
        url_match=("tac-online.org.cn",),
    ),
)


def get_whitelist() -> tuple[DataSource, ...]:
    """返回白名单的只读快照。"""
    return WHITELIST


def find_by_url(url: str) -> DataSource | None:
    """根据 URL 推断数据源（解析助手 / 录入校验用）。

    返回第一个 url_match 命中的源；未命中返回 None。
    """
    for src in WHITELIST:
        for needle in src.url_match:
            if needle in url:
                return src
    return None


def find_by_name(name: str) -> DataSource | None:
    """根据 name 取源。"""
    for src in WHITELIST:
        if src.name == name:
            return src
    return None


def is_whitelisted(url: str) -> bool:
    """判定 URL 是否来自白名单源（录入校验）。"""
    return find_by_url(url) is not None
