"""reminder_policy 单元测试：档位 × 节点 × 输出时刻。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

import pytest

from app.domain.reminder_policy import (
    NODE_FIELD,
    POLICIES,
    VALID_LEVELS,
    compute_send_times,
    exam_node_value,
    get_policy_summary,
)
from app.infra.time import TZ_SHANGHAI, TZ_UTC


@dataclass
class FakeExam:
    registration_start: Optional[datetime] = None
    registration_end: Optional[datetime] = None
    payment_end: Optional[datetime] = None
    admission_ticket_start: Optional[datetime] = None
    exam_date: Optional[datetime] = None


def _exam(*, exam_date: datetime = datetime(2026, 11, 7, 9, 0)) -> FakeExam:
    """完整五字段考试。"""
    return FakeExam(
        registration_start=datetime(2026, 8, 15, 0, 0),
        registration_end=datetime(2026, 9, 5, 23, 59),
        payment_end=datetime(2026, 9, 10, 23, 59),
        admission_ticket_start=datetime(2026, 10, 25, 0, 0),
        exam_date=exam_date,
    )


class TestPolicyMatrix:
    """POLICIES 结构正确。"""

    def test_three_levels_exist(self):
        assert VALID_LEVELS == {"conservative", "standard", "aggressive"}

    def test_each_level_covers_five_nodes(self):
        for lvl in VALID_LEVELS:
            assert set(POLICIES[lvl].keys()) == set(NODE_FIELD.keys())

    def test_offsets_are_integers_descending_or_zero(self):
        """偏移应是负数（提前）或 0（当天）；不应为正。"""
        for lvl, pol in POLICIES.items():
            for node, offs in pol.items():
                for off in offs:
                    assert isinstance(off, int)
                    assert off <= 0, f"{lvl}/{node} 含未来偏移 {off}"

    def test_aggressive_has_more_or_equal_offsets_than_standard(self):
        """强烈档位提前量集合应是标准档位的超集（次数更多或相等）。"""
        for node in NODE_FIELD:
            assert len(POLICIES["aggressive"][node]) >= len(POLICIES["standard"][node])
            assert len(POLICIES["standard"][node]) >= len(POLICIES["conservative"][node])


class TestComputeSendTimes:
    """compute_send_times 行为。"""

    def test_standard_exam_day_has_three_offsets(self):
        e = _exam()
        result = compute_send_times(e, "standard")
        assert len(result["exam_day"]) == 3

    def test_aggressive_exam_day_has_four_offsets(self):
        e = _exam()
        result = compute_send_times(e, "aggressive")
        assert len(result["exam_day"]) == 4

    def test_conservative_exam_day_has_one_offset(self):
        e = _exam()
        result = compute_send_times(e, "conservative")
        assert len(result["exam_day"]) == 1

    def test_offsets_applied_to_base_datetime(self):
        e = _exam(exam_date=datetime(2026, 11, 7, 9, 0))
        result = compute_send_times(e, "standard")
        # naive 视为 UTC：09:00 UTC → 17:00 SHA；提前 -7/-3/-1 天
        base_sha = datetime(2026, 11, 7, 17, 0, tzinfo=TZ_SHANGHAI)
        assert result["exam_day"] == [
            base_sha + timedelta(days=-7),
            base_sha + timedelta(days=-3),
            base_sha + timedelta(days=-1),
        ]

    def test_returns_all_five_nodes_when_all_fields_present(self):
        e = _exam()
        result = compute_send_times(e, "standard")
        assert set(result.keys()) == {
            "registration_start",
            "registration_end",
            "payment_end",
            "admission_start",
            "exam_day",
        }

    def test_skips_nodes_with_none_field(self):
        e = FakeExam(
            registration_start=datetime(2026, 8, 15),
            registration_end=datetime(2026, 9, 5),
            payment_end=None,  # 缺失
            admission_ticket_start=None,  # 缺失
            exam_date=datetime(2026, 11, 7, 9, 0),
        )
        result = compute_send_times(e, "standard")
        assert "payment_end" not in result
        assert "admission_start" not in result
        assert "registration_end" in result
        assert "exam_day" in result

    def test_invalid_level_raises(self):
        e = _exam()
        with pytest.raises(ValueError, match="invalid reminder level"):
            compute_send_times(e, "foo")

    def test_returns_shanghai_tz_aware(self):
        """输出 datetime 必须 tz-aware 且为 Asia/Shanghai。"""
        e = _exam()
        result = compute_send_times(e, "standard")
        for node, times in result.items():
            assert times, f"{node} 应有至少 1 个时刻"
            for t in times:
                assert t.tzinfo is TZ_SHANGHAI


class TestTimezoneHandling:
    """naive vs aware 输入。"""

    def test_naive_treated_as_utc(self):
        """naive datetime 视为 UTC（业务约定）。"""
        e = FakeExam(
            registration_start=datetime(2026, 8, 15, 0, 0),  # naive
            registration_end=datetime(2026, 9, 5, 23, 59),
            exam_date=datetime(2026, 11, 7, 1, 0),  # UTC 01:00
        )
        result = compute_send_times(e, "conservative")
        # exam_day 提前 3 天 → 2026-11-04 01:00 UTC = 2026-11-04 09:00 SHA
        assert result["exam_day"][0] == datetime(
            2026, 11, 4, 9, 0, tzinfo=TZ_SHANGHAI
        )

    def test_aware_utc_input_converted_to_shanghai(self):
        e = FakeExam(
            registration_start=datetime(2026, 8, 15, 0, 0, tzinfo=TZ_UTC),
            registration_end=datetime(2026, 9, 5, 23, 59, tzinfo=TZ_UTC),
            exam_date=datetime(2026, 11, 7, 1, 0, tzinfo=TZ_UTC),
        )
        result = compute_send_times(e, "conservative")
        # exam_day 提前 3 天 → 2026-11-04 01:00 UTC → 转 SHA 为 09:00
        assert result["exam_day"][0] == datetime(
            2026, 11, 4, 9, 0, tzinfo=TZ_SHANGHAI
        )


class TestExamNodeValue:
    """exam_node_value 读取字段。"""

    def test_returns_datetime_for_known_node(self):
        e = _exam()
        v = exam_node_value(e, "exam_day")
        assert v == datetime(2026, 11, 7, 9, 0)

    def test_returns_none_when_field_missing(self):
        e = FakeExam()
        assert exam_node_value(e, "payment_end") is None

    def test_unknown_node_raises(self):
        with pytest.raises(ValueError, match="unknown node"):
            exam_node_value(_exam(), "made_up_node")


class TestPolicySummary:
    """get_policy_summary 用于展示。"""

    def test_returns_all_levels(self):
        s = get_policy_summary()
        assert set(s.keys()) == VALID_LEVELS

    def test_returns_independent_copy(self):
        """修改返回的 dict 不应影响全局 POLICIES。"""
        s = get_policy_summary()
        s["conservative"]["exam_day"].append(-99)
        assert -99 not in POLICIES["conservative"]["exam_day"]
