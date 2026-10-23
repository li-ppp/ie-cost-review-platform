"""
Excel文件解析服务
"""

import openpyxl
from openpyxl.utils import get_column_letter
import re
import os
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


# 列名字段固定 9 项（与 ExcelData 模型对应）
FIELD_KEYS = [
    "name", "unit",
    "submitted_qty", "submitted_price", "submitted_total",
    "audited_qty", "audited_price", "audited_total",
    "adjustment",
]

# adjustment 列别名（不同 Excel 命名差异）
_ADJUSTMENT_ALIASES = ("审增金额", "审减金额", "调整金额", "审核增减", "偏差", "增减金额", "审增减")

# 组表头关键词（按优先级匹配）
_GROUP_KEYWORDS: List[Tuple[str, str]] = [
    ("送审", "送审"),
    ("审结", "审结"),
    ("审定", "审定"),
    ("审计结果", "审计结果"),
    ("审核增减", "审核增减"),
    ("调整", "调整"),
]


# 工程类型映射
SHEET_TYPE_MAP = {
    "审表-09 分部分项工程和单价措施项目清单计价对比表（含工程~": "道路工程",
    "审表-09 分部分项工程和单价措施项目清单计价对比表（含工~1": "排水工程",
    "审表-09 分部分项工程和单价措施项目清单计价对比表（含工~2": "交安工程",
    "审表-09 分部分项工程和单价措施项目清单计价对比表（含工~3": "桥涵工程",
    "审表-09 分部分项工程和单价措施项目清单计价对比表（含工~4": "照明工程",
    "审表-09 分部分项工程和单价措施项目清单计价对比表（含工~5": "电力工程",
    "审表-09 分部分项工程和单价措施项目清单计价对比表（含工~6": "通信工程",
    # 简单sheet名称映射
    "道路工程": "道路工程",
    "排水工程": "排水工程",
    "交安工程": "交安工程",
    "交通安全": "交安工程",
    "桥涵工程": "桥涵工程",
    "桥梁工程": "桥涵工程",
    "照明工程": "照明工程",
    "电力工程": "电力工程",
    "通信工程": "通信工程",
}

# 支持的文件扩展名（openpyxl仅支持.xlsx）
SUPPORTED_EXTENSIONS = ('.xlsx',)


def safe_float(val) -> Optional[float]:
    """安全地将值转换为浮点数"""
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _read_header_area(
    ws,
    header_row: int,
    data_start_row: Optional[int] = None,
) -> Tuple[Dict[int, Dict[int, str]], List[int]]:
    """读取表头区域，返回 (header_area, sorted_rows)。

    Args:
        ws: 工作表
        header_row: 表头起始行
        data_start_row: 数据起始行；若提供则只读到 data_start_row-1（避免读入数据行），
                       否则默认读 4 行（向后兼容）。
    """
    header_area: Dict[int, Dict[int, str]] = {}
    if data_start_row is not None:
        max_header_row = data_start_row - 1
    else:
        max_header_row = header_row + 3
    for row in range(header_row, max_header_row + 1):
        if row > ws.max_row:
            break
        for col_idx in range(1, ws.max_column + 1):
            val = ws.cell(row, col_idx).value
            if val:
                if row not in header_area:
                    header_area[row] = {}
                header_area[row][col_idx] = str(val).strip()
    return header_area, sorted(header_area.keys())


def _scan_group_headers(
    header_area: Dict[int, Dict[int, str]],
    sorted_rows: List[int],
    max_column: int,
) -> List[Tuple[str, int, int]]:
    """
    扫描最顶层有内容的行，识别组表头（送审工程/审结工程/审计结果 等）。
    组表头跨多列时，其值仅出现在起始列。
    返回 [(group_name, start_col, end_col), ...]，end_col 为下一个组起点-1，末组为 max_column。

    单级表头（仅 1 行表头）时返回空列表：此时每个列名都是独立叶子，
    不存在跨列组表头，强行识别会把"送审数量"/"调整金额"等叶子误判为组表头。
    """
    if not sorted_rows:
        return []
    if len(sorted_rows) <= 1:
        return []

    top_row = sorted_rows[0]
    top_cells = header_area.get(top_row, {})

    # 收集该行所有 (col, value)
    groups: List[Tuple[str, int]] = []
    for col_idx in sorted(top_cells.keys()):
        val = top_cells[col_idx]
        for kw, name in _GROUP_KEYWORDS:
            if kw in val:
                groups.append((name, col_idx))
                break

    if not groups:
        return []

    groups.sort(key=lambda x: x[1])
    result: List[Tuple[str, int, int]] = []
    for i, (name, start) in enumerate(groups):
        end = groups[i + 1][1] - 1 if i + 1 < len(groups) else max_column
        result.append((name, start, end))
    return result


