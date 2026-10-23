"""
pytest 全局配置与夹具
"""
import os
import sys
from pathlib import Path

# 将 backend 目录加入 sys.path，使测试可直接 import 项目模块
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from database import Base
from models import User
import auth as auth_module


@pytest.fixture(scope="function")
def db_session(tmp_path):
    """每个测试函数独立的内存 SQLite 数据库会话"""
    db_path = tmp_path / "test.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def client(db_session, monkeypatch):
    """带认证的 FastAPI TestClient，使用测试数据库"""
    # 替换 get_db 依赖，使其返回测试会话
    from database import get_db
    import main as main_module

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    # 确保有默认管理员
    auth_module.create_default_admin(db_session)

    main_module.app.dependency_overrides[get_db] = _override_get_db
    with TestClient(main_module.app) as c:
        yield c
    main_module.app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def admin_token(client):
    """获取管理员 JWT token"""
    resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "admin123"},
    )
    assert resp.status_code == 200, f"登录失败: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="function")
def auth_headers(admin_token):
    """带管理员 token 的请求头"""
    return {"Authorization": f"Bearer {admin_token}"}
