"""Smoke 测试：确保 app 包可被正确导入。

这是 M0.0 的最小可验证点——任何里程碑的代码加入 app/ 后，都必须仍然通过这个测试。
"""
import app


def test_app_package_importable():
    """顶层包能 import。"""
    assert app is not None


def test_app_version_set():
    """版本号已声明。"""
    assert app.__version__ == "0.1.0"


def test_app_sub_packages_importable():
    """所有子包都能 import（空 __init__.py 不应报错）。"""
    from app import api, usecase, domain, repository, notification, scheduler, infra, data_sources  # noqa: F401

    assert api.__name__ == "app.api"
    assert usecase.__name__ == "app.usecase"
    assert domain.__name__ == "app.domain"
    assert repository.__name__ == "app.repository"
    assert notification.__name__ == "app.notification"
    assert scheduler.__name__ == "app.scheduler"
    assert infra.__name__ == "app.infra"
    assert data_sources.__name__ == "app.data_sources"
