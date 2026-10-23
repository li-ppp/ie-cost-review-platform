"""
数据备份与恢复路由
"""

import os
import shutil
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from database import get_db, SessionLocal, DB_PATH, engine
from models import BackupRecord, User
from schemas import BackupCreateRequest, BackupResponse
from auth import get_current_user, require_admin
from routers.logs import log_operation
from config import DATA_DIR, UPLOADS_DIR

router = APIRouter()
logger = logging.getLogger(__name__)

BACKUP_DIR = os.path.join(DATA_DIR, "backups")
os.makedirs(BACKUP_DIR, exist_ok=True)


def _dir_size(path: str) -> int:
    total = 0
    if not os.path.exists(path):
        return 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                continue
    return total


@router.post("/create", response_model=BackupResponse)
def create_backup(
    req: BackupCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """创建数据备份（数据库文件 + uploads 目录）"""

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{timestamp}"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    try:
        os.makedirs(backup_path, exist_ok=True)

        # 复制数据库文件前先 checkpoint，确保 WAL 中的已提交事务合并到主库
        if os.path.exists(DB_PATH):
            try:
                from sqlalchemy import text as _sql_text
                with engine.connect() as conn:
                    conn.execute(_sql_text("PRAGMA wal_checkpoint(TRUNCATE)"))
            except Exception as ck_err:
                logger.warning(f"WAL checkpoint 失败（继续备份）: {ck_err}")
            shutil.copy2(DB_PATH, os.path.join(backup_path, "database.db"))
            # 同时备份 -wal/-shm 文件（若仍存在）
            for suffix in ("-wal", "-shm"):
                side = DB_PATH + suffix
                if os.path.exists(side):
                    try:
                        shutil.copy2(side, os.path.join(backup_path, f"database.db{suffix}"))
                    except OSError as e:
                        logger.warning(f"复制 {suffix} 文件失败: {e}")

        # 复制 uploads 目录
        if os.path.exists(UPLOADS_DIR):
            shutil.copytree(UPLOADS_DIR, os.path.join(backup_path, "uploads"))

        # 计算备份大小
        size = _dir_size(backup_path)

        # 写入记录
        record = BackupRecord(
            filename=backup_name,
            file_path=backup_path,
            file_size=size,
            description=req.description,
            created_by=getattr(current_user, "id", None),
        )
        db.add(record)
        db.commit()
        db.refresh(record)

        logger.info(f"备份创建成功: {backup_name}, 用户: {current_user.username}")
        log_operation(db, current_user.id, current_user.username, "创建备份",
                    target_type="backup", target_id=record.id,
                    detail=f"备份: {backup_name}, 大小: {size}字节", ip_address=request.client.host)
        return record
    except Exception as e:
        logger.error(f"备份创建失败: {e}", exc_info=True)
        # 清理失败的备份目录
        if os.path.exists(backup_path):
            shutil.rmtree(backup_path, ignore_errors=True)
        raise HTTPException(status_code=500, detail=f"备份创建失败: {str(e)}")


@router.get("/list", response_model=List[BackupResponse])
def list_backups(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """列出所有备份"""
    records = db.query(BackupRecord).order_by(BackupRecord.created_at.desc()).all()
    return records


@router.post("/restore/{backup_id}")
def restore_backup(
    backup_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """从备份恢复数据（危险操作：会覆盖当前数据）"""

    record = db.query(BackupRecord).filter(BackupRecord.id == backup_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="备份记录不存在")

    if not os.path.exists(record.file_path):
        raise HTTPException(status_code=404, detail="备份文件不存在")

    db_backup = os.path.join(record.file_path, "database.db")
    uploads_backup = os.path.join(record.file_path, "uploads")

    # 在关闭会话前记录操作（恢复是危险操作）
    log_operation(db, current_user.id, current_user.username, "恢复备份",
                target_type="backup", target_id=backup_id,
                detail=f"从备份恢复: {record.filename}", ip_address=request.client.host)

    try:
        # 先提交当前会话事务，但不主动 close（由 get_db 依赖注入管理）
        try:
            db.commit()
        except Exception:
            pass

        # 恢复数据库文件：先写入临时文件，成功后原子替换
        if os.path.exists(db_backup):
            # 清理 WAL/SHM 文件
            for suffix in ("-wal", "-shm"):
                side = DB_PATH + suffix
                if os.path.exists(side):
                    try:
                        os.remove(side)
                    except OSError:
                        pass
            tmp_db = DB_PATH + ".restore_tmp"
            shutil.copy2(db_backup, tmp_db)
            # Windows 下 os.replace 可原子替换
            os.replace(tmp_db, DB_PATH)

        # 恢复 uploads 目录：先复制到临时目录，成功后替换旧目录
        if os.path.exists(uploads_backup):
            tmp_uploads = UPLOADS_DIR + ".restore_tmp"
            # 清理可能残留的临时目录
            if os.path.exists(tmp_uploads):
                shutil.rmtree(tmp_uploads, ignore_errors=True)
            shutil.copytree(uploads_backup, tmp_uploads)
            # 替换旧目录
            old_uploads = UPLOADS_DIR + ".old"
            if os.path.exists(UPLOADS_DIR):
                os.replace(UPLOADS_DIR, old_uploads)
            os.replace(tmp_uploads, UPLOADS_DIR)
            # 删除旧目录
            if os.path.exists(old_uploads):
                shutil.rmtree(old_uploads, ignore_errors=True)

        logger.warning(f"数据已从备份 {record.filename} 恢复, 用户: {current_user.username}")
        return {"message": "数据恢复成功，建议重启服务"}
    except Exception as e:
        logger.error(f"备份恢复失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"恢复失败: {str(e)}")


@router.delete("/{backup_id}")
def delete_backup(
    backup_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """删除备份"""

    record = db.query(BackupRecord).filter(BackupRecord.id == backup_id).first()
    if not record:
        raise HTTPException(status_code=404, detail="备份记录不存在")

    # 删除物理文件
    if record.file_path and os.path.exists(record.file_path):
        try:
            shutil.rmtree(record.file_path)
        except OSError as e:
            logger.warning(f"删除备份文件失败 {record.file_path}: {e}")

    db.delete(record)
    db.commit()
    logger.info(f"备份已删除: {record.filename}, 用户: {current_user.username}")
    log_operation(db, current_user.id, current_user.username, "删除备份",
                target_type="backup", target_id=backup_id,
                detail=f"删除备份: {record.filename}", ip_address=request.client.host)
    return {"message": "备份已删除"}