def _scan_subgroup_cells(
    header_area: Dict[int, Dict[int, str]],
    sorted_rows: List[int],
    top_row: Optional[int],
) -> set:
    """识别子组标题单元格：中间行单元格 (r, c) 是子组标题，
    当且仅当最底行 (last_row, c) 也有值（说明 (r, c) 是组标题，下方有更细分的叶子）。

    如果最底行同列为空，则中间行单元格本身就是叶子（如"工程量"列在 R4 有值、R5 为空，
    说明工程量无需再细分单价/合价，R4 的"工程量"就是叶子）。

    通用结构推断，不依赖任何关键词（如"审核增减"）。
    """
    sub_cells: set = set()
    if not sorted_rows:
        return sub_cells
    last_row = sorted_rows[-1]
    last_row_cells = header_area.get(last_row, {})
    for i, row in enumerate(sorted_rows):
        if top_row is not None and row == top_row:
            continue  # 顶行：组表头
        if row == last_row:
            continue  # 最底行：真正的叶子
        for col, val in header_area.get(row, {}).items():
            # 关键：只有当最底行同列也有值时，中间行单元格才是子组标题
            # 否则中间行单元格本身就是叶子（如 F4='工程量'，F5 为空）
            if col in last_row_cells:
                sub_cells.add((row, col))
    return sub_cells


def _detect_adjustment_column(
    header_area: Dict[int, Dict[int, str]],
    sorted_rows: List[int],
    groups: List[Tuple[str, int, int]],
    max_column: int,
) -> Optional[int]:
    """
    两遍扫描识别 adjustment 列，修复两类 bug：
    1. "审增金额被通用金额抢先"——通过 Pass 1/2 优先级解决
    2. "审核增减子组标题被当作叶子"——通过识别子组标题单元格并从叶子文本中排除

    优先级（从高到低）：
    1. 审计结果/审核增减/调整 组内，叶子含特定别名（审增金额/审减金额/调整金额等）
       —— 子组标题"审核增减"被排除，避免误命中
    2. 审计结果/审核增减/调整 组内，叶子含通用"金额"
    3. 无组表头时，全局叶子含特定别名
    4. 旧模板兼容：full_text 同时含"审核增减"和"金额"
    """
    if not sorted_rows:
        return None

    top_row = sorted_rows[0] if groups else None
    adjustment_groups = ("审计结果", "审核增减", "调整")

    # 通用结构推断：非顶行非最底行的单元格都是子组标题，从叶子文本中排除。
    # 不依赖关键词，任何中间层标题（"审核增减"/"金额(元)"/"差异明细"等）都能正确排除。
    sub_cells = _scan_subgroup_cells(header_area, sorted_rows, top_row)

    def col_group(col_idx: int) -> Optional[str]:
        for name, start, end in groups:
            if start <= col_idx <= end:
                return name
        return None

    def leaf_text_of(col_idx: int, exclude_top: bool = False, exclude_sub: bool = True) -> str:
        """拼接本列叶子表头文本；
        exclude_top=True 时跳过组表头行避免组名污染；
        exclude_sub=True 时跳过子组标题单元格避免子组标题（如"审核增减"）污染叶子文本。
        """
        leaves: List[str] = []
        for row in sorted_rows:
            if exclude_top and row == top_row:
                continue
            if exclude_sub and (row, col_idx) in sub_cells:
                continue
            if col_idx in header_area.get(row, {}):
                leaves.append(header_area[row][col_idx])
        return " ".join(leaves)

    # Pass 1：adjustment 组内找特定别名（审增金额 等）—— 排除子组标题
    for col_idx in range(1, max_column + 1):
        if col_group(col_idx) not in adjustment_groups:
            continue
        lt = leaf_text_of(col_idx, exclude_top=True)
        if lt and any(alias in lt for alias in _ADJUSTMENT_ALIASES):
            return col_idx

    # Pass 2：adjustment 组内回退通用"金额" —— 排除子组标题
    for col_idx in range(1, max_column + 1):
        if col_group(col_idx) not in adjustment_groups:
            continue
        lt = leaf_text_of(col_idx, exclude_top=True)
        if lt and ("金额" in lt or "amount" in lt.lower()):
            return col_idx

    # Pass 3：无组表头时全局找特定别名
    if not groups:
        for col_idx in range(1, max_column + 1):
            lt = leaf_text_of(col_idx)
            if lt and any(alias in lt for alias in _ADJUSTMENT_ALIASES):
                return col_idx

    # Pass 4：旧模板兼容——full_text 同时含"审核增减"和"金额"（保留子组文本）
    for col_idx in range(1, max_column + 1):
        lt = leaf_text_of(col_idx, exclude_sub=False)
        if not lt:
            continue
        grp = col_group(col_idx)
        full_text = f"{grp} {lt}" if grp else lt
        if "审核增减" in full_text and "金额" in full_text:
            return col_idx

    return None


