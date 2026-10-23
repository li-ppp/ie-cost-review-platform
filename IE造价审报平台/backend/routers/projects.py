"""
项目管理路由
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request, Form
from sqlalchemy.orm import Session, joinedload
from typing import List, Optional
from pydantic import BaseModel
import os
import re
import json
import logging
import time
import threading
from datetime import datetime

from database import get_db
from models import Project, ExcelFile, ExcelData, Report, User, _utcnow
from schemas import ProjectCreate, ProjectUpdate, ProjectResponse, ExcelFileResponse
from services.excel_parser import parse_excel_file, parse_excel_file_multi_sheet
from config import UPLOADS_DIR
from auth import get_current_user, require_admin
from routers.logs import log_operation

router = APIRouter()
logger = logging.getLogger(__name__)

UPLOAD_DIR = os.path.join(UPLOADS_DIR, "excel")
os.makedirs(UPLOAD_DIR, exist_ok=True)

MAX_LIMIT = 500
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# 线程安全的项目列表缓存
_projects_cache: dict = {}
_projects_cache_lock = threading.Lock()
_projects_cache_ttl = 5


class DataUpdateRequest(BaseModel):
    """数据项更新请求模型"""
    item_name: Optional[str] = None
    unit: Optional[str] = None
    submitted_qty: Optional[float] = None
    submitted_price: Optional[float] = None
    submitted_total: Optional[float] = None
    audited_qty: Optional[float] = None
    audited_price: Optional[float] = None
    audited_total: Optional[float] = None
    adjustment: Optional[float] = None


def _sanitize_filename(filename: str) -> str:
    """清理文件名，保留中文字符，仅移除不安全的路径字符"""
    # 保留中文、字母、数字、下划线、连字符、点
    # 移除路径分隔符和控制字符
    safe = re.sub(r'[\\/:*?"<>|\r\n\t]', '_', filename)
    # 限制长度，避免文件系统路径过长
    if len(safe) > 100:
        name, ext = os.path.splitext(safe)
        safe = name[:100 - len(ext)] + ext
    return safe


def _invalidate_projects_cache() -> None:
    """清除项目列表缓存"""
    with _projects_cache_lock:
        _projects_cache.clear()


@router.post("/", response_model=ProjectResponse)
def create_project(
    project: ProjectCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """创建项目"""
    db_project = Project(**project.dict())
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    _invalidate_projects_cache()
    log_operation(db, current_user.id, current_user.username, "创建项目",
                target_type="project", target_id=db_project.id,
                detail=f"创建项目: {db_project.name}", ip_address=request.client.host)
    return db_project


@router.get("/")
def get_projects(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取项目列表（含Excel和报告计数，带缓存）"""
    from sqlalchemy import func

    if skip < 0:
        skip = 0
    limit = max(1, min(limit, MAX_LIMIT))

    cache_key = f"{skip}_{limit}"
    current_time = time.time()

    with _projects_cache_lock:
        cached = _projects_cache.get(cache_key)
        if cached and (current_time - cached["time"]) < _projects_cache_ttl:
            return cached["data"]

    # 使用子查询一次性获取计数，避免N+1问题
    excel_counts = db.query(
        ExcelFile.project_id,
        func.count(ExcelFile.id).label('count')
    ).group_by(ExcelFile.project_id).subquery()

    report_counts = db.query(
        Report.project_id,
        func.count(Report.id).label('count')
    ).group_by(Report.project_id).subquery()

    projects = db.query(
        Project,
        func.coalesce(excel_counts.c.count, 0).label('excel_count'),
        func.coalesce(report_counts.c.count, 0).label('report_count')
    ).outerjoin(
        excel_counts, Project.id == excel_counts.c.project_id
    ).outerjoin(
        report_counts, Project.id == report_counts.c.project_id
    ).order_by(Project.created_at.desc()).offset(skip).limit(limit).all()

    result = []
    for p, excel_count, report_count in projects:
        result.append({
            "id": p.id,
            "name": p.name,
            "client_name": p.client_name,
            "project_type": p.project_type,
            "status": p.status,
            "created_at": p.created_at,
            "updated_at": p.updated_at,
            "excel_count": excel_count,
            "report_count": report_count
        })

    with _projects_cache_lock:
        _projects_cache[cache_key] = {"time": current_time, "data": result}

    return result


@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取项目详情"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")
    return project


@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: int,
    project: ProjectUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """更新项目"""
    db_project = db.query(Project).filter(Project.id == project_id).first()
    if not db_project:
        raise HTTPException(status_code=404, detail="项目不存在")

    update_data = project.dict(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_project, key, value)

    db_project.updated_at = _utcnow()
    db.commit()
    db.refresh(db_project)
    _invalidate_projects_cache()
    return db_project


