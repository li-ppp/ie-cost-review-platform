"""
数据库模型
"""

from sqlalchemy import Column, Integer, String, DateTime, JSON, Float, ForeignKey, Index, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone, timedelta
from database import Base


def _utcnow():
    """返回北京时间（UTC+8）"""
    beijing_tz = timezone(timedelta(hours=8))
    return datetime.now(beijing_tz)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(100))
    role = Column(String(20), default="user")
    created_at = Column(DateTime, default=_utcnow)


class OperationLog(Base):
    __tablename__ = "operation_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    username = Column(String(50))
    action = Column(String(50), nullable=False)
    target_type = Column(String(50))
    target_id = Column(Integer)
    detail = Column(Text)
    ip_address = Column(String(50))
    created_at = Column(DateTime, default=_utcnow)

    __table_args__ = (
        Index("ix_operation_logs_user_id", "user_id"),
        Index("ix_operation_logs_created_at", "created_at"),
    )


class SystemSetting(Base):
    __tablename__ = "system_settings"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(Text)
    description = Column(String(200))
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    client_name = Column(String(200), index=True)
    project_type = Column(String(50), index=True)
    status = Column(String(20), default="draft", index=True)
    created_at = Column(DateTime, default=_utcnow, index=True)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow, index=True)

    excel_files = relationship("ExcelFile", back_populates="project", cascade="all, delete-orphan")
    reports = relationship("Report", back_populates="project", cascade="all, delete-orphan")


class ExcelFile(Base):
    __tablename__ = "excel_files"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    engineering_type = Column(String(50))
    upload_time = Column(DateTime, default=_utcnow)

    project = relationship("Project", back_populates="excel_files")
    data_items = relationship("ExcelData", back_populates="excel_file", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_excel_files_project_id", "project_id"),
    )


class ExcelData(Base):
    __tablename__ = "excel_data"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("excel_files.id"), nullable=False)
    item_name = Column(String(500))
    unit = Column(String(20))
    submitted_qty = Column(Float)
    submitted_price = Column(Float)
    submitted_total = Column(Float)
    audited_qty = Column(Float)
    audited_price = Column(Float)
    audited_total = Column(Float)
    adjustment = Column(Float)
    row_index = Column(Integer)

    excel_file = relationship("ExcelFile", back_populates="data_items")

    __table_args__ = (
        Index("ix_excel_data_file_id", "file_id"),
    )


class Template(Base):
    __tablename__ = "templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    template_type = Column(String(50))
    file_path = Column(String(500), nullable=False)
    variables = Column(JSON, default=dict)
    created_at = Column(DateTime, default=_utcnow)

    reports = relationship("Report", back_populates="template")


class Report(Base):
    __tablename__ = "reports"

    id = Column(Integer, primary_key=True, index=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)
    template_id = Column(Integer, ForeignKey("templates.id"), nullable=False, index=True)
    file_name = Column(String(255))
    file_path = Column(String(500))
    status = Column(String(20), default="generated", index=True)
    generated_at = Column(DateTime, default=_utcnow, index=True)

    # 报告编号
    report_number = Column(String(50), index=True)

    # 审核流程字段
    review_status = Column(String(20), default="draft", index=True)  # draft/reviewing/approved/rejected
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    review_comment = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)

    # 版本管理字段
    version = Column(Integer, default=1)
    parent_report_id = Column(Integer, ForeignKey("reports.id"), nullable=True)

    # 填充结果报告（JSON）
    fill_report = Column(JSON, nullable=True)

    # 生成人（上传人）
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)

    project = relationship("Project", back_populates="reports")
    template = relationship("Template", back_populates="reports")


class BackupRecord(Base):
    """数据备份记录"""
    __tablename__ = "backup_records"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, default=0)  # 字节
    description = Column(String(500))
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=_utcnow, index=True)


class DataDictionary(Base):
    """数据字典"""
    __tablename__ = "data_dictionary"

    id = Column(Integer, primary_key=True, index=True)
    category = Column(String(50), nullable=False, index=True)  # engineering_type/unit/status
    code = Column(String(50), nullable=False)
    name = Column(String(100), nullable=False)
    description = Column(String(200))
    sort_order = Column(Integer, default=0)
