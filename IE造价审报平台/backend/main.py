"""
IE工程造价审报自动生成平台 - 后端主入口
"""
import sys
import os
import io

# --windowed 模式下 sys.stdout 为 None，uvicorn 日志会崩溃
# 必须在所有 import 之前重定向
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

# 确保 backend 目录在 sys.path 中（支持 PyInstaller 打包）
_backend_dir = os.path.dirname(os.path.abspath(__file__))
if _backend_dir not in sys.path:
    sys.path.insert(0, _backend_dir)

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, FileResponse
from routers import projects, templates, reports, auth, logs, settings, backup, dictionary, users
from database import engine, Base, SessionLocal
from config import LOGS_DIR, UPLOADS_DIR, RESOURCES_DIR
from auth import create_default_admin
from routers.settings import init_default_settings
from routers.dictionary import init_default_dictionary
import logging
from logging.handlers import RotatingFileHandler
from collections import OrderedDict

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        RotatingFileHandler(
            os.path.join(LOGS_DIR, "app.log"),
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        ),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 创建数据库表
Base.metadata.create_all(bind=engine)

# 数据库迁移：为已有表添加缺失的列
def migrate_database():
    """检查并添加缺失的数据库列"""
    import sqlite3
    from config import DATA_DIR
    
    db_path = os.path.join(DATA_DIR, "database.db")
    if not os.path.exists(db_path):
        logger.info(f"数据库文件不存在，跳过迁移: {db_path}")
        return
    
    logger.info(f"开始数据库迁移: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 检查 reports 表的列
    cursor.execute("PRAGMA table_info(reports)")
    existing_columns = {row[1] for row in cursor.fetchall()}
    logger.info(f"reports 表现有列: {existing_columns}")
    
    # 需要添加的列
    columns_to_add = [
        ("report_number", "VARCHAR(50)"),
        ("review_status", "VARCHAR(20)"),
        ("reviewer_id", "INTEGER"),
        ("review_comment", "TEXT"),
        ("reviewed_at", "DATETIME"),
        ("version", "INTEGER DEFAULT 1"),
        ("parent_report_id", "INTEGER"),
        ("fill_report", "JSON"),
        ("created_by", "INTEGER"),
    ]

    for col_name, col_type in columns_to_add:
        if col_name not in existing_columns:
            try:
                cursor.execute(f"ALTER TABLE reports ADD COLUMN {col_name} {col_type}")
                logger.info(f"已添加列: reports.{col_name}")
            except sqlite3.OperationalError as e:
                logger.warning(f"添加列 {col_name} 失败: {e}")

    conn.commit()
    conn.close()
    logger.info("数据库迁移完成")

migrate_database()

# 初始化默认管理员和系统设置
db = SessionLocal()
try:
    create_default_admin(db)
    init_default_settings(db)
    init_default_dictionary(db)
finally:
    db.close()

app = FastAPI(
    title="IE工程造价审报自动生成平台",
    description="自动化工程造价评审报告生成系统",
    version="1.0.0"
)

# 全局异常处理器（保留 HTTPException 的状态码和详情）
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    if isinstance(exc, HTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )
    logger.error(f"未处理的异常: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误，请稍后重试"}
    )

# 配置GZip压缩（对大于1KB的响应进行压缩）
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 配置CORS（可通过环境变量 CORS_ORIGINS 配置，逗号分隔）
_cors_env = os.environ.get("CORS_ORIGINS", "")
if _cors_env:
    _cors_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
