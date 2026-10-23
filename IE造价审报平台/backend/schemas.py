"""
Pydantic数据模型
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


# 用户认证相关
class UserBase(BaseModel):
    username: str = Field(..., min_length=2, max_length=50)
    display_name: Optional[str] = Field(None, max_length=100)


class UserCreate(UserBase):
    password: str = Field(..., min_length=6)


class UserLogin(BaseModel):
    username: str
    password: str


class UserResponse(UserBase):
    id: int
    role: str
    created_at: datetime

    class Config:
        from_attributes = True


class Token(BaseModel):
    access_token: str
    token_type: str


class TokenData(BaseModel):
    user_id: Optional[int] = None
    username: Optional[str] = None


# 操作日志相关
class OperationLogResponse(BaseModel):
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    target_type: Optional[str] = None
    target_id: Optional[int] = None
    detail: Optional[str] = None
    ip_address: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


# 系统设置相关
class SystemSettingBase(BaseModel):
    key: str = Field(..., max_length=100)
    value: Optional[str] = None
    description: Optional[str] = Field(None, max_length=200)


class SystemSettingCreate(SystemSettingBase):
    pass


class SystemSettingResponse(SystemSettingBase):
    id: int
    updated_at: datetime

    class Config:
        from_attributes = True


# 项目相关
class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=200, description="项目名称")
    client_name: Optional[str] = Field(None, max_length=200, description="客户名称")
    project_type: Optional[str] = Field(None, max_length=100, description="项目类型")
    status: Optional[str] = Field("draft", pattern="^(draft|in_progress|completed|archived)$", description="项目状态")

    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v):
        if not v.strip():
            raise ValueError('项目名称不能为空')
        return v.strip()


class ProjectCreate(ProjectBase):
    pass


class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=200)
    client_name: Optional[str] = Field(None, max_length=200)
    project_type: Optional[str] = Field(None, max_length=100)
    status: Optional[str] = Field(None, pattern="^(draft|in_progress|completed|archived)$")

    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v):
        if v is not None and not v.strip():
            raise ValueError('项目名称不能为空')
        return v.strip() if v else v


class ProjectResponse(ProjectBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# Excel数据相关
class ExcelDataResponse(BaseModel):
    id: int
    item_name: Optional[str] = None
    unit: Optional[str] = None
    submitted_qty: Optional[float] = None
    submitted_price: Optional[float] = None
    submitted_total: Optional[float] = None
    audited_qty: Optional[float] = None
    audited_price: Optional[float] = None
    audited_total: Optional[float] = None
    adjustment: Optional[float] = None
    row_index: Optional[int] = None

    class Config:
        from_attributes = True


class ExcelFileResponse(BaseModel):
    id: int
    file_name: str
    engineering_type: Optional[str] = None
    upload_time: datetime
    data_items: List[ExcelDataResponse] = []

    class Config:
        from_attributes = True


# 模板相关
class TemplateBase(BaseModel):
    name: str
    template_type: Optional[str] = None


class TemplateCreate(TemplateBase):
    pass


class TemplateResponse(TemplateBase):
    id: int
    file_path: str
    variables: Optional[dict] = None
    created_at: datetime

    class Config:
        from_attributes = True


# 报告相关
class ReportBase(BaseModel):
    project_id: int
    template_id: int


class ReportCreate(ReportBase):
    pass


class ReportResponse(ReportBase):
    id: int
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    status: str
    generated_at: datetime
    report_number: Optional[str] = None
    review_status: Optional[str] = None
    reviewer_id: Optional[int] = None
    review_comment: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    version: Optional[int] = 1
    parent_report_id: Optional[int] = None
    fill_report: Optional[dict] = None

    class Config:
        from_attributes = True


# 备份相关
class BackupCreateRequest(BaseModel):
    description: Optional[str] = Field(None, max_length=500)


class BackupResponse(BaseModel):
    id: int
    filename: str
    file_path: str
    file_size: int
    description: Optional[str] = None
    created_by: Optional[int] = None
    created_at: datetime

    class Config:
        from_attributes = True


# 数据字典相关
class DictionaryBase(BaseModel):
    category: str = Field(..., max_length=50, description="字典分类")
    code: str = Field(..., max_length=50, description="编码")
    name: str = Field(..., max_length=100, description="名称")
    description: Optional[str] = Field(None, max_length=200)
    sort_order: Optional[int] = 0


class DictionaryCreate(DictionaryBase):
    pass


class DictionaryUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    description: Optional[str] = Field(None, max_length=200)
    sort_order: Optional[int] = None


class DictionaryResponse(DictionaryBase):
    id: int

    class Config:
        from_attributes = True


# 模板变量配置相关
class TemplateVariableItem(BaseModel):
    placeholder: str  # 如 {{项目名称}}
    field_name: str  # 对应字段
    description: Optional[str] = None
    default_value: Optional[str] = None


class TemplateVariablesUpdate(BaseModel):
    variables: List[TemplateVariableItem]
