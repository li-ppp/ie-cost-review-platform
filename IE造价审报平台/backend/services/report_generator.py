"""
评审报告生成服务 - 支持灵活模板匹配与上下文感知定位
"""

import re
import os
import logging
from datetime import datetime
from docx import Document
from docx.shared import Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
from copy import deepcopy
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


def fmt_num(val, decimals: int = 2) -> str:
    """格式化数字为带两位小数的字符串"""
    if val is None:
        return "0.00"
    try:
        val = float(val)
    except (ValueError, TypeError):
        return "0.00"
    return f"{val:,.{decimals}f}"


def replace_paragraph_text(para, new_text: str) -> None:
    """替换段落文本，保留原有格式"""
    for run in para.runs:
        run.text = ""

    if para.runs:
        para.runs[0].text = new_text
    else:
        para.text = new_text


def generate_report_number(project_id: int, year: Optional[int] = None) -> str:
    """
    生成报告编号
    格式：IE-{年份}-{项目ID:03d}
    例如：IE-2026-001
    """
    if year is None:
        year = datetime.now().year
    return f"IE-{year}-{project_id:03d}"


def replace_placeholders(doc: Document, placeholders: Dict[str, str]) -> None:
    """
    替换文档中的占位符
    支持的占位符格式：
    - {{变量名}}
    - {变量名}
    - XX路项目（兼容旧模板）
    """
    def _replace_in_text(text: str) -> str:
        new_text = text
        for key, value in placeholders.items():
            new_text = new_text.replace(f"{{{{{key}}}}}", value)
            new_text = new_text.replace(f"{{{key}}}", value)
        if "项目名称" in placeholders:
            new_text = new_text.replace("XX 路项目", placeholders["项目名称"])
            new_text = new_text.replace("XX路项目", placeholders["项目名称"])
        return new_text

    for para in doc.paragraphs:
        text = para.text
        new_text = _replace_in_text(text)
        if new_text != text:
            replace_paragraph_text(para, new_text)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    text = para.text
                    new_text = _replace_in_text(text)
                    if new_text != text:
                        replace_paragraph_text(para, new_text)