else:
    _cors_origins = ["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 挂载静态文件目录
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")

# 注册路由
app.include_router(auth.router, prefix="/api/auth", tags=["用户认证"])
app.include_router(projects.router, prefix="/api/projects", tags=["项目管理"])
app.include_router(templates.router, prefix="/api/templates", tags=["模板管理"])
app.include_router(reports.router, prefix="/api/reports", tags=["报告生成"])
app.include_router(logs.router, prefix="/api/logs", tags=["操作日志"])
app.include_router(settings.router, prefix="/api/settings", tags=["系统设置"])
app.include_router(backup.router, prefix="/api/backup", tags=["数据备份"])
app.include_router(dictionary.router, prefix="/api/dictionary", tags=["数据字典"])
app.include_router(users.router, prefix="/api/users", tags=["账号管理"])


@app.get("/api/health")
def health_check():
    return {"status": "healthy"}


# 前端静态文件目录（运行时查找）
frontend_dist = os.path.join(RESOURCES_DIR, "frontend", "dist")
logger.info(f"RESOURCES_DIR: {RESOURCES_DIR}")
logger.info(f"frontend_dist: {frontend_dist}")
logger.info(f"frontend_dist exists: {os.path.exists(frontend_dist)}")

# 前端文件路径缓存（LRU，避免内存无限增长）
_FRONTEND_CACHE_MAX = 256
_frontend_cache: "OrderedDict[str, str | None]" = OrderedDict()

# 始终注册 SPA catch-all 路由，在请求时动态查找前端文件
@app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
async def spa_catch_all(full_path: str):
    # 减少日志输出，提升性能
    if full_path.startswith("api/") or full_path.startswith("uploads/"):
        return JSONResponse(status_code=404, content={"detail": "Not found"})

    # 使用缓存避免重复的文件系统检查
    if full_path in _frontend_cache:
        cached_path = _frontend_cache.pop(full_path)
        _frontend_cache[full_path] = cached_path  # 移到末尾（LRU）
        if cached_path and os.path.isfile(cached_path):
            return FileResponse(cached_path)

    if os.path.exists(frontend_dist):
        file_path = os.path.join(frontend_dist, full_path)
        if os.path.isfile(file_path):
            _frontend_cache[full_path] = file_path
            # 超过上限时移除最旧的条目
            while len(_frontend_cache) > _FRONTEND_CACHE_MAX:
                _frontend_cache.popitem(last=False)
            return FileResponse(file_path, headers={
                "Cache-Control": "public, max-age=31536000" if full_path.startswith("assets/") else "public, max-age=3600"
            })
        index_path = os.path.join(frontend_dist, "index.html")
        if os.path.exists(index_path):
            _frontend_cache[full_path] = None  # 标记为SPA路由
            while len(_frontend_cache) > _FRONTEND_CACHE_MAX:
                _frontend_cache.popitem(last=False)
            return FileResponse(index_path)

    return JSONResponse(status_code=404, content={"detail": "Not found"})


def open_browser():
    """延迟打开浏览器，等待服务器启动"""
    import time
    import webbrowser
    time.sleep(2)  # 等待 uvicorn 启动
    webbrowser.open("http://localhost:8000")


def _create_tray_icon():
    """创建系统托盘图标，用于打包后管理服务进程（退出/打开浏览器）"""
    from PIL import Image, ImageDraw
    import pystray

    img = Image.new('RGB', (64, 64), color=(48, 65, 86))
    draw = ImageDraw.Draw(img)
    draw.ellipse([8, 8, 56, 56], fill=(64, 158, 255))
    draw.text((20, 18), "IE", fill=(255, 255, 255))

    def on_open(icon, item):
        import webbrowser
        webbrowser.open("http://localhost:8000")

    def on_quit(icon, item):
        icon.stop()
        import os
        os._exit(0)

    menu = pystray.Menu(
        pystray.MenuItem("打开浏览器", on_open),
        pystray.MenuItem("退出服务", on_quit),
    )
    return pystray.Icon("IE造价审报平台", img, "IE造价审报平台 - 服务运行中", menu)


if __name__ == "__main__":
    import uvicorn
    import threading
    import os

    is_frozen = getattr(sys, 'frozen', False)

    if is_frozen:
        # 打包环境：uvicorn 后台线程 + 托盘图标主线程
        def run_server():
            uvicorn.run(app, host="0.0.0.0", port=8000)

        server_thread = threading.Thread(target=run_server, daemon=True)
        server_thread.start()

        threading.Thread(target=open_browser, daemon=True).start()

        logger.info("Starting uvicorn server on 0.0.0.0:8000 (tray mode)")
        tray = _create_tray_icon()
        tray.run()
    else:
        # 开发环境：直接运行 uvicorn，Ctrl+C 终止
        threading.Thread(target=open_browser, daemon=True).start()
        logger.info("Starting uvicorn server on 0.0.0.0:8000")
        uvicorn.run(app, host="0.0.0.0", port=8000)
