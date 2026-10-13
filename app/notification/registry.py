"""通道注册表。

启动时注册所有可用通道，运行时按 name 获取。
测试中可注入 Mock 通道。
"""
from __future__ import annotations

from app.notification.base import Channel

_registry: dict[str, Channel] = {}


def register(channel: Channel) -> None:
    """注册一个通道。已存在的 name 会被覆盖。"""
    _registry[channel.name] = channel


def get(name: str) -> Channel:
    """按 name 取得通道。未注册则 KeyError。"""
    return _registry[name]


def get_all() -> dict[str, Channel]:
    """返回所有已注册通道的副本。"""
    return dict(_registry)


def reset_for_test() -> None:
    """测试钩子：清空注册表。"""
    _registry.clear()