def detect_column_mapping(
    ws,
    header_row: int,
    data_start_row: Optional[int] = None,
) -> Dict[str, Optional[int]]:
    """
    动态检测Excel列映射关系，支持多级表头（组表头跨列，叶子表头在子行）。

    Args:
        ws: Excel工作表对象
        header_row: 表头行号
        data_start_row: 数据起始行；传入可避免把数据行误读为表头（影响子组识别）

    Returns:
        列名到列索引的映射字典
    """
    mapping: Dict[str, Optional[int]] = {k: None for k in FIELD_KEYS}

    header_area, sorted_rows = _read_header_area(ws, header_row, data_start_row)
    if not sorted_rows:
        return mapping

    groups = _scan_group_headers(header_area, sorted_rows, ws.max_column)

    # adjustment 列单独两遍扫描，避免通用"金额"抢先于特定别名"审增金额"
    mapping["adjustment"] = _detect_adjustment_column(
        header_area, sorted_rows, groups, ws.max_column
    )

    def col_group(col_idx: int) -> Optional[str]:
        for name, start, end in groups:
            if start <= col_idx <= end:
                return name
        return None

    def leaf_headers(col_idx: int) -> List[str]:
        """本列在所有表头行的值。
        不排除顶行组表头：单行表头时顶行即叶子行，排除会导致所有字段为 None。
        顶行组表头文本（"送审工程"/"审计结果"等）不含 name/unit/工程量/单价/合价
        等关键词，不会误匹配；adjustment 由 _detect_adjustment_column 单独处理。
        """
        leaves: List[str] = []
        for row in sorted_rows:
            if col_idx in header_area.get(row, {}):
                leaves.append(header_area[row][col_idx])
        return leaves

    for col_idx in range(1, ws.max_column + 1):
        leaves = leaf_headers(col_idx)
        if not leaves:
            continue
        leaf_text = " ".join(leaves)
        grp = col_group(col_idx)
        # 组合文本用于匹配（组 + 叶子）
        full_text = f"{grp} {leaf_text}" if grp else leaf_text

        # 项目名称
        if mapping["name"] is None and "项目名称" in leaf_text:
            mapping["name"] = col_idx
            continue
        # 单位
        if mapping["unit"] is None and ("计量单位" in leaf_text or leaf_text == "单位"):
            mapping["unit"] = col_idx
            continue

        # adjustment 已由 _detect_adjustment_column 预先识别，此处跳过

        # 送审组
        if grp == "送审" or (grp is None and "送审" in full_text):
            if mapping["submitted_qty"] is None and ("工程量" in leaf_text or "数量" in leaf_text):
                mapping["submitted_qty"] = col_idx
                continue
            if mapping["submitted_price"] is None and "单价" in leaf_text:
                mapping["submitted_price"] = col_idx
                continue
            if mapping["submitted_total"] is None and ("合价" in leaf_text or "总价" in leaf_text):
                mapping["submitted_total"] = col_idx
                continue

        # 审结/审定组
        if grp in ("审结", "审定") or (grp is None and ("审结" in full_text or "审定" in full_text)):
            if mapping["audited_qty"] is None and ("工程量" in leaf_text or "数量" in leaf_text):
                mapping["audited_qty"] = col_idx
                continue
            if mapping["audited_price"] is None and "单价" in leaf_text:
                mapping["audited_price"] = col_idx
                continue
            if mapping["audited_total"] is None and ("合价" in leaf_text or "总价" in leaf_text):
                mapping["audited_total"] = col_idx
                continue

    return mapping


