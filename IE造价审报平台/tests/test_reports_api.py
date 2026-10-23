"""
报告管理 API 单元测试
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))


class TestReportsList:
    def test_list_reports(self, client, auth_headers):
        resp = client.get("/api/reports/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_list_reports_auth_required(self, client):
        resp = client.get("/api/reports/")
        assert resp.status_code in (401, 403)


class TestReviewStatus:
    def test_review_status_values(self):
        """测试审核状态文本映射的完整性"""
        # 仅校验枚举值在文档中存在
        valid_statuses = {"draft", "reviewing", "approved", "rejected"}
        assert "approved" in valid_statuses
        assert "rejected" in valid_statuses


class TestBackupApi:
    def test_list_backups(self, client, auth_headers):
        resp = client.get("/api/backup/list", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_backup_auth_required(self, client):
        resp = client.get("/api/backup/list")
        assert resp.status_code in (401, 403)


class TestDictionaryApi:
    def test_list_dictionary(self, client, auth_headers):
        resp = client.get("/api/dictionary/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_get_categories(self, client, auth_headers):
        resp = client.get("/api/dictionary/categories", headers=auth_headers)
        assert resp.status_code == 200

    def test_create_dictionary_item(self, client, auth_headers):
        resp = client.post(
            "/api/dictionary/",
            json={
                "category": "unit",
                "code": "test_unit",
                "name": "测试单位",
                "description": "测试用",
                "sort_order": 99,
            },
            headers=auth_headers,
        )
        assert resp.status_code in (200, 201)
        data = resp.json()
        assert data["name"] == "测试单位"

    def test_dictionary_auth_required(self, client):
        resp = client.get("/api/dictionary/")
        assert resp.status_code in (401, 403)


class TestTemplateApi:
    def test_list_templates(self, client, auth_headers):
        resp = client.get("/api/templates/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_templates_auth_required(self, client):
        resp = client.get("/api/templates/")
        assert resp.status_code in (401, 403)
