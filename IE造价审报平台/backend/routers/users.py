"""
用户管理路由（仅管理员）
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import Optional

from database import get_db
from models import User, Report, OperationLog
from schemas import UserResponse
from auth import get_current_user, require_admin, get_password_hash
from routers.logs import log_operation

router = APIRouter()

DEFAULT_RESET_PASSWORD = "123456"


@router.get("/")
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """获取所有员工列表及总数（仅管理员）"""
    users = db.query(User).order_by(User.id.asc()).all()
    items = []
    for u in users:
        items.append({
            "id": u.id,
            "username": u.username,
            "display_name": u.display_name or "",
            "role": u.role,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        })
    return {"total": len(items), "items": items}


@router.post("/", response_model=UserResponse)
def create_user(
    data: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """管理员新增员工（默认密码 123456）"""
    username = (data.get("username") or "").strip()
    if not username or len(username) < 2:
        raise HTTPException(status_code=400, detail="用户名至少 2 个字符")

    existing = db.query(User).filter(User.username == username).first()
    if existing:
        raise HTTPException(status_code=400, detail="用户名已存在")

    raw_password = data.get("password") or DEFAULT_RESET_PASSWORD
    if len(raw_password) < 6:
        raise HTTPException(status_code=400, detail="密码长度不能少于 6 个字符")

    display_name = (data.get("display_name") or "").strip() or username

    new_user = User(
        username=username,
        password_hash=get_password_hash(raw_password),
        display_name=display_name,
        role="user",
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    log_operation(db, current_user.id, current_user.username, "新增员工",
                  target_type="user", target_id=new_user.id,
                  detail=f"新增员工: {new_user.username}", ip_address=request.client.host)
    return new_user


@router.post("/{user_id}/reset-password")
def reset_password(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """重置员工密码为 123456（仅管理员）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="不能重置管理员密码")

    user.password_hash = get_password_hash(DEFAULT_RESET_PASSWORD)
    db.commit()

    log_operation(db, current_user.id, current_user.username, "重置密码",
                  target_type="user", target_id=user.id,
                  detail=f"重置员工密码: {user.username}", ip_address=request.client.host)
    return {"message": f"密码已重置为 {DEFAULT_RESET_PASSWORD}", "username": user.username}


@router.delete("/{user_id}")
def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """删除员工（仅管理员，不能删除自己和管理员账号）"""
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    if user.id == current_user.id:
        raise HTTPException(status_code=400, detail="不能删除当前登录账号")
    if user.role == "admin":
        raise HTTPException(status_code=400, detail="不能删除管理员账号")

    # 检查是否有关联报告（创建人或审核人）
    report_count = db.query(Report).filter(
        (Report.created_by == user_id) | (Report.reviewer_id == user_id)
    ).count()
    if report_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"该员工关联 {report_count} 个报告（创建或审核），无法删除。请先处理相关报告。"
        )

    username = user.username
    # 操作日志的 user_id 设为 NULL（保留日志历史，仅断开关联）
    db.query(OperationLog).filter(OperationLog.user_id == user_id).update(
        {OperationLog.user_id: None}, synchronize_session=False
    )
    db.delete(user)
    db.commit()

    log_operation(db, current_user.id, current_user.username, "删除员工",
                  target_type="user", target_id=user_id,
                  detail=f"删除员工: {username}", ip_address=request.client.host)
    return {"message": f"已删除员工: {username}"}