def classify_items(items: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """将明细行分为审减项和审增项"""
    reduced: List[Dict] = []
    increased: List[Dict] = []

    for item in items:
        adj = item.get("adjustment")
        if adj is None:
            continue
        try:
            adj_val = float(adj)
        except (ValueError, TypeError):
            continue

        if adj_val < 0:
            reduced.append(item)
        elif adj_val > 0:
            increased.append(item)

    return reduced, increased


def build_item_line(item: Dict, is_last: bool = False) -> str:
    """构建单个清单项的评审描述文本"""
    name = item.get("name", "")
    unit = item.get("unit", "") or ""

    sq = item.get("submitted_qty")
    sp = item.get("submitted_price")
    st = item.get("submitted_total")
    aq = item.get("audited_qty")
    ap = item.get("audited_price")
    at = item.get("audited_total")
    adj = item.get("adjustment")

    sq_s = fmt_num(sq) if sq is not None else "0"
    sp_s = fmt_num(sp) if sp is not None else "0"
    st_s = fmt_num(st) if st is not None else "0.00"
    aq_s = fmt_num(aq) if aq is not None else "0"
    ap_s = fmt_num(ap) if ap is not None else "0"
    at_s = fmt_num(at) if at is not None else "0.00"

    try:
        adj_val = float(adj) if adj is not None else 0
    except (ValueError, TypeError):
        adj_val = 0

    if adj_val < 0:
        adj_label = "审减"
        adj_val_str = fmt_num(abs(adj_val))
    elif adj_val > 0:
        adj_label = "审增"
        adj_val_str = fmt_num(adj_val)
    else:
        adj_label = "审减"
        adj_val_str = "0.00"

    unit_price = f"元/{unit}" if unit else "元"
    end_mark = "。" if is_last else "；"
    line = (
        f'清单项"{name}"，'
        f"送审工程量{sq_s}{unit}，送审单价{sp_s}{unit_price}，送审合价{st_s}元，"
        f"审核工程量{aq_s}{unit}，审核单价{ap_s}{unit_price}，审核合价{at_s}元，"
        f"{adj_label}金额{adj_val_str}元{end_mark}"
    )
    return line


ENGINEERING_TYPE_ALIASES = {
    "道路工程": ["道路工程", "道路", "路工程", "市政道路"],
    "排水工程": ["排水工程", "排水", "雨污水", "给排水"],
    "交安工程": ["交安工程", "交通安全", "交安", "交通工程"],
    "桥涵工程": ["桥涵工程", "桥梁工程", "桥涵", "桥梁"],
    "照明工程": ["照明工程", "照明", "路灯", "路灯工程"],
    "电力工程": ["电力工程", "电力", "电气", "供电"],
    "通信工程": ["通信工程", "通信", "弱电", "管线"],
}


def match_engineering_type(text: str) -> Optional[str]:
    """从段落文本中识别工程类型标题（如"道路工程："）"""
    text_clean = text.strip()
    if not (text_clean.endswith("：") or text_clean.endswith(":")):
        return None
    text_clean = text_clean.rstrip("：: \t").strip()
    for eng_type, aliases in ENGINEERING_TYPE_ALIASES.items():
        for alias in aliases:
            if text_clean == alias:
                return eng_type
    return None


def _insert_paragraph_after(paragraph, text: str, template_para=None):
    """在指定段落后插入新段落，复制模板段落的格式"""
    new_p = OxmlElement('w:p')
    if template_para is not None:
        new_p = deepcopy(template_para._element)
        for r in new_p.findall(qn('w:r')):
            for t in r.findall(qn('w:t')):
                t.text = text
                break
            break
    else:
        new_r = OxmlElement('w:r')
        new_t = OxmlElement('w:t')
        new_t.text = text
        new_r.append(new_t)
        new_p.append(new_r)
    paragraph._element.addnext(new_p)
    return new_p


def _replace_summary_paragraph(para, ffb_total_submitted: float, ffb_total_audited: float) -> bool:
    """替换分部分项工程汇总段落中的金额数据。
    ffb_adjustment = audited - submitted：正数（审定>送审）是审增，负数（审定<送审）是审减。"""
    text = para.text
    ffb_adjustment = ffb_total_audited - ffb_total_submitted

    # 根据 ffb_adjustment 正负选择文案：正数审增，负数审减
    if ffb_adjustment > 0:
        summary_label = "审增"
    else:
        summary_label = "审减"

    pattern = r'由[\d,]+\.?\d*元[，,]\s*调整为[\d,]+\.?\d*元[，,]\s*(?:审减|核减|审增)[\d,]+\.?\d*元'
    replacement = (
        f"由{fmt_num(ffb_total_submitted)}元，"
        f"调整为{fmt_num(ffb_total_audited)}元，"
        f"{summary_label}{fmt_num(abs(ffb_adjustment))}元"
    )
    new_text = re.sub(pattern, replacement, text)

    if new_text != text:
        replace_paragraph_text(para, new_text)
        return True

    if "分部分项工程" in text and re.search(r'\d[\d,]*\.\d{2}', text):
        summary = (
            f"（一）分部分项工程及单价措施项目费部分：因分部分项工程量清单、"
            f"工程量及综合单价的调整，由{fmt_num(ffb_total_submitted)}元，"
            f"调整为{fmt_num(ffb_total_audited)}元，"
            f"{summary_label}{fmt_num(abs(ffb_adjustment))}元，核减具体情况如下："
        )
        replace_paragraph_text(para, summary)
        return True

    return False


# (二)~(六) 段落前缀 → section_totals 字典 key 的映射
_SECTION_PREFIX_MAP = [
    ("（二）", "措施项目"),
    ("（三）", "其他项目"),
    ("（四）", "规费"),
    ("（五）", "税金"),
    ("（六）", "附加税"),
]


def _replace_section_paragraph(para, submitted: float, audited: float, adjustment: float) -> bool:
    """替换 (二)~(六) 段落中的"由 X 元调整为 Y 元，审减金额 Z 元"数字。
    与 (一) 的区别：此处用"审减金额"而非"审减"，且"由X元"与"调整为"之间无逗号。
    adjustment 为正数时是审增，负数时是审减，根据正负动态选择文案。"""
    text = para.text
    # 同时匹配"审减金额"和"审增金额"两种历史文案
    pattern = r'由\s*[\d,]+\.?\d*\s*元\s*调整为\s*[\d,]+\.?\d*\s*元[，,]\s*审[减增]金额\s*[\d,]+\.?\d*\s*元'
    # 根据 adjustment 正负选择文案
    if adjustment is not None and adjustment > 0:
        label = "审增金额"
        amount_str = fmt_num(abs(adjustment))
    else:
        label = "审减金额"
        amount_str = fmt_num(abs(adjustment)) if adjustment is not None else "0"
    replacement = (
        f"由 {fmt_num(submitted)} 元"
        f"调整为 {fmt_num(audited)} 元，"
        f"{label} {amount_str} 元"
    )
    new_text = re.sub(pattern, replacement, text)
    if new_text != text:
        replace_paragraph_text(para, new_text)
        return True
    return False


def _find_section_region(paragraphs, start_idx: int, end_markers) -> List[int]:
    """
    查找从 start_idx 开始的段落区域，直到遇到结束标记
    返回区域内所有段落的索引列表
    """
    region: List[int] = []
    for j in range(start_idx + 1, len(paragraphs)):
        t = paragraphs[j].text.strip()
        if not t:
            continue
        for marker in end_markers:
            if marker(t):
                return region
        region.append(j)
    return region


def _is_detail_item(text: str) -> bool:
    """判断段落是否为明细项（清单项描述）"""
    if not text:
        return False
    patterns = [
        r'^清单项["\u201c]',
        r'^清单项\d',
        r'^\d+[\.\、]',
    ]
    return any(re.search(p, text) for p in patterns)


def _fill_cell(cell, value: str, alignment=None, font_size: Optional[int] = None, bold: bool = False) -> None:
    """填充单元格并设置格式"""
    cell.text = value
    if alignment is not None:
        for para in cell.paragraphs:
            para.alignment = alignment
    for para in cell.paragraphs:
        for run in para.runs:
            if font_size is not None:
                run.font.size = Pt(font_size)
            if bold:
                run.font.bold = True


def create_cost_analysis_table(doc: Document, items: List[Dict], table_type: str = "审减") -> Optional[Any]:
    """
    创建造价分析表格

    Args:
        doc: Word文档对象
        items: 数据项列表
        table_type: 表格类型（"审减"或"审增"）

    Returns:
        创建的表格对象
    """
    if not items:
        return None

    table = doc.add_table(rows=1, cols=10)
    table.style = 'Table Grid'

    headers = ["序号", "项目名称", "单位", "送审工程量", "送审单价", "送审合价",
               "审核工程量", "审核单价", "审核合价", f"{table_type}金额"]

    header_row = table.rows[0]
    for i, header in enumerate(headers):
        _fill_cell(header_row.cells[i], header, WD_ALIGN_PARAGRAPH.CENTER, font_size=10, bold=True)

    # 数据列配置：字段名 -> 列索引
    field_cols = [
        ("submitted_qty", 3), ("submitted_price", 4), ("submitted_total", 5),
        ("audited_qty", 6), ("audited_price", 7), ("audited_total", 8),
    ]

    for idx, item in enumerate(items, 1):
        row = table.add_row()
        _fill_cell(row.cells[0], str(idx), WD_ALIGN_PARAGRAPH.CENTER, font_size=9)
        _fill_cell(row.cells[1], item.get("name", ""), font_size=9)
        _fill_cell(row.cells[2], item.get("unit", ""), WD_ALIGN_PARAGRAPH.CENTER, font_size=9)

        for field, col_idx in field_cols:
            val = item.get(field)
            _fill_cell(row.cells[col_idx], fmt_num(val) if val is not None else "0.00",
                       WD_ALIGN_PARAGRAPH.RIGHT, font_size=9)

        adj = item.get("adjustment")
        adj_display = fmt_num(abs(float(adj))) if adj is not None else "0.00"
        _fill_cell(row.cells[9], adj_display, WD_ALIGN_PARAGRAPH.RIGHT, font_size=9)

    # 合计行
    total_row = table.add_row()
    _fill_cell(total_row.cells[0], "", font_size=10, bold=True)
    _fill_cell(total_row.cells[1], "合计", WD_ALIGN_PARAGRAPH.CENTER, font_size=10, bold=True)
    for i in range(2, 10):
        _fill_cell(total_row.cells[i], "", font_size=10, bold=True)

    total_submitted = sum(item.get("submitted_total", 0) or 0 for item in items)
    total_audited = sum(item.get("audited_total", 0) or 0 for item in items)
    total_adjustment = sum(item.get("adjustment", 0) or 0 for item in items)

    _fill_cell(total_row.cells[5], fmt_num(total_submitted), WD_ALIGN_PARAGRAPH.RIGHT, font_size=10, bold=True)
    _fill_cell(total_row.cells[8], fmt_num(total_audited), WD_ALIGN_PARAGRAPH.RIGHT, font_size=10, bold=True)
    _fill_cell(total_row.cells[9], fmt_num(abs(total_adjustment)), WD_ALIGN_PARAGRAPH.RIGHT, font_size=10, bold=True)

    return table


def generate_analysis_text(project_data: Dict[str, Any], project_name: str) -> str:
    """生成造价分析文本"""
    total_submitted = 0.0
    total_audited = 0.0
    engineering_stats: List[Dict[str, Any]] = []

    for eng_type, data in project_data.items():
        items = data.get("items", [])
        eng_submitted = sum(item.get("submitted_total", 0) or 0 for item in items)
        eng_audited = sum(item.get("audited_total", 0) or 0 for item in items)
        eng_adjustment = eng_audited - eng_submitted

        total_submitted += eng_submitted
        total_audited += eng_audited

        engineering_stats.append({
            "type": eng_type,
            "submitted": eng_submitted,
            "audited": eng_audited,
            "adjustment": eng_adjustment
        })

    if total_submitted > 0:
        adjustment_rate = (abs(total_submitted - total_audited) / total_submitted) * 100
    else:
        adjustment_rate = 0

    # 根据送审与审定的关系动态选择"审减"或"审增"文案
    if total_submitted - total_audited > 0:
        adj_label_total = "审减"
    else:
        adj_label_total = "审增"

    text = f"经审核，{project_name}送审金额为{fmt_num(total_submitted)}元，"
    text += f"审定金额为{fmt_num(total_audited)}元，"
    text += f"{adj_label_total}金额为{fmt_num(abs(total_submitted - total_audited))}元，"
    text += f"{adj_label_total}率为{adjustment_rate:.2f}%。\n\n"

    text += "各工程类型审核情况如下：\n"
    for stat in engineering_stats:
        if stat["adjustment"] != 0:
            text += f"{stat['type']}：送审{fmt_num(stat['submitted'])}元，"
            text += f"审定{fmt_num(stat['audited'])}元，"
            if stat["adjustment"] < 0:
                text += f"审减{fmt_num(abs(stat['adjustment']))}元。\n"
            else:
                text += f"审增{fmt_num(stat['adjustment'])}元。\n"

    high_adjustment_items = []
    for eng_type, data in project_data.items():
        items = data.get("items", [])
        for item in items:
            adj = item.get("adjustment")
            if adj is not None and abs(adj) > 10000:
                high_adjustment_items.append({
                    "name": item.get("name"),
                    "type": eng_type,
                    "adjustment": adj
                })

    if high_adjustment_items:
        text += f"\n主要调整项（金额超过1万元）共{len(high_adjustment_items)}项：\n"
        for item in sorted(high_adjustment_items, key=lambda x: abs(x["adjustment"]), reverse=True)[:5]:
            if item["adjustment"] < 0:
                text += f"- {item['name']}（{item['type']}）：审减{fmt_num(abs(item['adjustment']))}元\n"
            else:
                text += f"- {item['name']}（{item['type']}）：审增{fmt_num(item['adjustment'])}元\n"

    return text


def generate_review_report(
    template_path: str,
    output_path: str,
    project_data: Dict[str, Any],
    project_name: str = "XX路项目",
    client_name: str = "",
    project_type: str = "",
    project_id: Optional[int] = None,
    report_number: Optional[str] = None,
    section_totals: Optional[Dict[str, Dict[str, float]]] = None
) -> Dict[str, Any]:
    """
    生成评审报告 - 上下文感知的智能定位

    核心改进：
    1. 用"锚点 + 区域边界"代替绝对索引定位
    2. 根据上下文判断区域类型（审减/核增）
    3. 动态刷新段落列表，避免索引失效
    4. 增强边界情况处理（空数据、无明细项、特殊字符）
    5. 支持占位符模板机制（{{变量名}}）
    6. 自动生成造价分析文本
    7. 支持报告编号管理

    Returns:
        填充结果字典，包含 matched_types/skipped_types/warnings 等
    """
    if not project_data:
        raise ValueError("项目数据不能为空")
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"模板文件不存在: {template_path}")

    fill_result = {
        "matched_types": [],
        "skipped_types": [],
        "skipped_reasons": {},
        "filled_placeholders": [],
        "unfilled_placeholders": [],
        "summary_replaced": False,
        "detail_counts": {},
        "warnings": [],
        "sections_replaced": [],
        "section_totals": section_totals or {},
    }

    project_name = project_name.strip() or "XX路项目"

    if report_number is None:
        if project_id is not None:
            report_number = generate_report_number(project_id)
        else:
            report_number = f"IE-{datetime.now().year}-{int(datetime.now().timestamp()) % 10000:04d}"

    try:
        doc = Document(template_path)
    except Exception as e:
        logger.error(f"打开模板文件失败: {template_path}, 错误: {e}")
        raise ValueError(f"无法打开模板文件: {e}")

    # 计算汇总数据
    ffb_total_submitted = 0.0
    ffb_total_audited = 0.0

    for eng_type, data in project_data.items():
        items = data.get("items", [])
        for item in items:
            ffb_total_submitted += item.get("submitted_total") or 0
            ffb_total_audited += item.get("audited_total") or 0

    # 计算核减率
    if ffb_total_submitted > 0:
        reduction_rate = ((ffb_total_submitted - ffb_total_audited) / ffb_total_submitted) * 100
    else:
        reduction_rate = 0.0

    # === 第一步：替换占位符 ===
    placeholders = {
        "项目名称": project_name,
        "建设单位": client_name or "（建设单位）",
        "工程类型": project_type or "（工程类型）",
        "编制日期": datetime.now().strftime("%Y年%m月%d日"),
        "报告编号": report_number,
        "送审金额": fmt_num(ffb_total_submitted),
        "审定金额": fmt_num(ffb_total_audited),
        "审减金额": fmt_num(ffb_total_submitted - ffb_total_audited),
        "核减率": f"{reduction_rate:.2f}",
    }
    replace_placeholders(doc, placeholders)

    # 检查未替换的占位符
    remaining_placeholders = set()
    ph_scan_pattern = re.compile(r"\{\{([^}]+)\}\}")
    for para in doc.paragraphs:
        for m in ph_scan_pattern.finditer(para.text):
            remaining_placeholders.add(m.group(1).strip())
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    for m in ph_scan_pattern.finditer(para.text):
                        remaining_placeholders.add(m.group(1).strip())
    fill_result["unfilled_placeholders"] = sorted(remaining_placeholders)
    fill_result["filled_placeholders"] = [k for k in placeholders.keys() if k not in remaining_placeholders]

    # === 第二步：替换汇总数据段落 ===
    paragraphs = doc.paragraphs
    for para in paragraphs:
        text = para.text.strip()
        if text.startswith("（一）") and "分部分项工程" in text and re.search(r'\d[\d,]*\.\d{2}', text):
            if _replace_summary_paragraph(para, ffb_total_submitted, ffb_total_audited):
                fill_result["summary_replaced"] = True
    if not fill_result["summary_replaced"]:
        fill_result["warnings"].append("未找到汇总段落（以'（一）'开头且含'分部分项工程'的段落），汇总数据未更新")

    # === 第二步扩展：替换 (二)~(六) 措施/其他/规费/税金/附加税 段落金额 ===
    if section_totals:
        sections_replaced = []
        for para in paragraphs:
            text = para.text.strip()
            for prefix, key in _SECTION_PREFIX_MAP:
                if text.startswith(prefix) and key in section_totals:
                    vals = section_totals[key]
                    sub = float(vals.get("submitted") or 0)
                    aud = float(vals.get("audited") or 0)
                    adj = float(vals.get("adjustment") or 0)
                    if _replace_section_paragraph(para, sub, aud, adj):
                        sections_replaced.append(key)
                    break
        fill_result["sections_replaced"] = sections_replaced
        missing = [k for k in section_totals if k not in sections_replaced]
        if missing:
            fill_result["warnings"].append(f"未匹配到以下汇总段落的金额替换: {', '.join(missing)}")
    else:
        fill_result["sections_replaced"] = []

    # === 第三步：智能定位并填充每个工程类型的核减/核增明细 ===
    def is_next_section_header(text: str) -> bool:
        if text.startswith("（") and "、" in text[:5]:
            return True
        if text.startswith("附件"):
            return True
        return False

    def is_engineering_header(text: str) -> bool:
        return match_engineering_type(text) is not None

    def _fill_section(paragraphs, sub_header_idx, region_end, target_items):
        """在子标题后填充明细项"""
        if sub_header_idx < 0 or not target_items:
            return

        detail_indices = []
        for j in range(sub_header_idx + 1, min(region_end, len(paragraphs))):
            t = paragraphs[j].text.strip()
            if t and _is_detail_item(t):
                detail_indices.append(j)

        n = len(target_items)
        new_lines = [build_item_line(item, is_last=(i == n - 1)) for i, item in enumerate(target_items)]

        for k, item_idx in enumerate(detail_indices):
            if k < len(new_lines):
                replace_paragraph_text(paragraphs[item_idx], new_lines[k])
            else:
                replace_paragraph_text(paragraphs[item_idx], "")

        if len(new_lines) > len(detail_indices):
            insert_after_idx = detail_indices[-1] if detail_indices else sub_header_idx
            template_para = paragraphs[detail_indices[0]] if detail_indices else None

            for k in range(len(new_lines) - 1, len(detail_indices) - 1, -1):
                _insert_paragraph_after(
                    paragraphs[insert_after_idx],
                    new_lines[k],
                    template_para
                )

    for eng_type in project_data.keys():
        items = project_data[eng_type].get("items", [])
        reduced, increased = classify_items(items)

        if not reduced and not increased:
            continue

        paragraphs = doc.paragraphs

        # 查找工程类型标题
        header_idx = -1
        for i, para in enumerate(paragraphs):
            if match_engineering_type(para.text) == eng_type:
                header_idx = i
                break

        if header_idx < 0:
            fill_result["skipped_types"].append(eng_type)
            fill_result["skipped_reasons"][eng_type] = "模板中未找到该工程类型的标题段落"
            fill_result["warnings"].append(f"{eng_type}：有数据但模板中未找到对应的工程类型标题，数据未填充")
            logger.warning(f"工程类型 '{eng_type}' 在模板中未找到标题，跳过填充")
            continue

        # 确定工程类型区域边界
        region_end = len(paragraphs)
        for j in range(header_idx + 1, len(paragraphs)):
            t = paragraphs[j].text.strip()
            if is_engineering_header(t) or is_next_section_header(t):
                region_end = j
                break

        # 查找"核减具体情况"和"核增具体情况"子标题
        reduced_sub_idx = -1
        increased_sub_idx = -1
        for j in range(header_idx + 1, region_end):
            t = paragraphs[j].text.strip()
            if "核减" in t and "具体情况" in t:
                reduced_sub_idx = j
            elif "核增" in t and "具体情况" in t:
                increased_sub_idx = j

        # 填充核减项
        if reduced and reduced_sub_idx >= 0:
            reduced_end = increased_sub_idx if increased_sub_idx >= 0 else region_end
            _fill_section(paragraphs, reduced_sub_idx, reduced_end, reduced)
        elif reduced and reduced_sub_idx < 0:
            fill_result["warnings"].append(f"{eng_type}：有审减数据但模板中未找到'核减具体情况'子标题，审减数据未填充")

        # 刷新段落列表（插入可能改变了索引）
        if reduced and increased and reduced_sub_idx >= 0 and increased_sub_idx >= 0:
            paragraphs = doc.paragraphs
            # 重新定位
            header_idx = -1
            for i, para in enumerate(paragraphs):
                if match_engineering_type(para.text) == eng_type:
                    header_idx = i
                    break
            if header_idx < 0:
                continue
            region_end = len(paragraphs)
            for j in range(header_idx + 1, len(paragraphs)):
                t = paragraphs[j].text.strip()
                if is_engineering_header(t) or is_next_section_header(t):
                    region_end = j
                    break
            increased_sub_idx = -1
            for j in range(header_idx + 1, region_end):
                t = paragraphs[j].text.strip()
                if "核增" in t and "具体情况" in t:
                    increased_sub_idx = j
                    break

        # 填充核增项
        if increased and increased_sub_idx >= 0:
            _fill_section(paragraphs, increased_sub_idx, region_end, increased)
        elif increased and increased_sub_idx < 0:
            fill_result["warnings"].append(f"{eng_type}：有审增数据但模板中未找到'核增具体情况'子标题，审增数据未填充")

        # 记录匹配成功
        if eng_type not in fill_result["skipped_types"]:
            fill_result["matched_types"].append(eng_type)
            fill_result["detail_counts"][eng_type] = {
                "reduced": len(reduced),
                "increased": len(increased),
            }

    # === 第六步：清理占位符明细项和空工程类型区段 ===
    paragraphs = doc.paragraphs

    # 计算每个工程类型的审减/审增情况
    eng_data_status = {}
    for eng_type, data in project_data.items():
        items = data.get("items", [])
        reduced, increased = classify_items(items)
        eng_data_status[eng_type] = {
            "has_reduced": len(reduced) > 0,
            "has_increased": len(increased) > 0,
        }

    def _is_section_boundary(text: str) -> bool:
        if match_engineering_type(text) is not None:
            return True
        if text.startswith("（") and "、" in text[:5]:
            return True
        if text.startswith("附件"):
            return True
        return False

    paras_to_remove = []

    # 先清理"测试项目"明细项
    for p in paragraphs:
        text = p.text.strip()
        if not text:
            continue
        if "测试项目" in text and ("送审工程量0" in text or "送审合价0.00" in text):
            paras_to_remove.append(p)

    # 遍历段落，识别工程类型区段并清理空区段
    i = 0
    while i < len(paragraphs):
        para = paragraphs[i]
        text = para.text.strip()
        eng_type = match_engineering_type(text)

        if eng_type is not None:
            region_start = i
            region_end = len(paragraphs)
            for j in range(i + 1, len(paragraphs)):
                t = paragraphs[j].text.strip()
                if _is_section_boundary(t):
                    region_end = j
                    break

            status = eng_data_status.get(eng_type, {"has_reduced": False, "has_increased": False})

            if not status["has_reduced"] and not status["has_increased"]:
                for k in range(region_start, region_end):
                    paras_to_remove.append(paragraphs[k])
            else:
                for k in range(region_start, region_end):
                    t = paragraphs[k].text.strip()
                    if "核减" in t and "具体情况" in t and not status["has_reduced"]:
                        paras_to_remove.append(paragraphs[k])
                    elif "核增" in t and "具体情况" in t and not status["has_increased"]:
                        paras_to_remove.append(paragraphs[k])

            i = region_end
        else:
            i += 1

    # 执行删除（去重避免同一段落被删除两次）
    seen = set()
    for p in paras_to_remove:
        if id(p) in seen:
            continue
        seen.add(id(p))
        parent = p._element.getparent()
        if parent is not None:
            parent.remove(p._element)

    try:
        doc.save(output_path)
    except Exception as e:
        logger.error(f"保存报告文件失败: {output_path}, 错误: {e}")
        raise

    return fill_result


