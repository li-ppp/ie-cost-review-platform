"""
报告生成器单元测试
"""
import sys
from pathlib import Path

import pytest

from services.report_generator import (
    fmt_num,
    classify_items,
    build_item_line,
    match_engineering_type,
    generate_report_number,
    replace_paragraph_text,
)

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))


class TestFmtNum:
    def test_integer(self):
        assert fmt_num(100) == "100.00"

    def test_float(self):
        assert fmt_num(3.14) == "3.14"

    def test_none(self):
        assert fmt_num(None) == "0.00"

    def test_zero(self):
        assert fmt_num(0) == "0.00"

    def test_negative(self):
        assert fmt_num(-50.25) == "-50.25"

    def test_custom_decimals(self):
        assert fmt_num(3.14159, decimals=3) == "3.142"


class TestClassifyItems:
    def test_mixed_adjustment(self):
        items = [
            {"item_name": "A", "adjustment": -100},
            {"item_name": "B", "adjustment": 200},
            {"item_name": "C", "adjustment": 0},
            {"item_name": "D", "adjustment": -50},
        ]
        reductions, increases = classify_items(items)
        # 审减（负数）
        assert len(reductions) == 2
        # 审增（正数）
        assert len(increases) == 1

    def test_all_reductions(self):
        items = [
            {"item_name": "A", "adjustment": -100},
            {"item_name": "B", "adjustment": -50},
        ]
        reductions, increases = classify_items(items)
        assert len(reductions) == 2
        assert len(increases) == 0

    def test_empty_list(self):
        reductions, increases = classify_items([])
        assert reductions == []
        assert increases == []


class TestMatchEngineeringType:
    def test_road(self):
        # 需以冒号结尾才会被识别为工程类型标题
        assert match_engineering_type("道路工程：") == "道路工程"

    def test_drainage(self):
        assert match_engineering_type("排水工程:") == "排水工程"

    def test_alias(self):
        assert match_engineering_type("桥梁工程：") == "桥涵工程"

    def test_no_colon_returns_none(self):
        # 无冒号结尾时返回 None
        assert match_engineering_type("道路工程") is None

    def test_no_match(self):
        assert match_engineering_type("未知工程：") is None


class TestGenerateReportNumber:
    def test_format(self):
        num = generate_report_number(project_id=1)
        # 格式应为 PJ-YYYY-XXXX 类似格式
        assert "1" in num or num.startswith("PJ")

    def test_year_included(self):
        import datetime
        year = datetime.datetime.now().year
        num = generate_report_number(project_id=42)
        assert str(year) in num


class TestBuildItemLine:
    def test_basic_line(self):
        item = {
            "name": "测试项目",
            "unit": "m3",
            "submitted_qty": 100,
            "submitted_total": 1000,
            "audited_qty": 90,
            "audited_total": 900,
            "adjustment": -100,
        }
        line = build_item_line(item)
        assert isinstance(line, str)
        assert "测试项目" in line
        assert "送审工程量" in line
        assert "审减" in line

    def test_increase_item(self):
        item = {
            "name": "审增项",
            "unit": "m",
            "submitted_qty": 100,
            "submitted_total": 1000,
            "audited_qty": 110,
            "audited_total": 1200,
            "adjustment": 200,
        }
        line = build_item_line(item)
        assert "审增" in line
