"""
数据字典管理路由
"""

import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Request
from sqlalchemy.orm import Session

from database import get_db
from models import DataDictionary, User
from schemas import DictionaryCreate, DictionaryUpdate, DictionaryResponse
from auth import get_current_user, require_admin
from routers.logs import log_operation

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_LIMIT = 500


@router.get("/", response_model=List[DictionaryResponse])
def list_dictionary(
    category: Optional[str] = Query(None, description="按分类筛选"),
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """获取数据字典列表（仅管理员）"""
    if skip < 0:
        skip = 0
    limit = max(1, min(limit, MAX_LIMIT))

    query = db.query(DataDictionary)
    if category:
        query = query.filter(DataDictionary.category == category)
    items = query.order_by(
        DataDictionary.category.asc(),
        DataDictionary.sort_order.asc(),
        DataDictionary.id.asc(),
    ).offset(skip).limit(limit).all()
    return items


@router.get("/categories")
def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """获取所有字典分类（仅管理员）"""
    rows = db.query(DataDictionary.category).distinct().all()
    return [r[0] for r in rows]


@router.post("/", response_model=DictionaryResponse)
def create_dictionary(
    data: DictionaryCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """创建字典项（仅管理员）"""
    existing = db.query(DataDictionary).filter(
        DataDictionary.category == data.category,
        DataDictionary.code == data.code,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail=f"分类 '{data.category}' 下已存在编码 '{data.code}'")

    item = DataDictionary(**data.dict())
    db.add(item)
    db.commit()
    db.refresh(item)
    logger.info(f"字典项创建: {data.category}/{data.code}, 用户: {current_user.username}")
    log_operation(db, current_user.id, current_user.username, "创建字典项",
                target_type="dictionary", target_id=item.id,
                detail=f"字典: {data.category}/{data.code}", ip_address=request.client.host)
    return item


@router.put("/{item_id}", response_model=DictionaryResponse)
def update_dictionary(
    item_id: int,
    data: DictionaryUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """更新字典项（仅管理员）"""
    item = db.query(DataDictionary).filter(DataDictionary.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="字典项不存在")

    update_data = data.dict(exclude_unset=True)
    for k, v in update_data.items():
        setattr(item, k, v)

    db.commit()
    db.refresh(item)
    log_operation(db, current_user.id, current_user.username, "更新字典项",
                target_type="dictionary", target_id=item_id,
                detail=f"字典: {item.category}/{item.code}", ip_address=request.client.host)
    return item


@router.delete("/{item_id}")
def delete_dictionary(
    item_id: int,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """删除字典项（仅管理员）"""
    item = db.query(DataDictionary).filter(DataDictionary.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="字典项不存在")

    db.delete(item)
    db.commit()
    logger.info(f"字典项删除: {item.category}/{item.code}, 用户: {current_user.username}")
    log_operation(db, current_user.id, current_user.username, "删除字典项",
                target_type="dictionary", target_id=item_id,
                detail=f"字典: {item.category}/{item.code}", ip_address=request.client.host)
    return {"message": "字典项已删除"}


def init_default_dictionary(db: Session) -> None:
    """初始化默认字典数据"""
    defaults = [
        # 工程类型
        ("engineering_type", "road", "道路工程", "道路、市政道路", 1),
        ("engineering_type", "drainage", "排水工程", "排水、雨污水、给排水", 2),
        ("engineering_type", "traffic_safety", "交安工程", "交通安全、交安", 3),
        ("engineering_type", "bridge", "桥涵工程", "桥梁、桥涵", 4),
        ("engineering_type", "lighting", "照明工程", "照明、路灯", 5),
        ("engineering_type", "power", "电力工程", "电力、电气、供电", 6),
        ("engineering_type", "communication", "通信工程", "通信、弱电、管线", 7),
        # 单位
        ("unit", "m", "米", "长度单位", 1),
        ("unit", "m2", "平方米", "面积单位", 2),
        ("unit", "m3", "立方米", "体积单位", 3),
        ("unit", "t", "吨", "质量单位", 4),
        ("unit", "kg", "千克", "质量单位", 5),
        ("unit", "set", "套", "成套设备", 6),
        ("unit", "zuo", "座", "座数单位", 7),
        ("unit", "xiang", "项", "项目单位", 8),
        ("unit", "ge", "个", "数量单位", 9),
        # 项目状态
        ("status", "draft", "草稿", "新建未开始", 1),
        ("status", "in_progress", "进行中", "项目进行中", 2),
        ("status", "completed", "已完成", "项目已完成", 3),
        ("status", "archived", "已归档", "项目已归档", 4),
    ]

    for category, code, name, desc, sort in defaults:
        existing = db.query(DataDictionary).filter(
            DataDictionary.category == category,
            DataDictionary.code == code,
        ).first()
        if not existing:
            db.add(DataDictionary(
                category=category, code=code, name=name,
                description=desc, sort_order=sort,
            ))
    db.commit()
