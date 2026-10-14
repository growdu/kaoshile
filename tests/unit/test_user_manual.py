"""用户手册完整性测试。

目的：保证 `docs/user_manual.md` 中至少出现一次所有 API 端点。
新增 / 修改端点后，CI 会立刻提示需要同步手册（避免代码与文档漂移）。

白名单：
- `/healthz` / `/readyz`：健康检查（不进手册正文，仅在 §3.2 引用）
"""
from __future__ import annotations

import re
from pathlib import Path


DOC_PATH = Path(__file__).resolve().parents[2] / "docs" / "user_manual.md"


def _routes() -> list[str]:
    """从 app/api/ 抓出所有 @router.method 后的 path。"""
    import re as _re
    from pathlib import Path as _Path

    paths: list[str] = []
    rx = _re.compile(r'@router\.(get|post|put|patch|delete)\(\s*"([^"]+)"')
    for py in _Path("app/api").glob("*.py"):
        for match in rx.finditer(py.read_text(encoding="utf-8")):
            paths.append(match.group(2))
    return sorted(set(paths))


def test_all_api_paths_documented():
    """每个 API path 至少在用户手册中出现一次（用 `path {` 或 path 本身）。"""
    doc = DOC_PATH.read_text(encoding="utf-8")
    missing: list[str] = []
    for path in _routes():
        # 路径里 `{exam_id}` 这类参数用通配模式匹配
        pattern = re.escape(path).replace(r"\{exam_id\}", r"\{[^}]+\}")
        if not re.search(pattern, doc):
            missing.append(path)
    assert not missing, f"用户手册未覆盖以下 API path：{missing}"


def test_manual_has_user_and_admin_sections():
    """用户手册必须包含普通用户 + 管理员两大章节。"""
    doc = DOC_PATH.read_text(encoding="utf-8")
    assert "普通用户" in doc, "缺少「普通用户手册」章节"
    assert "管理员手册" in doc, "缺少「管理员手册」章节"


def test_manual_documents_error_envelope():
    """信封（ok/data/error.code）必须在手册中说明。"""
    doc = DOC_PATH.read_text(encoding="utf-8")
    assert '"ok": true' in doc or "'ok': true" in doc
    assert '"code"' in doc or "'code'" in doc, "手册未提及 error.code 字段"