def get_unit_from_name(name: str) -> str:
    """从项目名称中推断单位"""
    if not name:
        return ""

    patterns = {
        r"面积|面层|基层|砖|卷材|土工布|标线|脚手架|模板|人行道|盲道|边坡": "m2",
        r"土方|土石方|回填|弃置|换填|砂砾石|碎石|片石|垫层": "m3",
        r"管|电缆|导线|线缆|敷设|路缘|嵌边|分隔": "m",
        r"灯|标志|信号灯|机箱|杆|路灯|套": "套",
        r"井|雨水口|基础|座": "座",
        r"株|栽植": "株",
        r"防撞桶|垃圾箱|个": "个",
        r"指路牌|块": "块",
        r"接地极|根": "根",
        r"钢筋|t$": "t",
        r"kg$": "kg",
        r"系统|调试": "系统",
    }

    for pattern, unit in patterns.items():
        if re.search(pattern, name):
            return unit
    return ""


def _detect_header_row(ws) -> tuple:
    """检测表头行和数据起始行"""
    header_row = 1
    data_start_row = 2

    if ws.max_row >= 5:
        row5_values = [ws.cell(5, col).value for col in range(1, 15)]
        if any(v and "项目名称" in str(v) for v in row5_values):
            header_row = 5
            data_start_row = 6
    if ws.max_row >= 3 and header_row == 1:
        row3_values = [ws.cell(3, col).value for col in range(1, 15)]
        if any(v and "项目名称" in str(v) for v in row3_values):
            header_row = 3
            data_start_row = 6

    return header_row, data_start_row


def _detect_engineering_type(sheet_name: str, ws) -> str:
    """识别工程类型"""
    if sheet_name in SHEET_TYPE_MAP:
        return SHEET_TYPE_MAP[sheet_name]

    a2_value = ws['A2'].value
    if a2_value:
        match = re.search(r'【(.+?)】', str(a2_value))
        if match:
            return match.group(1)

    return "未知"


def _parse_sheet_items(
    ws,
    column_mapping_override: Optional[Dict[str, int]] = None,
) -> List[Dict[str, Any]]:
    """解析单个sheet的数据项

    Args:
        ws: 工作表对象
        column_mapping_override: 用户手工指定的列映射 {field_key: col_index}，
            非空时跳过自动检测直接使用。
    """
    header_row, data_start_row = _detect_header_row(ws)

    if column_mapping_override:
        # 用 override 覆盖自动检测；缺失字段回退到自动检测
        auto = detect_column_mapping(ws, header_row, data_start_row)
        col_mapping = {k: column_mapping_override.get(k) or auto.get(k) for k in FIELD_KEYS}
    else:
        col_mapping = detect_column_mapping(ws, header_row, data_start_row)

    if not col_mapping["name"]:
        col_mapping["name"] = 3 if header_row in [3, 5] else 2

    items: List[Dict[str, Any]] = []
    for row_idx in range(data_start_row, ws.max_row + 1):
        seq = ws.cell(row_idx, 1).value
        name = ws.cell(row_idx, col_mapping["name"]).value if col_mapping["name"] else None

        if name is None:
            continue

        name = str(name).strip()

        if "分部小计" in name or ("合" in name and "计" in name):
            continue
        if "审结工程删除" in name or "单价措施项目清单" in name:
            continue
        if name in ("混凝土模板及支架（撑）", "大型机械设备进出场及安拆"):
            continue

        submitted_qty = safe_float(ws.cell(row_idx, col_mapping["submitted_qty"]).value) if col_mapping["submitted_qty"] else None
        submitted_price = safe_float(ws.cell(row_idx, col_mapping["submitted_price"]).value) if col_mapping["submitted_price"] else None
        submitted_total = safe_float(ws.cell(row_idx, col_mapping["submitted_total"]).value) if col_mapping["submitted_total"] else None
        audited_qty = safe_float(ws.cell(row_idx, col_mapping["audited_qty"]).value) if col_mapping["audited_qty"] else None
        audited_price = safe_float(ws.cell(row_idx, col_mapping["audited_price"]).value) if col_mapping["audited_price"] else None
        audited_total = safe_float(ws.cell(row_idx, col_mapping["audited_total"]).value) if col_mapping["audited_total"] else None
        adjustment = safe_float(ws.cell(row_idx, col_mapping["adjustment"]).value) if col_mapping["adjustment"] else None

        # 自动计算调整金额：调整金额 = 审核合价 - 送审合价
        if adjustment is None and submitted_total is not None and audited_total is not None:
            adjustment = round(audited_total - submitted_total, 2)

        # 跳过空行（使用 is not None 检查，0 是有效值）
        if seq is None and submitted_total is None and audited_total is None:
            continue

        # 优先使用Excel中的单位列，为空时从名称推断
        unit = ""
        if col_mapping["unit"]:
            raw_unit = ws.cell(row_idx, col_mapping["unit"]).value
            if raw_unit:
                unit = str(raw_unit).strip()
        if not unit:
            unit = get_unit_from_name(name)

        items.append({
            "name": name,
            "unit": unit,
            "submitted_qty": submitted_qty,
            "submitted_price": submitted_price,
            "submitted_total": submitted_total,
            "audited_qty": audited_qty,
            "audited_price": audited_price,
            "audited_total": audited_total,
            "adjustment": adjustment,
            "row_index": row_idx
        })

    return items


