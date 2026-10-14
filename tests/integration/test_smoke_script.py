"""scripts/smoke.py 端到端冒烟脚本的集成测试。

策略：直接复用 scripts/smoke.py 暴露的 step_* 函数，在每个 step 之后断言
Step.ok 为 True。这样 CI 既覆盖脚本逻辑又不依赖 subprocess。

对无前置依赖的 step（health / list_exams / register_login）单独测；
其余依赖前置（订阅、用户等）的步骤统一通过 test_run_all_full_chain 端到端覆盖。
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture
def smoke_ctx():
    """每个测试独立构建 app + session factory，避免 autouse 清零 db_mod 的影响。

    启动约 50ms/次，可接受。
    """
    import sys

    _ROOT = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)
    from scripts.smoke import _make_app_and_session_factory

    return _make_app_and_session_factory()


def test_step_health(smoke_ctx):
    client, _, _ = smoke_ctx
    from scripts.smoke import step_health

    s = step_health(client)
    assert s.ok, s.detail


def test_step_list_exams(smoke_ctx):
    client, _, _ = smoke_ctx
    from scripts.smoke import step_list_exams

    s = step_list_exams(client)
    assert s.ok, s.detail


def test_step_register_login(smoke_ctx):
    client, _, _ = smoke_ctx
    from scripts.smoke import step_register_login

    s = step_register_login(client)
    assert s.ok, s.detail


def test_run_all_full_chain():
    """完整链路一次性跑通：覆盖 step_subscribe_confirm / trigger_node /
    cancel / change_email / dashboard 五个有依赖的步骤。"""
    import sys

    _ROOT = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    if _ROOT not in sys.path:
        sys.path.insert(0, _ROOT)
    from scripts.smoke import run_all

    steps = run_all(fail_fast=False)
    failed = [s for s in steps if not s.ok]
    assert not failed, f"失败的步骤：{[(s.name, s.detail) for s in failed]}"
    assert len(steps) == 8