def validate_template(template_path: str) -> Dict[str, Any]:
    """
    扫描模板文件，返回结构兼容性报告（只读分析，不修改模板）。

    Returns:
        {
            "placeholders": ["项目名称", ...],
            "engineering_types": [{"type", "header_text", "has_reduced_subheader", ...}, ...],
            "has_summary_paragraph": bool,
            "summary_paragraph_index": int | None,
            "warnings": [str, ...],
            "is_compatible": bool,
        }
    """
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"模板文件不存在: {template_path}")

    try:
        doc = Document(template_path)
    except Exception as e:
        raise ValueError(f"无法打开模板文件: {e}")

    placeholders_set = set()
    ph_pattern = re.compile(r"\{\{([^}]+)\}\}")

    paragraphs = doc.paragraphs

    for para in paragraphs:
        for m in ph_pattern.finditer(para.text):
            placeholders_set.add(m.group(1).strip())
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    for m in ph_pattern.finditer(para.text):
                        placeholders_set.add(m.group(1).strip())

    engineering_types_found = []
    has_summary_paragraph = False
    summary_paragraph_index = None
    warnings = []

    def _is_section_boundary(text: str) -> bool:
        if match_engineering_type(text) is not None:
            return True
        if text.startswith("（") and "、" in text[:5]:
            return True
        if text.startswith("附件"):
            return True
        return False

    for i, para in enumerate(paragraphs):
        text = para.text.strip()

        eng_type = match_engineering_type(text)
        if eng_type is not None:
            region_end = len(paragraphs)
            for j in range(i + 1, len(paragraphs)):
                t = paragraphs[j].text.strip()
                if _is_section_boundary(t):
                    region_end = j
                    break

            has_reduced = False
            has_increased = False
            detail_count = 0
            for j in range(i + 1, region_end):
                t = paragraphs[j].text.strip()
                if "核减" in t and "具体情况" in t:
                    has_reduced = True
                elif "核增" in t and "具体情况" in t:
                    has_increased = True
                if _is_detail_item(t):
                    detail_count += 1

            engineering_types_found.append({
                "type": eng_type,
                "header_text": text,
                "paragraph_index": i,
                "has_reduced_subheader": has_reduced,
                "has_increased_subheader": has_increased,
                "detail_item_count": detail_count,
            })

        if text.startswith("（一）") and "分部分项工程" in text:
            has_summary_paragraph = True
            summary_paragraph_index = i

    found_type_names = {et["type"] for et in engineering_types_found}
    all_expected_types = list(ENGINEERING_TYPE_ALIASES.keys())
    for t in all_expected_types:
        if t not in found_type_names:
            warnings.append(f"模板中未找到'{t}'的标题段落，含该类型数据的Excel将无法填充")

    for et in engineering_types_found:
        if not et["has_reduced_subheader"]:
            warnings.append(f"{et['type']}区段缺少'核减具体情况'子标题")
        if not et["has_increased_subheader"]:
            warnings.append(f"{et['type']}区段缺少'核增具体情况'子标题")
        if et["detail_item_count"] == 0:
            warnings.append(f"{et['type']}区段无明细项占位行，新数据将插入到子标题后")

    if not has_summary_paragraph:
        warnings.append("未找到汇总段落（以'（一）'开头且含'分部分项工程'的段落），汇总数据将无法更新")

    return {
        "placeholders": sorted(placeholders_set),
        "engineering_types": engineering_types_found,
        "has_summary_paragraph": has_summary_paragraph,
        "summary_paragraph_index": summary_paragraph_index,
        "warnings": warnings,
        "is_compatible": len(warnings) == 0 or all("缺少" not in w and "未找到" not in w for w in warnings),
    }
