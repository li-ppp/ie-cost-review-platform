"""
系统设置路由
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List, Dict
from database import get_db
from models import SystemSetting, User
from schemas import SystemSettingCreate, SystemSettingResponse
from auth import get_current_user, require_admin

router = APIRouter()

# 系统设置缓存
_settings_cache: Dict[str, str] = {}
_cache_initialized = False


def _refresh_cache(db: Session):
    """刷新缓存"""
    global _settings_cache, _cache_initialized
    settings = db.query(SystemSetting).all()
    _settings_cache = {s.key: s.value for s in settings}
    _cache_initialized = True


def get_setting_value(key: str, default: str = '', db: Session = None) -> str:
    """获取设置值（带缓存）"""
    global _cache_initialized
    if not _cache_initialized and db:
        _refresh_cache(db)
    return _settings_cache.get(key, default)


@router.get("/", response_model=List[SystemSettingResponse])
async def get_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """获取所有系统设置（仅管理员）"""
    settings = db.query(SystemSetting).all()
    # 刷新缓存
    _refresh_cache(db)
    return settings


@router.get("/{key}", response_model=SystemSettingResponse)
async def get_setting(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """获取指定设置项（仅管理员）"""
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"设置项 '{key}' 不存在",
        )
    return setting


@router.put("/{key}", response_model=SystemSettingResponse)
async def update_setting(
    key: str,
    setting_data: SystemSettingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """更新设置项（仅管理员）"""
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        # 创建新设置项
        setting = SystemSetting(
            key=key,
            value=setting_data.value,
            description=setting_data.description,
        )
        db.add(setting)
    else:
        # 更新现有设置项
        setting.value = setting_data.value
        if setting_data.description is not None:
            setting.description = setting_data.description

    db.commit()
    db.refresh(setting)

    # 刷新缓存
    _refresh_cache(db)

    return setting


@router.delete("/{key}")
async def delete_setting(
    key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """删除设置项（仅管理员）"""
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"设置项 '{key}' 不存在",
        )

    db.delete(setting)
    db.commit()
    # 刷新缓存，避免 get_setting_value 返回已删除的值
    _refresh_cache(db)
    return {"message": f"设置项 '{key}' 已删除"}


def init_default_settings(db: Session):
    """初始化默认系统设置"""
    default_settings = [
        {
            "key": "company_name",
            "value": "IE工程造价咨询公司",
            "description": "公司名称",
        },
        {
            "key": "report_title_prefix",
            "value": "工程造价评审报告",
            "description": "报告标题前缀",
        },
        {
            "key": "max_upload_size_mb",
            "value": "10",
            "description": "最大上传文件大小(MB)",
        },
        {
            "key": "supported_engineering_types",
            "value": "道路工程,排水工程,交安工程,桥涵工程,照明工程,电力工程,通信工程",
            "description": "支持的工程类型（逗号分隔）",
        },
    ]

    for setting_data in default_settings:
        existing = db.query(SystemSetting).filter(SystemSetting.key == setting_data["key"]).first()
        if not existing:
            setting = SystemSetting(**setting_data)
            db.add(setting)

    db.commit()
