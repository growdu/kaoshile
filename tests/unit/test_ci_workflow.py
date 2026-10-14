"""CI workflow 完整性测试。

目的：
- 保证 `.github/workflows/ci.yml` 存在且可解析（YAML 合法）；
- 必需的 job 都在（lint / test / smoke），缺失就 fail；
- 触发的 branch 至少包含 main。
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WF_PATH = Path(__file__).resolve().parents[2] / ".github" / "workflows" / "ci.yml"


def test_workflow_file_exists():
    assert WF_PATH.exists(), f"缺少 CI workflow 文件：{WF_PATH}"


def test_workflow_yaml_parseable():
    data = yaml.safe_load(WF_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict), "CI workflow 顶层应为 dict"
    assert "jobs" in data, "CI workflow 必须包含 jobs"


def test_workflow_required_jobs_present():
    data = yaml.safe_load(WF_PATH.read_text(encoding="utf-8"))
    jobs = data.get("jobs", {})
    required = {"lint", "test", "smoke"}
    missing = required - set(jobs.keys())
    assert not missing, f"CI 缺少必需 job：{missing}"


def test_workflow_triggers_main():
    data = yaml.safe_load(WF_PATH.read_text(encoding="utf-8"))
    on = data.get(True) or data.get("on")  # yaml 1.1 把 'on' 当 bool，要兼容
    triggers = on if isinstance(on, dict) else {}
    # push.branches / pull_request.branches 都要包含 main
    push_branches = (
        triggers.get("push", {}).get("branches", [])
        if isinstance(triggers.get("push"), dict)
        else []
    )
    pr_branches = (
        triggers.get("pull_request", {}).get("branches", [])
        if isinstance(triggers.get("pull_request"), dict)
        else []
    )
    assert "main" in push_branches, "CI push 触发必须包含 main"
    assert "main" in pr_branches, "CI pull_request 触发必须包含 main"


def test_test_job_uses_pytest_with_coverage():
    data = yaml.safe_load(WF_PATH.read_text(encoding="utf-8"))
    test_job = data["jobs"]["test"]
    steps = test_job.get("steps", [])
    # 找运行 pytest 的命令
    found = False
    for step in steps:
        run = step.get("run", "")
        if "pytest" in run and ("cov" in run or "coverage" in run):
            found = True
            break
    assert found, "test job 必须用 pytest + coverage"


def test_smoke_job_invokes_scripts_smoke():
    data = yaml.safe_load(WF_PATH.read_text(encoding="utf-8"))
    smoke_job = data["jobs"]["smoke"]
    steps = smoke_job.get("steps", [])
    found = any(
        "scripts/smoke.py" in step.get("run", "") for step in steps
    )
    assert found, "smoke job 必须执行 scripts/smoke.py"