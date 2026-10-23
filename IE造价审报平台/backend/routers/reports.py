"""
报告生成路由
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import logging

from database import get_db, SessionLocal
from models import Report, Project, Template, ExcelFile, User
from schemas import ReportResponse
from services.report_generator import generate_review_report, generate_report_number
from auth import get_current_user, require_admin
from routers.logs import log_operation
from config import UPLOADS_DIR

router = APIRouter()
logger = logging.getLogger(__name__)

OUTPUT_DIR = os.path.join(UPLOADS_DIR, "reports")
os.makedirs(OUTPUT_DIR, exist_ok=True)

MAX_LIMIT = 500


class ReviewRequest(BaseModel):
    review_status: str = Field(..., description="审核状态: reviewing/approved/rejected")
    review_comment: Optional[str] = Field("", description="审核意见")


def _generate_report_background(
    report_id: int,
    template_path: str,
    output_path: str,
    project_data: dict,
    project_name: str,
    client_name: str = "",
    project_type: str = "",
    project_id: int = None,
    report_number: str = None,
    section_totals: dict = None
):
    """后台任务：生成报告"""
    db = SessionLocal()
    try:
        logger.info(f"开始生成报告 ID: {report_id}")

        fill_result = generate_review_report(
            template_path=template_path,
            output_path=output_path,
            project_data=project_data,
            project_name=project_name,
            client_name=client_name,
            project_type=project_type,
            project_id=project_id,
            report_number=report_number,
            section_totals=section_totals
        )

        report = db.query(Report).filter(Report.id == report_id).first()
        if report:
            report.status = "generated"
            report.fill_report = fill_result
            db.commit()
            logger.info(f"报告生成成功 ID: {report_id}, 匹配类型: {fill_result.get('matched_types')}, 跳过: {fill_result.get('skipped_types')}")
        else:
            logger.error(f"报告记录不存在 ID: {report_id}")

    except Exception as e:
        logger.error(f"报告生成失败 ID: {report_id}: {str(e)}", exc_info=True)
        db.rollback()
        report = db.query(Report).filter(Report.id == report_id).first()
        if report:
            report.status = "failed"
            report.fill_report = {
                "error": str(e),
                "warnings": ["报告生成过程中发生异常"],
                "matched_types": [],
                "skipped_types": [],
                "unfilled_placeholders": [],
            }
            db.commit()
    finally:
        db.close()


@router.post("/generate", response_model=ReportResponse)
def generate_report(
    report_data: dict,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """生成评审报告（异步）"""
    project_id = report_data.get("project_id")
    template_id = report_data.get("template_id")

    if not project_id or not template_id:
        raise HTTPException(status_code=400, detail="缺少项目ID或模板ID")

    project = db.query(Project).filter(Project.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    template = db.query(Template).filter(Template.id == template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    excel_files = db.query(ExcelFile).options(
        joinedload(ExcelFile.data_items)
    ).filter(ExcelFile.project_id == project.id).all()

    if not excel_files:
        raise HTTPException(status_code=400, detail="项目没有上传Excel数据")

    all_data = {}
    for excel_file in excel_files:
        all_data[excel_file.engineering_type] = {
            "items": [
                {
                    "name": item.item_name,
                    "unit": item.unit,
                    "submitted_qty": item.submitted_qty,
                    "submitted_price": item.submitted_price,
                    "submitted_total": item.submitted_total,
                    "audited_qty": item.audited_qty,
                    "audited_price": item.audited_price,
                    "audited_total": item.audited_total,
                    "adjustment": item.adjustment
                }
                for item in excel_file.data_items
            ]
        }

    report_number = generate_report_number(project.id)

    report_record = Report(
        project_id=project.id,
        template_id=template.id,
        file_name="pending",
        file_path="pending",
        status="generating",
        report_number=report_number,
        review_status="draft",
        created_by=current_user.id
    )
    db.add(report_record)
    db.commit()
    db.refresh(report_record)

    # 用 report_record.id 生成唯一文件名，避免同项目重复生成时覆盖旧报告
    output_filename = f"{project.name}_评审报告_{report_number}_{report_record.id}.docx"
    output_path = os.path.join(OUTPUT_DIR, output_filename)
    report_record.file_name = output_filename
    report_record.file_path = output_path
    db.commit()
    db.refresh(report_record)

    section_totals = report_data.get("section_totals")

    background_tasks.add_task(
        _generate_report_background,
        report_record.id,
        template.file_path,
        output_path,
        all_data,
        project.name,
        project.client_name or "",
        project.project_type or "",
        project.id,
        report_number,
        section_totals
    )

    logger.info(f"报告生成任务已提交 ID: {report_record.id}, 用户: {getattr(current_user, 'username', 'unknown')}")
    log_operation(db, current_user.id, current_user.username, "生成报告",
                target_type="report", target_id=report_record.id,
                detail=f"生成报告: {project.name}, 编号: {report_number}", ip_address=request.client.host)
    return report_record


@router.get("/")
def get_all_reports(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取所有报告（含项目名称、模板名称和上传人）"""
    limit = min(limit, MAX_LIMIT)
    reports = (
        db.query(Report, Project.name.label("project_name"), Template.name.label("template_name"), User.username.label("created_by_name"))
        .join(Project, Report.project_id == Project.id)
        .join(Template, Report.template_id == Template.id)
        .outerjoin(User, Report.created_by == User.id)
        .order_by(Report.generated_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    result = []
    for r, proj_name, tmpl_name, creator_name in reports:
        item = {c.name: getattr(r, c.name) for c in r.__table__.columns}
        item["project_name"] = proj_name
        item["template_name"] = tmpl_name
        item["created_by_name"] = creator_name or ""
        result.append(item)
    return result


@router.get("/project/{project_id}")
def get_project_reports(
    project_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取项目的所有报告（含项目名称、模板名称和上传人）"""
    reports = (
        db.query(Report, Project.name.label("project_name"), Template.name.label("template_name"), User.username.label("created_by_name"))
        .join(Project, Report.project_id == Project.id)
        .join(Template, Report.template_id == Template.id)
        .outerjoin(User, Report.created_by == User.id)
        .filter(Report.project_id == project_id)
        .order_by(Report.generated_at.desc())
        .all()
    )
    result = []
    for r, proj_name, tmpl_name, creator_name in reports:
        item = {c.name: getattr(r, c.name) for c in r.__table__.columns}
        item["project_name"] = proj_name
        item["template_name"] = tmpl_name
        item["created_by_name"] = creator_name or ""
        result.append(item)
    return result


@router.get("/{report_id}")
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取报告详情"""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")
    return report


@router.delete("/{report_id}")
def delete_report(
    report_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """删除报告（数据库记录 + 物理文件）"""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    file_name = report.file_name or ""
    file_path = report.file_path or ""

    # 删除物理文件（docx 和同名 pdf）
    for path in {file_path, file_path[:-5] + '.pdf' if file_path.endswith('.docx') else ''}:
        if path and os.path.exists(path):
            try:
                os.remove(path)
            except OSError as e:
                logger.warning(f"删除报告文件失败 {path}: {e}")

    db.delete(report)
    db.commit()

    log_operation(db, current_user.id, current_user.username, "删除报告",
                target_type="report", target_id=report_id,
                detail=f"删除报告: {file_name}", ip_address=request.client.host)
    return {"message": "报告已删除"}


@router.get("/{report_id}/download")
def download_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """下载报告"""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    if not report.file_path or not os.path.exists(report.file_path):
        raise HTTPException(status_code=404, detail="报告文件不存在")

    return FileResponse(
        report.file_path,
        filename=report.file_name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )


@router.get("/{report_id}/preview")
def preview_report(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """预览报告内容（返回文本格式）"""
    from docx import Document

    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    if report.status != "generated":
        raise HTTPException(status_code=400, detail="报告尚未生成完成")

    if not report.file_path or not os.path.exists(report.file_path):
        raise HTTPException(status_code=404, detail="报告文件不存在")

    try:
        doc = Document(report.file_path)
        content_parts = [para.text for para in doc.paragraphs if para.text.strip()]
        content = "\n\n".join(content_parts)

        return {
            "report_id": report_id,
            "file_name": report.file_name,
            "content": content
        }
    except Exception as e:
        logger.error(f"预览报告失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="预览报告失败")


@router.get("/{report_id}/fill-result")
def get_fill_result(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取报告生成的填充结果详情"""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    if report.status == "generating":
        return {
            "report_id": report_id,
            "status": "generating",
            "fill_report": None,
            "message": "报告正在生成中"
        }

    if report.status == "failed":
        return {
            "report_id": report_id,
            "status": "failed",
            "fill_report": report.fill_report,
            "message": "报告生成失败"
        }

    return {
        "report_id": report_id,
        "status": report.status,
        "fill_report": report.fill_report,
        "message": "报告生成完成"
    }


@router.get("/{report_id}/export-pdf")
def export_report_pdf(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """导出报告为PDF格式（优先使用Word转换，保留完整红头文件样式）"""
    import io
    import subprocess
    import tempfile
    from urllib.parse import quote
    from fastapi.responses import StreamingResponse

    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    if report.status != "generated":
        raise HTTPException(status_code=400, detail="报告尚未生成完成")

    if not report.file_path or not os.path.exists(report.file_path):
        raise HTTPException(status_code=404, detail=f"报告文件不存在: {report.file_path}")

    base_name = report.file_name or f"report_{report_id}"
    pdf_filename = base_name[:-5] + '.pdf' if base_name.endswith('.docx') else base_name + '.pdf'
    docx_path = os.path.abspath(report.file_path)
    pdf_path = os.path.join(os.path.dirname(docx_path), pdf_filename)

    buffer = None

    # 方法1：使用 Word COM 自动化转换（保留完整样式：红头、字体、表格等）
    try:
        vbs_content = (
            'On Error Resume Next\n'
            f'Set word = CreateObject("Word.Application")\n'
            'word.Visible = False\n'
            f'Set doc = word.Documents.Open("{docx_path}")\n'
            'If Err.Number <> 0 Then\n'
            '    word.Quit\n'
            '    WScript.Quit 1\n'
            'End If\n'
            f'doc.SaveAs "{pdf_path}", 17\n'
            'doc.Close\n'
            'word.Quit\n'
            'If Err.Number <> 0 Then WScript.Quit 1\n'
        )

        vbs_fd, vbs_path = tempfile.mkstemp(suffix='.vbs')
        try:
            with os.fdopen(vbs_fd, 'w') as f:
                f.write(vbs_content)
            result = subprocess.run(
                ['cscript', '//nologo', vbs_path],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0 and os.path.exists(pdf_path):
                with open(pdf_path, 'rb') as f:
                    buffer = io.BytesIO(f.read())
                os.remove(pdf_path)
                logger.info(f"Word COM 转换 PDF 成功, report_id={report_id}")
            else:
                logger.warning(f"Word VBS 转换失败: rc={result.returncode}, stderr={result.stderr[:200]}")
        finally:
            if os.path.exists(vbs_path):
                os.remove(vbs_path)
    except Exception as e:
        logger.warning(f"Word COM 转换异常，将使用 reportlab 回退: {e}")

    # 方法2：reportlab 回退（不保留完整样式，仅含文本和表格）
    if buffer is None:
        try:
            from docx import Document
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.lib import colors
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
            from reportlab.pdfbase import pdfmetrics

            docx_doc = Document(report.file_path)

            font_name = 'Helvetica'
            for fp in ["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simsun.ttc"]:
                if os.path.exists(fp):
                    try:
                        from reportlab.pdfbase.ttfonts import TTFont
                        pdfmetrics.registerFont(TTFont('ChineseFont', fp))
                        font_name = 'ChineseFont'
                        break
                    except Exception:
                        continue
            if font_name == 'Helvetica':
                try:
                    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
                    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
                    font_name = 'STSong-Light'
                except Exception:
                    pass

            buffer = io.BytesIO()
            pdf_doc = SimpleDocTemplate(
                buffer, pagesize=A4,
                leftMargin=25*mm, rightMargin=25*mm,
                topMargin=25*mm, bottomMargin=25*mm,
            )
            title_style = ParagraphStyle('Title', fontName=font_name, fontSize=18, alignment=1, spaceAfter=12, leading=26)
            heading_style = ParagraphStyle('Heading', fontName=font_name, fontSize=13, spaceBefore=8, spaceAfter=4, leading=20)
            body_style = ParagraphStyle('Body', fontName=font_name, fontSize=10.5, leading=18, firstLineIndent=21)
            cell_style = ParagraphStyle('Cell', fontName=font_name, fontSize=9, leading=13)

            story = []
            first_text = docx_doc.paragraphs[0].text.strip() if docx_doc.paragraphs else ''
            for para in docx_doc.paragraphs:
                text = para.text.strip()
                if not text:
                    story.append(Spacer(1, 4))
                    continue
                style_name = para.style.name if para.style else ''
                if 'Title' in style_name or text == first_text:
                    story.append(Paragraph(text, title_style))
                elif style_name.startswith('Heading'):
                    story.append(Paragraph(text, heading_style))
                else:
                    story.append(Paragraph(text, body_style))

            for table in docx_doc.tables:
                data = []
                for row in table.rows:
                    cells = []
                    for cell in row.cells:
                        cell_text = cell.text.strip()
                        cells.append(Paragraph(cell_text, cell_style) if cell_text else '')
                    data.append(cells)
                if data:
                    col_count = max(len(r) for r in data)
                    col_width = (A4[0] - 50*mm) / col_count
                    t = Table(data, colWidths=[col_width]*col_count, repeatRows=1)
                    t.setStyle(TableStyle([
                        ('FONTNAME', (0, 0), (-1, -1), font_name),
                        ('FONTSIZE', (0, 0), (-1, -1), 9),
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#4472C4')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#8EA9DB')),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#E9EFF7')]),
                        ('TOPPADDING', (0, 0), (-1, -1), 4),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ]))
                    story.append(Spacer(1, 6))
                    story.append(t)
                    story.append(Spacer(1, 6))

            pdf_doc.build(story)
            buffer.seek(0)
            logger.info(f"reportlab 回退生成 PDF, report_id={report_id}")
        except Exception as e:
            logger.error(f"reportlab 回退也失败: {e}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"导出PDF失败: {str(e)}")

    encoded_filename = quote(pdf_filename)
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=report_{report_id}.pdf; filename*=UTF-8''{encoded_filename}"}
    )


@router.put("/{report_id}/review")
def review_report(
    report_id: int,
    review_data: ReviewRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """审核报告"""
    from models import _utcnow

    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    if review_data.review_status not in ["reviewing", "approved", "rejected"]:
        raise HTTPException(status_code=400, detail="无效的审核状态")

    report.review_status = review_data.review_status
    report.review_comment = review_data.review_comment or ""
    report.reviewed_at = _utcnow()
    report.reviewer_id = current_user.id

    db.commit()
    db.refresh(report)
    log_operation(db, current_user.id, current_user.username, "审核报告",
                target_type="report", target_id=report_id,
                detail=f"审核状态: {review_data.review_status}", ip_address=request.client.host)

    return {
        "id": report.id,
        "report_number": report.report_number,
        "review_status": report.review_status,
        "review_comment": report.review_comment,
        "reviewed_at": report.reviewed_at
    }


@router.get("/{report_id}/review-history")
def get_review_history(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """获取报告审核历史"""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    return {
        "id": report.id,
        "report_number": report.report_number,
        "review_status": report.review_status,
        "review_comment": report.review_comment,
        "reviewed_at": report.reviewed_at
    }


@router.post("/{report_id}/new-version", response_model=ReportResponse)
def create_new_version(
    report_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """基于已有报告创建新版本：用项目当前 Excel 数据重新生成，版本号+1"""
    from models import _utcnow
    from sqlalchemy.orm import joinedload

    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    if report.status != "generated":
        raise HTTPException(status_code=400, detail="源报告尚未生成完成")

    project = db.query(Project).filter(Project.id == report.project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="项目不存在")

    template = db.query(Template).filter(Template.id == report.template_id).first()
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    # 获取项目当前 Excel 数据（可能是更新后的数据）
    excel_files = db.query(ExcelFile).options(
        joinedload(ExcelFile.data_items)
    ).filter(ExcelFile.project_id == project.id).all()

    if not excel_files:
        raise HTTPException(status_code=400, detail="项目没有 Excel 数据，无法生成新版本")

    all_data = {}
    for excel_file in excel_files:
        all_data[excel_file.engineering_type] = {
            "items": [
                {
                    "name": item.item_name,
                    "unit": item.unit,
                    "submitted_qty": item.submitted_qty,
                    "submitted_price": item.submitted_price,
                    "submitted_total": item.submitted_total,
                    "audited_qty": item.audited_qty,
                    "audited_price": item.audited_price,
                    "audited_total": item.audited_total,
                    "adjustment": item.adjustment
                }
                for item in excel_file.data_items
            ]
        }

    # 计算新版本号：基于同根版本的最大版本号
    root_id = report.parent_report_id or report.id
    max_version = db.query(Report).filter(
        (Report.id == root_id) | (Report.parent_report_id == root_id)
    ).order_by(Report.version.desc()).first()
    new_version = (max_version.version + 1) if max_version else (report.version + 1)

    # 生成新文件名和路径
    base, ext = os.path.splitext(report.file_name or "report.docx")
    # 去掉旧的 _vN 后缀
    import re
    base = re.sub(r'_v\d+$', '', base)
    new_filename = f"{base}_v{new_version}{ext}"
    new_path = os.path.join(OUTPUT_DIR, new_filename)

    # 用当前数据重新生成报告（同步执行，保证版本内容真实更新）
    # 复用原报告的 section_totals（措施/其他/规费/税金/附加税 汇总数据）
    prev_fill = report.fill_report if isinstance(report.fill_report, dict) else {}
    prev_section_totals = prev_fill.get("section_totals") or None

    try:
        fill_result = generate_review_report(
            template_path=template.file_path,
            output_path=new_path,
            project_data=all_data,
            project_name=project.name,
            client_name=project.client_name or "",
            project_type=project.project_type or "",
            project_id=project.id,
            report_number=report.report_number,
            section_totals=prev_section_totals
        )
    except Exception as e:
        logger.error(f"新版本生成失败 report_id={report_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"新版本生成失败: {e}")

    new_report = Report(
        project_id=project.id,
        template_id=template.id,
        file_name=new_filename,
        file_path=new_path,
        status="generated",
        generated_at=_utcnow(),
        report_number=report.report_number,
        review_status="draft",
        version=new_version,
        parent_report_id=root_id,
        fill_report=fill_result,
        created_by=current_user.id
    )
    db.add(new_report)
    db.commit()
    db.refresh(new_report)

    logger.info(f"报告新版本创建: {report_id} -> v{new_version}, 用户: {getattr(current_user, 'username', 'unknown')}")
    log_operation(db, current_user.id, current_user.username, "创建报告新版本",
                target_type="report", target_id=new_report.id,
                detail=f"基于报告 {report_id} 创建新版本 v{new_version}", ip_address=request.client.host)
    return new_report


@router.get("/{report_id}/versions", response_model=List[ReportResponse])
def get_report_versions(
    report_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """获取报告的所有版本"""
    report = db.query(Report).filter(Report.id == report_id).first()
    if not report:
        raise HTTPException(status_code=404, detail="报告不存在")

    root_id = report.parent_report_id or report.id
    versions = db.query(Report).filter(
        (Report.id == root_id) | (Report.parent_report_id == root_id)
    ).order_by(Report.version.asc()).all()
    return versions


@router.get("/{report_id}/compare/{other_id}")
def compare_reports(
    report_id: int,
    other_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """对比两个版本报告的内容差异"""
    from docx import Document
    import difflib

    r1 = db.query(Report).filter(Report.id == report_id).first()
    r2 = db.query(Report).filter(Report.id == other_id).first()
    if not r1 or not r2:
        raise HTTPException(status_code=404, detail="报告不存在")

    if not (r1.file_path and os.path.exists(r1.file_path)):
        raise HTTPException(status_code=400, detail=f"报告 {report_id} 文件不存在")
    if not (r2.file_path and os.path.exists(r2.file_path)):
        raise HTTPException(status_code=400, detail=f"报告 {other_id} 文件不存在")

    try:
        doc1 = Document(r1.file_path)
        doc2 = Document(r2.file_path)

        lines1 = [p.text for p in doc1.paragraphs if p.text.strip()]
        lines2 = [p.text for p in doc2.paragraphs if p.text.strip()]

        differ = difflib.unified_diff(lines1, lines2, fromfile=f"v{r1.version}", tofile=f"v{r2.version}", lineterm="")
        diff_text = "\n".join(differ)

        return {
            "report1": {"id": r1.id, "version": r1.version, "filename": r1.file_name},
            "report2": {"id": r2.id, "version": r2.version, "filename": r2.file_name},
            "diff": diff_text if diff_text else "两个版本内容完全一致",
            "lines1_count": len(lines1),
            "lines2_count": len(lines2),
        }
    except Exception as e:
        logger.error(f"报告对比失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="报告对比失败")