def _validate_excel_file(file_path: str) -> None:
    """验证Excel文件"""
    if not os.path.exists(file_path):
        logger.error(f"Excel文件不存在: {file_path}")
        raise FileNotFoundError(f"Excel文件不存在: {file_path}")

    if not file_path.lower().endswith(SUPPORTED_EXTENSIONS):
        logger.error(f"不支持的文件格式: {file_path}")
        raise ValueError(f"不支持的文件格式，仅支持 .xlsx")


def parse_excel_file(
    file_path: str,
    column_mapping_override: Optional[Dict[str, Dict[str, int]]] = None,
) -> Dict[str, Any]:
    """
    解析Excel文件，提取工程数据

    Args:
        file_path: Excel文件路径
        column_mapping_override: 按 sheet_name 索引的手工列映射，可为 None

    Returns:
        包含工程类型和数据项的字典
    """
    _validate_excel_file(file_path)

    try:
        wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
    except Exception as e:
        logger.error(f"打开Excel文件失败: {file_path}, 错误: {str(e)}")
        raise ValueError(f"无法打开Excel文件: {str(e)}")

    try:
        engineering_type = "未知"
        for sheet_name in wb.sheetnames:
            if sheet_name in SHEET_TYPE_MAP:
                engineering_type = SHEET_TYPE_MAP[sheet_name]
                break
            ws = wb[sheet_name]
            a2_value = ws['A2'].value
            if a2_value:
                match = re.search(r'【(.+?)】', str(a2_value))
                if match:
                    engineering_type = match.group(1)
                    break

        items: List[Dict[str, Any]] = []
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            override = (column_mapping_override or {}).get(sheet_name)
            items.extend(_parse_sheet_items(ws, column_mapping_override=override))
    finally:
        wb.close()

    return {
        "engineering_type": engineering_type,
        "items": items
    }


def parse_excel_file_multi_sheet(
    file_path: str,
    column_mapping_override: Optional[Dict[str, Dict[str, int]]] = None,
) -> List[Dict[str, Any]]:
    """
    解析Excel文件，支持多sheet，每个sheet返回独立的数据

    Args:
        file_path: Excel文件路径
        column_mapping_override: 按 sheet_name 索引的手工列映射，可为 None

    Returns:
        包含多个工程类型数据的列表
    """
    _validate_excel_file(file_path)

    try:
        wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
    except Exception as e:
        logger.error(f"打开Excel文件失败: {file_path}, 错误: {str(e)}")
        raise ValueError(f"无法打开Excel文件: {str(e)}")

    results: List[Dict[str, Any]] = []
    try:
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            engineering_type = _detect_engineering_type(sheet_name, ws)
            override = (column_mapping_override or {}).get(sheet_name)
            items = _parse_sheet_items(ws, column_mapping_override=override)

            if items:
                results.append({
                    "engineering_type": engineering_type,
                    "sheet_name": sheet_name,
                    "items": items
                })
    finally:
        wb.close()

    return results


