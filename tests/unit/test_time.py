"""time 工具单元测试。"""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from freezegun import freeze_time

from app.infra.time import (
    TZ_SHANGHAI,
    TZ_UTC,
    now_utc,
    now_shanghai,
    parse_iso,
    to_shanghai,
    to_utc,
)


class TestTimezones:
    """TZ 常量正确。"""

    def test_shanghai_offset_is_8_hours(self):
        # 用一个任意 datetime 看时区偏移
        sample = datetime(2026, 10, 13, 12, 0, 0, tzinfo=TZ_SHANGHAI)
        assert sample.utcoffset() == timedelta(hours=8)

    def test_utc_offset_is_zero(self):
        sample = datetime(2026, 10, 13, 12, 0, 0, tzinfo=TZ_UTC)
        assert sample.utcoffset() == timedelta(0)

    def test_shanghai_key(self):
        assert TZ_SHANGHAI.key == "Asia/Shanghai"

    def test_utc_key(self):
        assert TZ_UTC.key == "UTC"


class TestNowFunctions:
    """now_* 返回 tz-aware。"""

    @freeze_time(lambda: datetime(2026, 10, 13, 12, 0, 0, tzinfo=TZ_SHANGHAI))
    def test_now_shanghai_is_aware_and_correct_hour(self):
        n = now_shanghai()
        assert n.tzinfo is TZ_SHANGHAI
        assert n.hour == 12
        assert n.minute == 0

    @freeze_time(lambda: datetime(2026, 10, 13, 12, 0, 0, tzinfo=TZ_SHANGHAI))
    def test_now_utc_returns_utc_equivalent(self):
        n = now_utc()
        assert n.tzinfo is TZ_UTC
        assert n.hour == 4  # 12 SHA = 04 UTC
        assert n.day == 13

    def test_now_returns_recent(self):
        """未冻结时返回「当前」时间。"""
        before = datetime.now(TZ_UTC)
        n = now_utc()
        after = datetime.now(TZ_UTC)
        assert before <= n <= after


class TestToUtc:
    """to_utc 行为。"""

    def test_naive_assumed_shanghai(self):
        # 业务约定：naive 视为 shanghai
        naive = datetime(2026, 10, 13, 12, 0, 0)
        result = to_utc(naive)
        assert result.tzinfo is TZ_UTC
        assert result.hour == 4
        assert result.day == 13

    def test_aware_shanghai_to_utc(self):
        aware = datetime(2026, 10, 13, 12, 0, 0, tzinfo=TZ_SHANGHAI)
        result = to_utc(aware)
        assert result.hour == 4
        assert result.tzinfo is TZ_UTC

    def test_aware_utc_passthrough(self):
        aware = datetime(2026, 10, 13, 4, 0, 0, tzinfo=TZ_UTC)
        result = to_utc(aware)
        assert result == aware


class TestToShanghai:
    """to_shanghai 行为。"""

    def test_naive_assumed_utc(self):
        naive = datetime(2026, 10, 13, 4, 0, 0)
        result = to_shanghai(naive)
        assert result.hour == 12
        assert result.tzinfo is TZ_SHANGHAI

    def test_aware_utc_to_shanghai(self):
        aware = datetime(2026, 10, 13, 4, 0, 0, tzinfo=TZ_UTC)
        result = to_shanghai(aware)
        assert result.hour == 12

    def test_aware_shanghai_passthrough(self):
        aware = datetime(2026, 10, 13, 12, 0, 0, tzinfo=TZ_SHANGHAI)
        result = to_shanghai(aware)
        assert result == aware


class TestParseIso:
    """parse_iso 行为。"""

    def test_naive_string_assumed_shanghai(self):
        dt = parse_iso("2026-10-13T12:00:00")
        assert dt.hour == 12
        assert dt.tzinfo is TZ_SHANGHAI

    def test_with_offset(self):
        dt = parse_iso("2026-10-13T04:00:00+00:00")
        # 04:00 UTC = 12:00 SHA
        assert to_shanghai(dt).hour == 12

    def test_with_offset_keeps_aware(self):
        dt = parse_iso("2026-10-13T12:00:00+08:00")
        assert dt.tzinfo is not None
        assert dt.hour == 12

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            parse_iso("not-a-date")


class TestRoundtrip:
    """上海 ↔ UTC 互转不变。"""

    def test_roundtrip_shanghai_utc_shanghai(self):
        original = datetime(2026, 10, 13, 12, 0, 0, tzinfo=TZ_SHANGHAI)
        assert to_shanghai(to_utc(original)) == original

    def test_roundtrip_utc_shanghai_utc(self):
        original = datetime(2026, 10, 13, 4, 0, 0, tzinfo=TZ_UTC)
        assert to_utc(to_shanghai(original)) == original
