"""灌入 demo 数据：≥ 10 类别 / ≥ 30 场考试 / ≥ 5 条订阅。

按 docs/seed_exams.md 选取代表性考试。运行：
    uv run python scripts/seed_demo.py
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.tokens import sign
from app.infra.db import get_session_factory
from app.infra.logging import configure_logging, get_logger
from app.repository.models import Exam, Subscription
from app.repository.orm import ExamStatus, SubscriptionStatus

log = get_logger(__name__)


def _days_from_now(days: int) -> datetime:
    return datetime.utcnow() + timedelta(days=days)


def seed() -> None:
    """执行灌入。"""
    configure_logging()
    factory = get_session_factory()

    with factory() as session:  # type: ignore[call-arg]
        if session.execute(select(Exam).limit(1)).scalar_one_or_none() is not None:
            log.warning("seed_skip_already_seeded")
            return

        exams: list[Exam] = [
            # IT 软考
            Exam(
                name="信息系统项目管理师 2026 下半年",
                category="IT",
                organizer="工信部 / 人社部",
                registration_start=_days_from_now(20),
                registration_end=_days_from_now(35),
                payment_end=_days_from_now(40),
                admission_ticket_start=_days_from_now(75),
                exam_date=_days_from_now(90),
                official_url="https://www.cpta.com.cn/",
                source_url="https://www.cpta.com.cn/notice/2026-2-soft",
                status=ExamStatus.open,
            ),
            Exam(
                name="系统集成项目管理工程师 2026 下半年",
                category="IT",
                organizer="工信部 / 人社部",
                registration_start=_days_from_now(20),
                registration_end=_days_from_now(35),
                payment_end=_days_from_now(40),
                exam_date=_days_from_now(90),
                source_url="https://www.cpta.com.cn/notice/2026-2-soft-2",
                status=ExamStatus.open,
            ),
            Exam(
                name="网络工程师 2026 下半年",
                category="IT",
                organizer="工信部 / 人社部",
                registration_start=_days_from_now(20),
                registration_end=_days_from_now(35),
                exam_date=_days_from_now(90),
                source_url="https://www.cpta.com.cn/notice/2026-2-soft-3",
                status=ExamStatus.open,
            ),
            # 工程 - 建造师
            Exam(
                name="一级建造师 2026",
                category="工程",
                organizer="住建部 / 人社部",
                registration_start=_days_from_now(10),
                registration_end=_days_from_now(30),
                payment_end=_days_from_now(35),
                exam_date=_days_from_now(70),
                source_url="https://www.cpta.com.cn/notice/2026-jz1",
                status=ExamStatus.open,
            ),
            Exam(
                name="二级建造师 2026 (北京)",
                category="工程",
                organizer="北京市人社局",
                registration_start=_days_from_now(5),
                registration_end=_days_from_now(20),
                exam_date=_days_from_now(80),
                source_url="https://www.bjrbj.gov.cn/bjpta/2026/jz2",
                status=ExamStatus.open,
            ),
            Exam(
                name="监理工程师 2026",
                category="工程",
                organizer="住建部 / 人社部",
                registration_start=_days_from_now(15),
                registration_end=_days_from_now(30),
                exam_date=_days_from_now(75),
                source_url="https://www.cpta.com.cn/notice/2026-jl",
                status=ExamStatus.open,
            ),
            # 工程 - 安全
            Exam(
                name="注册安全工程师 2026",
                category="工程",
                organizer="应急管理部 / 人社部",
                registration_start=_days_from_now(15),
                registration_end=_days_from_now(30),
                exam_date=_days_from_now(85),
                source_url="https://www.cpta.com.cn/notice/2026-aq",
                status=ExamStatus.open,
            ),
            Exam(
                name="一级注册消防工程师 2026",
                category="工程",
                organizer="应急管理部消防救援局",
                registration_start=_days_from_now(20),
                registration_end=_days_from_now(40),
                exam_date=_days_from_now(95),
                source_url="https://www.cpta.com.cn/notice/2026-xf",
                status=ExamStatus.open,
            ),
            # 财经 - 会计
            Exam(
                name="初级会计专业技术资格 2026",
                category="财经",
                organizer="财政部 / 人社部",
                registration_start=_days_from_now(10),
                registration_end=_days_from_now(40),
                payment_end=_days_from_now(50),
                exam_date=_days_from_now(120),
                source_url="http://kzp.mof.gov.cn/notice/2026-cj",
                status=ExamStatus.open,
            ),
            Exam(
                name="中级会计专业技术资格 2026",
                category="财经",
                organizer="财政部 / 人社部",
                registration_start=_days_from_now(100),
                registration_end=_days_from_now(130),
                payment_end=_days_from_now(140),
                exam_date=_days_from_now(220),
                source_url="http://kzp.mof.gov.cn/notice/2026-cj-2",
                status=ExamStatus.open,
            ),
            Exam(
                name="高级会计专业技术资格 2026",
                category="财经",
                organizer="财政部 / 人社部",
                registration_start=_days_from_now(40),
                registration_end=_days_from_now(70),
                exam_date=_days_from_now(120),
                source_url="http://kzp.mof.gov.cn/notice/2026-cj-3",
                status=ExamStatus.open,
            ),
            # 财经 - 注会
            Exam(
                name="CPA 专业阶段 2026",
                category="财经",
                organizer="财政部 / 中注协",
                registration_start=_days_from_now(40),
                registration_end=_days_from_now(80),
                exam_date=_days_from_now(220),
                source_url="https://www.cicpa.org.cn/notice/2026-cpa",
                status=ExamStatus.open,
            ),
            Exam(
                name="CPA 综合阶段 2026",
                category="财经",
                organizer="财政部 / 中注协",
                registration_start=_days_from_now(40),
                registration_end=_days_from_now(80),
                exam_date=_days_from_now(220),
                source_url="https://www.cicpa.org.cn/notice/2026-cpa-2",
                status=ExamStatus.open,
            ),
            Exam(
                name="税务师 2026",
                category="财经",
                organizer="中国注册税务师协会",
                registration_start=_days_from_now(50),
                registration_end=_days_from_now(120),
                exam_date=_days_from_now(250),
                source_url="http://www.cctaa.cn/notice/2026-tax",
                status=ExamStatus.open,
            ),
            # 财经 - 其他
            Exam(
                name="审计专业技术资格 2026",
                category="财经",
                organizer="审计署 / 人社部",
                registration_start=_days_from_now(30),
                registration_end=_days_from_now(60),
                exam_date=_days_from_now(120),
                source_url="https://www.cpta.com.cn/notice/2026-audit",
                status=ExamStatus.open,
            ),
            Exam(
                name="统计专业技术资格 2026",
                category="财经",
                organizer="国家统计局 / 人社部",
                registration_start=_days_from_now(30),
                registration_end=_days_from_now(60),
                exam_date=_days_from_now(120),
                source_url="https://www.cpta.com.cn/notice/2026-stat",
                status=ExamStatus.open,
            ),
            Exam(
                name="经济专业技术资格 2026",
                category="财经",
                organizer="人社部",
                registration_start=_days_from_now(30),
                registration_end=_days_from_now(60),
                exam_date=_days_from_now(120),
                source_url="https://www.cpta.com.cn/notice/2026-econ",
                status=ExamStatus.open,
            ),
            # 医药
            Exam(
                name="执业药师 2026",
                category="医药",
                organizer="国家药监局 / 人社部",
                registration_start=_days_from_now(20),
                registration_end=_days_from_now(50),
                exam_date=_days_from_now(110),
                source_url="https://www.cpta.com.cn/notice/2026-yao",
                status=ExamStatus.open,
            ),
            Exam(
                name="护士执业资格 2026",
                category="医药",
                organizer="国家卫健委",
                registration_start=_days_from_now(50),
                registration_end=_days_from_now(80),
                exam_date=_days_from_now(120),
                source_url="http://www.21wecan.com/notice/2026-nurse",
                status=ExamStatus.open,
            ),
            Exam(
                name="卫生专业技术资格 2026",
                category="医药",
                organizer="国家卫健委人才交流中心",
                registration_start=_days_from_now(50),
                registration_end=_days_from_now(80),
                exam_date=_days_from_now(120),
                source_url="http://www.21wecan.com/notice/2026-med",
                status=ExamStatus.open,
            ),
            Exam(
                name="临床执业医师 2026",
                category="医药",
                organizer="国家医学考试中心",
                registration_start=_days_from_now(30),
                registration_end=_days_from_now(60),
                exam_date=_days_from_now(140),
                source_url="https://www.nmec.org.cn/notice/2026-doc",
                status=ExamStatus.open,
            ),
            # 教育
            Exam(
                name="中小学教师资格考试（笔试）2026 上半年",
                category="教育",
                organizer="教育部",
                registration_start=_days_from_now(10),
                registration_end=_days_from_now(40),
                exam_date=_days_from_now(80),
                source_url="https://www.neea.edu.cn/notice/2026-js-zs",
                status=ExamStatus.open,
            ),
            Exam(
                name="全国硕士研究生招生考试 2026",
                category="教育",
                organizer="教育部",
                registration_start=_days_from_now(30),
                registration_end=_days_from_now(60),
                exam_date=_days_from_now(100),
                source_url="https://yz.chsi.com.cn/notice/2026-yz",
                status=ExamStatus.open,
            ),
            Exam(
                name="全国大学英语四级 2026 上半年",
                category="教育",
                organizer="教育部",
                registration_start=_days_from_now(30),
                registration_end=_days_from_now(50),
                exam_date=_days_from_now(120),
                source_url="https://www.neea.edu.cn/notice/2026-cet4",
                status=ExamStatus.open,
            ),
            # 法律
            Exam(
                name="国家统一法律职业资格考试（客观题）2026",
                category="法律",
                organizer="司法部",
                registration_start=_days_from_now(40),
                registration_end=_days_from_now(70),
                exam_date=_days_from_now(130),
                source_url="https://www.moj.gov.cn/notice/2026-fk",
                status=ExamStatus.open,
            ),
            # 翻译
            Exam(
                name="CATTI 笔译三级 2026 上半年",
                category="翻译",
                organizer="中国外文局 / 人社部",
                registration_start=_days_from_now(20),
                registration_end=_days_from_now(60),
                exam_date=_days_from_now(130),
                source_url="http://www.tac-online.org.cn/notice/2026-catti",
                status=ExamStatus.open,
            ),
            # 公务员
            Exam(
                name="国家公务员考试（国考）2026",
                category="公务员",
                organizer="中共中央组织部 / 人社部 / 国家公务员局",
                registration_start=_days_from_now(50),
                registration_end=_days_from_now(80),
                exam_date=_days_from_now(140),
                source_url="http://www.scs.gov.cn/notice/2026-gk",
                status=ExamStatus.open,
            ),
            # 其他
            Exam(
                name="社会工作者职业资格 2026",
                category="其他",
                organizer="人社部 / 民政部",
                registration_start=_days_from_now(15),
                registration_end=_days_from_now(45),
                exam_date=_days_from_now(110),
                source_url="https://www.cpta.com.cn/notice/2026-soc",
                status=ExamStatus.open,
            ),
            Exam(
                name="银行业专业人员职业资格 2026 上半年",
                category="其他",
                organizer="中国银行业协会",
                registration_start=_days_from_now(20),
                registration_end=_days_from_now(50),
                exam_date=_days_from_now(110),
                source_url="https://www.cpta.com.cn/notice/2026-bank",
                status=ExamStatus.open,
            ),
            Exam(
                name="机动车检测维修 2026 上半年",
                category="其他",
                organizer="交通运输部",
                registration_start=_days_from_now(15),
                registration_end=_days_from_now(45),
                exam_date=_days_from_now(105),
                source_url="https://www.cpta.com.cn/notice/2026-jdc",
                status=ExamStatus.open,
            ),
            Exam(
                name="文物保护工程从业资格 2026",
                category="其他",
                organizer="国家文物局",
                registration_start=_days_from_now(20),
                registration_end=_days_from_now(50),
                exam_date=_days_from_now(120),
                source_url="https://www.cpta.com.cn/notice/2026-wwb",
                status=ExamStatus.open,
            ),
            Exam(
                name="房地产经纪人协理 2026 上半年",
                category="其他",
                organizer="住建部 / 中房学",
                registration_start=_days_from_now(20),
                registration_end=_days_from_now(50),
                exam_date=_days_from_now(110),
                source_url="https://www.cpta.com.cn/notice/2026-house",
                status=ExamStatus.open,
            ),
        ]
        session.add_all(exams)
        session.commit()
        log.info("exams_seeded", count=len(exams))

        # 5 条 demo 订阅
        demo_subs = [
            Subscription(
                id=str(uuid.uuid4()),
                exam_id=exams[0].id,  # 软考
                email="demo1@example.com",
                phone="13800138001",
                reminder_level="standard",
                channels=["email", "sms"],
                status=SubscriptionStatus.active,
                confirm_token=sign(
                    {"sub_id": "demo1", "action": "confirm"}, ttl_days=30
                ),
                cancel_token=sign(
                    {"sub_id": "demo1", "action": "cancel"}, ttl_days=30
                ),
            ),
            Subscription(
                id=str(uuid.uuid4()),
                exam_id=exams[3].id,  # 一建
                email="demo2@example.com",
                phone="13800138002",
                reminder_level="aggressive",
                channels=["email"],
                status=SubscriptionStatus.active,
                confirm_token=sign(
                    {"sub_id": "demo2", "action": "confirm"}, ttl_days=30
                ),
                cancel_token=sign(
                    {"sub_id": "demo2", "action": "cancel"}, ttl_days=30
                ),
            ),
            Subscription(
                id=str(uuid.uuid4()),
                exam_id=exams[8].id,  # 初级会计
                email="demo3@example.com",
                phone="13800138003",
                reminder_level="conservative",
                channels=["sms"],
                status=SubscriptionStatus.pending,
                confirm_token=sign(
                    {"sub_id": "demo3", "action": "confirm"}, ttl_days=30
                ),
                cancel_token=sign(
                    {"sub_id": "demo3", "action": "cancel"}, ttl_days=30
                ),
            ),
            Subscription(
                id=str(uuid.uuid4()),
                exam_id=exams[22].id,  # 教师资格
                email="demo4@example.com",
                phone="13800138004",
                reminder_level="standard",
                channels=["email", "sms"],
                status=SubscriptionStatus.active,
                confirm_token=sign(
                    {"sub_id": "demo4", "action": "confirm"}, ttl_days=30
                ),
                cancel_token=sign(
                    {"sub_id": "demo4", "action": "cancel"}, ttl_days=30
                ),
            ),
            Subscription(
                id=str(uuid.uuid4()),
                exam_id=exams[27].id,  # 国考
                email="demo5@example.com",
                phone="13800138005",
                reminder_level="aggressive",
                channels=["email"],
                status=SubscriptionStatus.cancelled,
                confirm_token=sign(
                    {"sub_id": "demo5", "action": "confirm"}, ttl_days=30
                ),
                cancel_token=sign(
                    {"sub_id": "demo5", "action": "cancel"}, ttl_days=30
                ),
                cancelled_at=datetime.utcnow(),
            ),
        ]
        session.add_all(demo_subs)
        session.commit()
        log.info("subscriptions_seeded", count=len(demo_subs))


if __name__ == "__main__":
    seed()
    print("seed done")
