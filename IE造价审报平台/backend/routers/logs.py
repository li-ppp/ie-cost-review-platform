"""
操作日志路由
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List
from database import get_db
from models import OperationLog, User
from schemas import OperationLogResponse
from auth import get_current_user, require_admin

router = APIRouter()


def log_operation(
    db: Session,
    user_id: int,
    username: str,
    action: str,
    target_type: str = None,
    target_id: int = None,
    detail: str = None,
    ip_address: str = None,
):
    """记录操作日志"""
    log_entry = OperationLog(
        user_id=user_id,
        username=username,
        action=action,
        target_type=target_type,
        target_id=target_id,
        detail=detail,
        ip_address=ip_address,
    )
    db.add(log_entry)
    db.commit()


@router.get("/")
async def get_operation_logs(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """获取操作日志列表（仅管理员）"""
    query = db.query(OperationLog).order_by(OperationLog.created_at.desc())
    total = query.count()
    logs = query.offset(skip).limit(limit).all()
    return {"total": total, "items": logs}
