"""CI / GitHub 配置完整性测试。

目的：
- 保证 `.github/workflows/ci.yml` 存在且可解析（YAML 合法）；
- 必需的 job 都在（lint / test / smoke），缺失就 fail；
- 触发的 branch 至少包含 main；
- v7.1 起：依赖自动更新 / 发版 workflow / PR / Issue 模板 / CODEOWNERS / CHANGELOG 都到位。
"""
from __future__ import annotations

from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[2]
WF_PATH = ROOT / ".github" / "workflows" / "ci.yml"
RELEASE_PATH = ROOT / ".github" / "workflows" / "release.yml"
DEPENDABOT_PATH = ROOT / ".github" / "dependabot.yml"
CODEOWNERS_PATH = ROOT / ".github" / "CODEOWNERS"
PR_TEMPLATE_PATH = ROOT / ".github" / "PULL_REQUEST_TEMPLATE.md"
ISSUE_DIR = ROOT / ".github" / "ISSUE_TEMPLATE"
CHANGELOG_PATH = ROOT / "CHANGELOG.md"


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


# ---------- v7.1 新增：发版 / 依赖自动更新 / 模板 ----------


def test_release_workflow_exists_and_parseable():
    assert RELEASE_PATH.exists(), "缺少 release workflow"
    data = yaml.safe_load(RELEASE_PATH.read_text(encoding="utf-8"))
    assert "jobs" in data, "release.yml 必须包含 jobs"


def test_release_workflow_triggers_on_tag():
    data = yaml.safe_load(RELEASE_PATH.read_text(encoding="utf-8"))
    on = data.get(True) or data.get("on")
    push = on.get("push", {}) if isinstance(on, dict) else {}
    tags = push.get("tags", []) if isinstance(push, dict) else []
    assert any(t.startswith("v") for t in tags), "release 必须按 v* tag 触发"


def test_release_workflow_publishes_ghcr_image():
    """release job 应构建并推送镜像到 ghcr.io。"""
    data = yaml.safe_load(RELEASE_PATH.read_text(encoding="utf-8"))
    blob = RELEASE_PATH.read_text(encoding="utf-8")
    assert "ghcr.io" in blob, "release workflow 必须推送镜像到 ghcr.io"
    assert "docker/build-push-action" in blob, "release workflow 必须用 build-push-action"


def test_release_workflow_creates_release():
    data = yaml.safe_load(RELEASE_PATH.read_text(encoding="utf-8"))
    blob = RELEASE_PATH.read_text(encoding="utf-8")
    assert "action-gh-release" in blob, "release workflow 必须创建 GitHub Release"


def test_dependabot_config_exists_and_parseable():
    assert DEPENDABOT_PATH.exists(), "缺少 dependabot.yml"
    data = yaml.safe_load(DEPENDABOT_PATH.read_text(encoding="utf-8"))
    ecosystems = [
        u["package-ecosystem"]
        for u in data.get("updates", [])
        if isinstance(u, dict)
    ]
    assert "pip" in ecosystems, "Dependabot 必须跟踪 pip 依赖"
    assert "github-actions" in ecosystems, "Dependabot 必须跟踪 GitHub Actions"


def test_codeowners_exists_and_has_default_owner():
    assert CODEOWNERS_PATH.exists(), "缺少 CODEOWNERS"
    blob = CODEOWNERS_PATH.read_text(encoding="utf-8")
    assert "*" in blob, "CODEOWNERS 必须有全局默认 owner"


def test_pr_template_exists():
    assert PR_TEMPLATE_PATH.exists(), "缺少 PULL_REQUEST_TEMPLATE.md"


def test_issue_templates_exist():
    assert ISSUE_DIR.is_dir(), "缺少 .github/ISSUE_TEMPLATE 目录"
    names = {p.name for p in ISSUE_DIR.iterdir() if p.is_file()}
    assert "bug.md" in names, "缺少 bug Issue 模板"
    assert "feature.md" in names, "缺少 feature Issue 模板"


def test_changelog_exists_and_has_unreleased_section():
    """CHANGELOG 必须存在 + 有 [Unreleased] 段落。"""
    assert CHANGELOG_PATH.exists(), "缺少 CHANGELOG.md"
    blob = CHANGELOG_PATH.read_text(encoding="utf-8")
    assert "## [Unreleased]" in blob, "CHANGELOG.md 必须含 [Unreleased] 段落"
    # 至少有一个历史版本
    import re as _re

    versions = _re.findall(r"## \[v?\d+\.\d+\.\d+\]", blob)
    assert len(versions) >= 1, "CHANGELOG.md 必须记录至少一个历史版本"