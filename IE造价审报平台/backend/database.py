"""
数据库配置
"""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from config import DATA_DIR

DB_PATH = os.path.join(DATA_DIR, "database.db")

SQLALCHEMY_DATABASE_URL = f"sqlite:///{DB_PATH}"

# SQLite 优化配置
# SQLite 是单文件数据库，不需要连接池参数
# 使用 StaticPool 确保所有连接共享同一个数据库文件
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
    # SQLite 使用 NullPool 或 StaticPool 更合适
    # 这里使用默认配置，通过 PRAGMA 优化性能
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _):
    """配置 SQLite 性能优化参数"""
    cursor = dbapi_conn.cursor()
    # WAL 模式：提升并发读写性能
    cursor.execute("PRAGMA journal_mode=WAL")
    # NORMAL 同步模式：平衡性能和安全
    cursor.execute("PRAGMA synchronous=NORMAL")
    # 缓存大小：8MB（负值表示 KB）
    cursor.execute("PRAGMA cache_size=-8000")
    # 临时表使用内存
    cursor.execute("PRAGMA temp_store=MEMORY")
    # 内存映射：256MB，减少磁盘 IO
    cursor.execute("PRAGMA mmap_size=268435456")
    # 优化查询计划
    cursor.execute("PRAGMA query_only=OFF")
    cursor.close()


class Base(DeclarativeBase):
    pass


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    """数据库会话依赖注入"""
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    else:
        # 仅在会话仍活跃时提交，避免恢复备份等场景主动操作后重复 commit 报错
        try:
            if db.is_active:
                db.commit()
        except Exception:
            try:
                db.rollback()
            except Exception:
                pass
    finally:
        try:
            db.close()
        except Exception:
            pass
