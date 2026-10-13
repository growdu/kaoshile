"""解析助手：从管理员粘贴的公告文本中提取关键字段。

v1 启发式（不调用任何外部服务）：
- 时间：识别 YYYY年M月D日 / YYYY-MM-DD / YYYY.MM.DD / M月D日-M月D日；
- 名称：含「考试 / 资格 / 职称 / 注册」等关键词的标题行；
- 报名开始 / 报名截止 / 缴费截止 / 准考证 / 考试日：与时间相邻的「报名」「缴费」「准考证」「考试」关键词；
- 主办方：「主办」「承办」「主管」后的文本片段；
- 官方公告 URL：第一个 http(s):// 链接。

约定：
- 不修改任何数据库；
- 不提交任何考试记录；解析结果供管理员在 UI 校对后人工提交；
- 高亮无法解析的字段供管理员补全。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

# 多种日期格式（中文 / 数字 / 点号 / 短横线）
DATE_PATTERNS = [
    re.compile(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日"),
    re.compile(r"(20\d{2})-(\d{1,2})-(\d{1,2})"),
    re.compile(r"(20\d{2})\.(\d{1,2})\.(\d{1,2})"),
    re.compile(r"(20\d{2})/(\d{1,2})/(\d{1,2})"),
]

URL_RE = re.compile(r"https?://[^\s)）]+")

# 节点关键词 → 字段名
NODE_KEYWORDS = [
    ("报名截止", "registration_end"),
    ("报名结束", "registration_end"),
    ("缴费截止", "payment_end"),
    ("缴费结束", "payment_end"),
    ("打印开始", "admission_ticket_start"),
    ("准考证打印", "admission_ticket_start"),
    ("准考证", "admission_ticket_start"),
    ("考试日期", "exam_date"),
    ("考试时间", "exam_date"),
    ("考试日", "exam_date"),
    ("考试", "exam_date"),
    ("报名开始", "registration_start"),
    ("报名时间", "registration_start"),
    ("报名", "registration_start"),
]

NAME_KEYWORDS = ("考试", "资格", "职称", "注册", "认证", "水平", "等级")
ORGANIZER_KEYWORDS = ("主办单位", "主办", "承办", "主管", "组织")


@dataclass
class ParseResult:
    """解析结果。"""

    name: Optional[str] = None
    organizer: Optional[str] = None
    registration_start: Optional[datetime] = None
    registration_end: Optional[datetime] = None
    payment_end: Optional[datetime] = None
    admission_ticket_start: Optional[datetime] = None
    exam_date: Optional[datetime] = None
    official_url: Optional[str] = None
    """管理员需补全的字段。"""
    missing: list[str] = field(default_factory=list)
    """辅助信息。"""
    raw_dates_found: list[datetime] = field(default_factory=list)


def _to_dt(year: int, month: int, day: int) -> datetime:
    return datetime(year, month, day)


def _find_dates(text: str) -> list[datetime]:
    out: list[datetime] = []
    seen: set[tuple[int, int, int]] = set()
    for pat in DATE_PATTERNS:
        for m in pat.finditer(text):
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
            key = (y, mo, d)
            if key in seen:
                continue
            seen.add(key)
            try:
                out.append(_to_dt(y, mo, d))
            except ValueError:
                continue
    return out


def _find_first_url(text: str) -> Optional[str]:
    m = URL_RE.search(text)
    return m.group(0) if m else None


def _find_name(text: str) -> Optional[str]:
    """从首段含考试类关键词的行中提取名称。

    优先选文档开头的标题行（位置 ≤ 5 行）。
    """
    candidates: list[tuple[int, str]] = []
    for idx, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line or len(line) > 80:
            continue
        if any(kw in line for kw in NAME_KEYWORDS):
            candidates.append((idx, line))
    if not candidates:
        return None
    head = [c for c in candidates if c[0] <= 5]
    if head:
        return head[0][1]
    return candidates[0][1]


def _find_organizer(text: str) -> Optional[str]:
    for line in text.splitlines():
        line = line.strip()
        for kw in ORGANIZER_KEYWORDS:
            idx = line.find(kw)
            if idx >= 0:
                rest = line[idx + len(kw):].strip(" ：:：").strip()
                if rest and len(rest) <= 50:
                    return rest
    return None


def _assign_node_dates(
    text: str, all_dates: list[datetime]
) -> dict[str, Optional[datetime]]:
    """根据关键词定位每个节点的日期。

    简化策略：每个节点关键词第一次出现的位置，匹配最近的一个日期。
    若未匹配到，留 None。
    """
    out: dict[str, Optional[datetime]] = {
        "registration_start": None,
        "registration_end": None,
        "payment_end": None,
        "admission_ticket_start": None,
        "exam_date": None,
    }
    for keyword, field_name in NODE_KEYWORDS:
        idx = text.find(keyword)
        if idx < 0:
            continue
        if out.get(field_name) is not None and keyword not in {"报名时间", "报名"}:
            continue
        # 取关键词之后 2 行的内容（含日期所在行）
        first_nl = text.find("\n", idx)
        if first_nl < 0:
            first_nl = len(text)
        second_nl = text.find("\n", first_nl + 1)
        if second_nl < 0:
            second_nl = len(text)
        tail = text[idx:second_nl]
        dates = _find_dates(tail)
        if not dates:
            continue
        if keyword in {"报名时间", "报名"}:
            out["registration_start"] = dates[0]
            if len(dates) >= 2:
                out["registration_end"] = dates[-1]
        else:
            out[field_name] = dates[0]
    return out


def parse_announcement(text: str) -> ParseResult:
    """解析公告文本。"""
    result = ParseResult()
    all_dates = _find_dates(text)
    result.raw_dates_found = all_dates
    result.name = _find_name(text)
    result.organizer = _find_organizer(text)
    result.official_url = _find_first_url(text)
    node_dates = _assign_node_dates(text, all_dates)
    for k, v in node_dates.items():
        setattr(result, k, v)
    # missing
    if not result.name:
        result.missing.append("name")
    if not result.registration_start:
        result.missing.append("registration_start")
    if not result.registration_end:
        result.missing.append("registration_end")
    if not result.exam_date:
        result.missing.append("exam_date")
    return result