@router.delete("/{project_id}")
def delete_project(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """删除项目"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    # 删除关联的物理文件
    excel_files = db.query(ExcelFile).filter(ExcelFile.project_id == project_id).all()
    for ef in excel_files:
        if ef.file_path and os.path.exists(ef.file_path):
            try:
                os.remove(ef.file_path)
            except OSError as e:
                logger.warning(f"删除文件失败 {ef.file_path}: {e}")

    # 删除关联报告的物理文件（docx + 同名 pdf）
    reports = db.query(Report).filter(Report.project_id == project_id).all()
    for r in reports:
        for path in [r.file_path]:
            if not path:
                continue
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError as e:
                    logger.warning(f"删除报告文件失败 {path}: {e}")
            # 同名 pdf
            pdf_path = path[:-5] + '.pdf' if path.endswith('.docx') else None
            if pdf_path and os.path.exists(pdf_path):
                try:
                    os.remove(pdf_path)
                except OSError as e:
                    logger.warning(f"删除PDF文件失败 {pdf_path}: {e}")

    db.delete(project)
    db.commit()
    _invalidate_projects_cache()
    log_operation(db, current_user.id, current_user.username, "删除项目",
                target_type="project", target_id=project_id,
                detail=f"删除项目: {project.name}", ip_address=request.client.host)
    return {"message": "项目已删除"}


@router.post("/{project_id}/upload")
async def upload_excel(
    project_id: int,
    request: Request,
    file: UploadFile = File(...),
    column_mappings: str = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """上传Excel文件"""
    # 解析手工列映射（前端可选提交）
    mapping_override = None
    if column_mappings:
        try:
            mapping_override = json.loads(column_mappings)
            if not isinstance(mapping_override, dict):
                mapping_override = None
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"column_mappings JSON 解析失败: {e}")
            mapping_override = None
    if not file.filename:
        raise HTTPException(status_code=400, detail="未提供文件名")

    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ['.xlsx']:
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 格式")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小不能超过10MB")

    # 验证文件为有效的 Office Open XML（ZIP）格式
    if not content[:4].startswith(b'PK'):
        raise HTTPException(status_code=400, detail="文件格式无效，不是有效的 Excel 文件")

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    safe_filename = _sanitize_filename(file.filename)
    file_path = os.path.join(UPLOAD_DIR, f"{project_id}_{datetime.now().timestamp()}_{safe_filename}")

    # 先写入临时文件，解析成功后再提交
    try:
        with open(file_path, "wb") as buffer:
            buffer.write(content)
    except OSError as e:
        logger.error(f"文件写入失败: {e}")
        raise HTTPException(status_code=500, detail="文件保存失败")
    finally:
        await file.close()

    # 解析Excel（在删除旧数据之前，避免解析失败导致数据丢失）
    try:
        sheets_data = parse_excel_file_multi_sheet(file_path, column_mapping_override=mapping_override)
        if not sheets_data:
            data_result = parse_excel_file(file_path, column_mapping_override=mapping_override)
            data_items = data_result.get("items", []) if isinstance(data_result, dict) else []
            if data_items:
                eng_type = data_result.get("engineering_type", "未知") if isinstance(data_result, dict) else "未知"
                sheets_data = [{"engineering_type": eng_type, "items": data_items}]
            else:
                sheets_data = []
    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        logger.error(f"Excel解析失败: {e}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"Excel解析失败: {str(e)}")

    if not sheets_data:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=400, detail="Excel文件中没有有效数据")

    # 解析成功后，删除旧数据和物理文件
    old_excel_files = db.query(ExcelFile).filter(ExcelFile.project_id == project_id).all()
    old_file_paths = [ef.file_path for ef in old_excel_files if ef.file_path]
    for old_file in old_excel_files:
        db.delete(old_file)
    db.flush()  # 从会话中移除旧记录，但未提交

    # 保存新数据（批量提交）
    total_items_count = 0
    last_excel_file = None

    try:
        for sheet_data in sheets_data:
            items = sheet_data.get("items", [])
            if not items:
                logger.warning(f"Sheet '{sheet_data.get('engineering_type', '未知')}' 没有数据项")
                continue

            excel_file = ExcelFile(
                project_id=project_id,
                file_name=file.filename,
                file_path=file_path,
                engineering_type=sheet_data.get("engineering_type", "未知")
            )
            db.add(excel_file)
            db.flush()
            last_excel_file = excel_file

            for item in items:
                if not item.get("name"):
                    continue
                # 数值字段验证
                cleaned = {}
                for field in ["submitted_qty", "submitted_price", "submitted_total",
                              "audited_qty", "audited_price", "audited_total", "adjustment"]:
                    val = item.get(field)
                    if val is not None:
                        try:
                            cleaned[field] = float(val)
                        except (ValueError, TypeError):
                            logger.warning(f"字段 {field} 值无效: {val}")
                            cleaned[field] = None
                    else:
                        cleaned[field] = None

                excel_data = ExcelData(
                    file_id=excel_file.id,
                    item_name=item.get("name"),
                    unit=item.get("unit"),
                    submitted_qty=cleaned["submitted_qty"],
                    submitted_price=cleaned["submitted_price"],
                    submitted_total=cleaned["submitted_total"],
                    audited_qty=cleaned["audited_qty"],
                    audited_price=cleaned["audited_price"],
                    audited_total=cleaned["audited_total"],
                    adjustment=cleaned["adjustment"],
                    row_index=item.get("row_index")
                )
                db.add(excel_data)
                total_items_count += 1

        if last_excel_file is None:
            raise HTTPException(status_code=400, detail="Excel文件中没有有效数据项")

        db.commit()
    except HTTPException:
        db.rollback()
        if os.path.exists(file_path):
            os.remove(file_path)
        raise
    except Exception as e:
        db.rollback()
        if os.path.exists(file_path):
            os.remove(file_path)
        logger.error(f"保存数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="数据保存失败")

    # 删除旧Excel物理文件（提交成功后）
    for old_path in old_file_paths:
        if old_path and old_path != file_path and os.path.exists(old_path):
            try:
                os.remove(old_path)
            except OSError as e:
                logger.warning(f"删除旧文件失败 {old_path}: {e}")

    _invalidate_projects_cache()
    logger.info(f"项目 {project_id} 上传成功，共 {total_items_count} 项，用户: {getattr(current_user, 'username', 'unknown')}")
    log_operation(db, current_user.id, current_user.username, "上传Excel",
                target_type="project", target_id=project_id,
                detail=f"上传文件: {file.filename}, 共 {total_items_count} 项", ip_address=request.client.host)

    return {
        "message": "文件上传成功",
        "file_id": last_excel_file.id,
        "engineering_type": last_excel_file.engineering_type,
        "items_count": total_items_count
    }


@router.post("/{project_id}/excel-preview")
async def preview_excel_upload(
    project_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """预览Excel解析结果（不保存数据），用于上传前确认解析正确性"""
    import tempfile

    if not file.filename:
        raise HTTPException(status_code=400, detail="未提供文件名")

    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in ('.xlsx',):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 格式")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="文件大小不能超过10MB")

    if not content[:4].startswith(b'PK'):
        raise HTTPException(status_code=400, detail="文件格式无效，不是有效的 Excel 文件")

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    tmp_fd, tmp_path = tempfile.mkstemp(suffix='.xlsx')
    try:
        with os.fdopen(tmp_fd, 'wb') as f:
            f.write(content)

        from services.excel_parser import preview_excel_file
        result = preview_excel_file(tmp_path)
        logger.info(f"Excel预览: project_id={project_id}, sheets={result.get('total_sheets')}, warnings={len(result.get('warnings', []))}")
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Excel预览失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Excel预览失败: {str(e)}")
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


@router.get("/{project_id}/data", response_model=List[ExcelFileResponse])
def get_project_data(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取项目数据"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    excel_files = db.query(ExcelFile).options(
        joinedload(ExcelFile.data_items)
    ).filter(ExcelFile.project_id == project_id).all()
    return excel_files


@router.get("/{project_id}/summary")
def get_project_summary(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取项目数据汇总"""
    from sqlalchemy import func

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    excel_files = db.query(ExcelFile).filter(ExcelFile.project_id == project_id).all()

    summary = {
        "project_name": project.name,
        "total_submitted": 0.0,
        "total_audited": 0.0,
        "total_adjustment": 0.0,
        "engineering_types": []
    }

    for excel_file in excel_files:
        result = db.query(
            func.coalesce(func.sum(ExcelData.submitted_total), 0),
            func.coalesce(func.sum(ExcelData.audited_total), 0),
            func.coalesce(func.sum(ExcelData.adjustment), 0)
        ).filter(ExcelData.file_id == excel_file.id).first()

        file_submitted = float(result[0] or 0)
        file_audited = float(result[1] or 0)
        file_adjustment = float(result[2] or 0)

        summary["total_submitted"] += file_submitted
        summary["total_audited"] += file_audited
        summary["total_adjustment"] += file_adjustment

        summary["engineering_types"].append({
            "type": excel_file.engineering_type,
            "submitted": file_submitted,
            "audited": file_audited,
            "adjustment": file_adjustment
        })

    return summary


@router.put("/{project_id}/data/{data_id}")
def update_excel_data(
    project_id: int,
    data_id: int,
    data_update: DataUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """更新Excel数据项（人工修正）"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    excel_data = db.query(ExcelData).filter(
        ExcelData.id == data_id,
        ExcelData.file_id.in_(
            db.query(ExcelFile.id).filter(ExcelFile.project_id == project_id)
        )
    ).first()

    if not excel_data:
        raise HTTPException(status_code=404, detail="数据项不存在")

    update_data = data_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(excel_data, field, value)

    db.commit()
    db.refresh(excel_data)
    _invalidate_projects_cache()

    return {
        "message": "数据更新成功",
        "data": {
            "id": excel_data.id,
            "item_name": excel_data.item_name,
            "unit": excel_data.unit,
            "submitted_qty": excel_data.submitted_qty,
            "submitted_price": excel_data.submitted_price,
            "submitted_total": excel_data.submitted_total,
            "audited_qty": excel_data.audited_qty,
            "audited_price": excel_data.audited_price,
            "audited_total": excel_data.audited_total,
            "adjustment": excel_data.adjustment
        }
    }


@router.post("/{project_id}/validate")
def validate_project_data(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """校验项目数据完整性"""
    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    excel_files = db.query(ExcelFile).filter(ExcelFile.project_id == project_id).all()

    if not excel_files:
        return {
            "valid": False,
            "errors": ["项目没有上传任何Excel文件"],
            "warnings": []
        }

    errors = []
    warnings = []

    for excel_file in excel_files:
        data_items = db.query(ExcelData).filter(ExcelData.file_id == excel_file.id).all()

        if not data_items:
            errors.append(f"文件 '{excel_file.file_name}' 没有数据项")
            continue

        for idx, item in enumerate(data_items, 1):
            if not item.item_name:
                errors.append(f"文件 '{excel_file.file_name}' 第 {idx} 行缺少项目名称")

            if item.submitted_qty is not None and item.submitted_qty < 0:
                warnings.append(f"文件 '{excel_file.file_name}' 第 {idx} 行送审工程量为负数")

            if item.submitted_price is not None and item.submitted_price < 0:
                warnings.append(f"文件 '{excel_file.file_name}' 第 {idx} 行送审单价为负数")

            if item.audited_qty is not None and item.audited_qty < 0:
                warnings.append(f"文件 '{excel_file.file_name}' 第 {idx} 行审核工程量为负数")

            if item.audited_price is not None and item.audited_price < 0:
                warnings.append(f"文件 '{excel_file.file_name}' 第 {idx} 行审核单价为负数")

            # 数据一致性检查（使用 is not None 判断，避免 0 被忽略）
            if (item.submitted_qty is not None and item.submitted_price is not None
                    and item.submitted_total is not None):
                expected_total = item.submitted_qty * item.submitted_price
                if abs(expected_total - item.submitted_total) > 0.01:
                    warnings.append(f"文件 '{excel_file.file_name}' 第 {idx} 行送审合价计算不一致")

    return {
        "valid": len(errors) == 0,
        "errors": errors,
        "warnings": warnings
    }


@router.get("/{project_id}/export")
def export_project_data(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """导出项目数据为Excel文件"""
    import openpyxl
    from fastapi.responses import StreamingResponse
    import io

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    excel_files = db.query(ExcelFile).options(
        joinedload(ExcelFile.data_items)
    ).filter(ExcelFile.project_id == project_id).all()

    if not excel_files:
        raise HTTPException(status_code=400, detail="项目没有数据可导出")

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    for excel_file in excel_files:
        sheet_name = (excel_file.engineering_type or "未知类型")[:31]  # Excel sheet 名最长 31 字符
        ws = wb.create_sheet(title=sheet_name)

        headers = ["序号", "项目名称", "单位", "送审工程量", "送审单价", "送审合价",
                   "审核工程量", "审核单价", "审核合价", "审减金额"]
        ws.append(headers)

        for idx, item in enumerate(excel_file.data_items, 1):
            ws.append([
                idx,
                item.item_name,
                item.unit,
                item.submitted_qty,
                item.submitted_price,
                item.submitted_total,
                item.audited_qty,
                item.audited_price,
                item.audited_total,
                item.adjustment
            ])

        # 调整列宽
        for column in ws.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if cell.value is not None:
                        max_length = max(max_length, len(str(cell.value)))
                except Exception:
                    continue
            adjusted_width = min(max_length + 2, 50)
            ws.column_dimensions[column_letter].width = adjusted_width

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    filename = f"{project.name}_数据导出.xlsx"
    return StreamingResponse(
        output,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{filename}"}
    )
