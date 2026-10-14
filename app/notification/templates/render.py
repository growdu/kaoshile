"""通知模板：邮件 / 短信文案占位符替换。

约定：
- 占位符用 `{name}` 形式，未提供的占位符原样保留；
- 默认模板硬编码于本模块；DB 中存在同名模板时优先用 DB；
- 所有模板必须包含退订链接（合规）；
- 模板提供纯函数渲染，不做副作用。
"""
from __future__ import annotations

from datetime import datetime
from typing import Mapping, Optional

from app.repository.orm import NodeType

NODE_LABEL = {
    NodeType.registration_start.value: "报名开始",
    NodeType.registration_end.value: "报名截止",
    NodeType.payment_end.value: "缴费截止",
    NodeType.admission_start.value: "准考证打印开始",
    NodeType.exam_day.value: "考试日",
}

EMAIL_TEMPLATE = """\
尊敬的订阅用户：

您订阅的【{exam_name}】即将进入【{node_label}】阶段。

📅 时间：{when}
🏛 主办：{organizer}
🔗 官方公告：{official_url}

——
取消订阅：{unsubscribe_url}

本邮件由 kaoshile 考试通知服务自动发送。
"""

SMS_TEMPLATE = "【kaoshile】您订阅的{exam_name}将于{when}迎来【{node_label}】，官方：{official_url}，退订：{unsubscribe_url}"


CONFIRM_EMAIL_TEMPLATE = """\
感谢订阅【{exam_name}】！

请在 30 天内点击以下链接完成确认，订阅才会生效：
✅ 确认订阅：{confirm_url}

——
取消订阅：{unsubscribe_url}
"""

CONFIRM_SMS_TEMPLATE = (
    "【kaoshile】感谢订阅{exam_name}。请确认：{confirm_url}（30 天内有效）"
)


def _fmt_when(value: datetime) -> str:
    """把 datetime 格式化为可读字符串（Asia/Shanghai，%Y-%m-%d %H:%M）。"""
    from app.infra.time import to_shanghai

    return to_shanghai(value).strftime("%Y-%m-%d %H:%M %Z")


def render(template: str, ctx: Mapping[str, object]) -> str:
    """占位符替换。

    缺失的 key 保留原 `{name}`；datetime 自动通过 _fmt_when 处理。
    """
    rendered = template
    for k, v in ctx.items():
        if isinstance(v, datetime):
            v_str = _fmt_when(v)
        else:
            v_str = str(v)
        rendered = rendered.replace("{" + k + "}", v_str)
    return rendered


def render_reminder_email(
    *,
    exam_name: str,
    organizer: str,
    node_type: str,
    when: datetime,
    official_url: str,
    unsubscribe_url: str,
) -> str:
    return render(
        EMAIL_TEMPLATE,
        {
            "exam_name": exam_name,
            "organizer": organizer,
            "node_label": NODE_LABEL.get(node_type, node_type),
            "when": when,
            "official_url": official_url,
            "unsubscribe_url": unsubscribe_url,
        },
    )


def render_reminder_sms(
    *,
    exam_name: str,
    node_type: str,
    when: datetime,
    official_url: str,
    unsubscribe_url: str,
) -> str:
    return render(
        SMS_TEMPLATE,
        {
            "exam_name": exam_name,
            "node_label": NODE_LABEL.get(node_type, node_type),
            "when": when,
            "official_url": official_url,
            "unsubscribe_url": unsubscribe_url,
        },
    )


def render_confirm_email(*, exam_name: str, confirm_url: str, unsubscribe_url: str) -> str:
    return render(
        CONFIRM_EMAIL_TEMPLATE,
        {
            "exam_name": exam_name,
            "confirm_url": confirm_url,
            "unsubscribe_url": unsubscribe_url,
        },
    )


def render_confirm_sms(*, exam_name: str, confirm_url: str) -> str:
    return render(
        CONFIRM_SMS_TEMPLATE,
        {"exam_name": exam_name, "confirm_url": confirm_url},
    )
