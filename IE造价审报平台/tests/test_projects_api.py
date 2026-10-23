"""
项目管理 API 单元测试
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))


class TestProjectCRUD:
    def test_create_project(self, client, auth_headers):
        resp = client.post(
            "/api/projects/",
            json={"name": "测试项目A", "client_name": "建设单位A", "project_type": "道路工程"},
            headers=auth_headers,
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["name"] == "测试项目A"
        assert data["client_name"] == "建设单位A"
        assert data["id"] > 0

    def test_create_project_without_name_fails(self, client, auth_headers):
        resp = client.post(
            "/api/projects/",
            json={"name": "", "client_name": "x", "project_type": "道路工程"},
            headers=auth_headers,
        )
        # name 为空应失败（422 验证错误）
        assert resp.status_code >= 400

    def test_list_projects(self, client, auth_headers):
        # 先创建一个
        client.post(
            "/api/projects/",
            json={"name": "列表测试", "client_name": "客户", "project_type": "排水工程"},
            headers=auth_headers,
        )
        resp = client.get("/api/projects/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_project_by_id(self, client, auth_headers):
        create = client.post(
            "/api/projects/",
            json={"name": "查询测试", "client_name": "客户", "project_type": "照明工程"},
            headers=auth_headers,
        )
        pid = create.json()["id"]
        resp = client.get(f"/api/projects/{pid}", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == pid

    def test_delete_project(self, client, auth_headers):
        create = client.post(
            "/api/projects/",
            json={"name": "待删除", "client_name": "", "project_type": "其他"},
            headers=auth_headers,
        )
        pid = create.json()["id"]
        resp = client.delete(f"/api/projects/{pid}", headers=auth_headers)
        assert resp.status_code in (200, 204)
        # 删除后再查询应 404
        resp2 = client.get(f"/api/projects/{pid}", headers=auth_headers)
        assert resp2.status_code == 404


class TestAuthRequired:
    def test_no_token_returns_401(self, client):
        resp = client.get("/api/projects/")
        assert resp.status_code in (401, 403)

    def test_invalid_token_returns_401(self, client):
        resp = client.get(
            "/api/projects/",
            headers={"Authorization": "Bearer invalid.token.here"},
        )
        assert resp.status_code == 401