def preview_excel_file(file_path: str) -> Dict[str, Any]:
    """
    预览Excel文件，返回解析结果概览（不保存数据）。
    用于上传前让用户确认解析是否正确。
    """
    _validate_excel_file(file_path)

    try:
        wb = openpyxl.load_workbook(file_path, data_only=True, read_only=True)
    except Exception as e:
        logger.error(f"打开Excel文件失败: {file_path}, 错误: {str(e)}")
        raise ValueError(f"无法打开Excel文件: {str(e)}")

    sheets_preview: List[Dict[str, Any]] = []
    warnings: List[str] = []

    try:
        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            header_row, data_start_row = _detect_header_row(ws)
            col_mapping = detect_column_mapping(ws, header_row, data_start_row)
            engineering_type = _detect_engineering_type(sheet_name, ws)

            # 读取表头区域，用于构建 available_columns（供前端手工映射下拉使用）
            header_area, sorted_rows = _read_header_area(ws, header_row, data_start_row)
            top_row = sorted_rows[0] if sorted_rows else header_row
            top_cells = header_area.get(top_row, {})
            available_columns = [
                {
                    "col": c,
                    "label": f"{get_column_letter(c)}: {top_cells.get(c, '')}",
                }
                for c in range(1, ws.max_column + 1)
                if any(c in header_area[r] for r in sorted_rows)
            ]

            # 收集前5行示例数据
            sample_rows: List[Dict[str, Any]] = []
            count = 0
            for row_idx in range(data_start_row, ws.max_row + 1):
                if count >= 5:
                    break
                name_col = col_mapping.get("name") or (3 if header_row in [3, 5] else 2)
                name = ws.cell(row_idx, name_col).value
                if name is None:
                    continue
                name = str(name).strip()
                if "分部小计" in name or ("合" in name and "计" in name):
                    continue
                if "审结工程删除" in name or "单价措施项目清单" in name:
                    continue

                sample_rows.append({
                    "name": name,
                    "unit": str(ws.cell(row_idx, col_mapping["unit"]).value or "") if col_mapping.get("unit") else "",
                    "submitted_qty": safe_float(ws.cell(row_idx, col_mapping["submitted_qty"]).value) if col_mapping.get("submitted_qty") else None,
                    "submitted_price": safe_float(ws.cell(row_idx, col_mapping["submitted_price"]).value) if col_mapping.get("submitted_price") else None,
                    "submitted_total": safe_float(ws.cell(row_idx, col_mapping["submitted_total"]).value) if col_mapping.get("submitted_total") else None,
                    "audited_qty": safe_float(ws.cell(row_idx, col_mapping["audited_qty"]).value) if col_mapping.get("audited_qty") else None,
                    "audited_price": safe_float(ws.cell(row_idx, col_mapping["audited_price"]).value) if col_mapping.get("audited_price") else None,
                    "audited_total": safe_float(ws.cell(row_idx, col_mapping["audited_total"]).value) if col_mapping.get("audited_total") else None,
                    "adjustment": safe_float(ws.cell(row_idx, col_mapping["adjustment"]).value) if col_mapping.get("adjustment") else None,
                })
                count += 1

            # 检查缺失的关键列
            missing_cols = [k for k, v in col_mapping.items() if v is None and k != "adjustment"]
            if missing_cols:
                warnings.append(f"Sheet '{sheet_name}' 缺少列: {', '.join(missing_cols)}")

            if engineering_type == "未知":
                warnings.append(f"Sheet '{sheet_name}' 未能识别工程类型")

            # 统计有效数据行数
            total_valid_rows = 0
            for row_idx in range(data_start_row, ws.max_row + 1):
                name_col = col_mapping.get("name") or (3 if header_row in [3, 5] else 2)
                name = ws.cell(row_idx, name_col).value
                if name is None:
                    continue
                name_str = str(name).strip()
                if "分部小计" in name_str or ("合" in name_str and "计" in name_str):
                    continue
                total_valid_rows += 1

            sheets_preview.append({
                "sheet_name": sheet_name,
                "engineering_type": engineering_type,
                "header_row": header_row,
                "data_start_row": data_start_row,
                "column_mapping": col_mapping,
                "available_columns": available_columns,
                "sample_data": sample_rows,
                "total_rows": total_valid_rows,
            })
    finally:
        wb.close()

    return {
        "sheets": sheets_preview,
        "warnings": warnings,
        "total_sheets": len(sheets_preview),
    }
