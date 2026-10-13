"""parse_helper 单元测试。"""
from __future__ import annotations

from datetime import datetime

from app.services.parse_helper import parse_announcement


SAMPLE_CPTA = """\
关于做好 2026 年度计算机技术与软件专业技术资格（水平）考试考务工作的通知

各有关单位：

根据《计算机技术与软件专业技术资格（水平）考试实施办法》，现将 2026 年度下半年考试有关事项通知如下：

一、考试日期
2026年11月7日 上午 09:00 - 11:30
二、报名时间
2026年8月15日 0:00 至 2026年9月5日 23:59
三、缴费截止
2026年9月10日 23:59
四、主办单位：工业和信息化部 / 人力资源和社会保障部
五、官方公告：https://www.cpta.com.cn/notice/2026-2-soft
"""


SAMPLE_JIANZHAO = """\
2026 年度一级建造师执业资格考试通知

考试时间：2026-09-20
报名时间：2026-06-15 至 2026-07-15
缴费截止：2026-07-20
准考证打印：2026-09-10

主办：住建部 / 人社部
官方：https://www.cpta.com.cn/notice/2026-jz1
"""


SAMPLE_NO_DATES = """\
某考试公告

主办：某单位
"""


class TestParseCpta:
    """CPTA 风格公告。"""

    def test_extract_name(self):
        r = parse_announcement(SAMPLE_CPTA)
        assert r.name is not None
        assert "计算机技术与软件" in r.name

    def test_extract_exam_date(self):
        r = parse_announcement(SAMPLE_CPTA)
        assert r.exam_date == datetime(2026, 11, 7)

    def test_extract_registration_start(self):
        r = parse_announcement(SAMPLE_CPTA)
        assert r.registration_start == datetime(2026, 8, 15)

    def test_extract_registration_end(self):
        r = parse_announcement(SAMPLE_CPTA)
        assert r.registration_end == datetime(2026, 9, 5)

    def test_extract_payment_end(self):
        r = parse_announcement(SAMPLE_CPTA)
        assert r.payment_end == datetime(2026, 9, 10)

    def test_extract_organizer(self):
        r = parse_announcement(SAMPLE_CPTA)
        assert r.organizer is not None
        assert "工业和信息化部" in r.organizer or "工业" in r.organizer

    def test_extract_official_url(self):
        r = parse_announcement(SAMPLE_CPTA)
        assert r.official_url == "https://www.cpta.com.cn/notice/2026-2-soft"

    def test_no_missing_required(self):
        r = parse_announcement(SAMPLE_CPTA)
        assert r.missing == []


class TestParseJianzhao:
    """数字格式日期。"""

    def test_extract_exam_date(self):
        r = parse_announcement(SAMPLE_JIANZHAO)
        assert r.exam_date == datetime(2026, 9, 20)

    def test_extract_admission(self):
        r = parse_announcement(SAMPLE_JIANZHAO)
        assert r.admission_ticket_start == datetime(2026, 9, 10)


class TestParseMissing:
    """缺失字段。"""

    def test_missing_required_dates(self):
        """无日期时主时间字段缺失；name 由 "某考试公告" 提取。"""
        r = parse_announcement(SAMPLE_NO_DATES)
        assert r.missing == ["registration_start", "registration_end", "exam_date"]
        assert r.name == "某考试公告"

    def test_raw_dates_empty(self):
        r = parse_announcement(SAMPLE_NO_DATES)
        assert r.raw_dates_found == []


class TestParseDateFormats:
    """各种日期格式。"""

    def test_dot_format(self):
        text = "考试时间：2026.11.07\n报名时间：2026.08.15 至 2026.09.05\n主办：x\n"
        r = parse_announcement(text)
        assert r.exam_date == datetime(2026, 11, 7)
        assert r.registration_start == datetime(2026, 8, 15)

    def test_slash_format(self):
        text = "考试时间：2026/11/07\n报名：2026/08/15 至 2026/09/05\n"
        r = parse_announcement(text)
        assert r.exam_date == datetime(2026, 11, 7)
