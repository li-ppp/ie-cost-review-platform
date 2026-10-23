"""
打包脚本 - 将后端和前端打包成单个 exe 文件
"""
import PyInstaller.__main__
import os
import sys
import shutil

# 获取项目根目录
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.join(ROOT_DIR, 'backend')
FRONTEND_DIR = os.path.join(ROOT_DIR, 'frontend')
FRONTEND_DIST = os.path.join(FRONTEND_DIR, 'dist')

# 验证必要目录
if not os.path.exists(BACKEND_DIR):
    print(f"错误：后端目录不存在：{BACKEND_DIR}")
    sys.exit(1)

# 检查前端是否已构建
if not os.path.exists(FRONTEND_DIST):
    print(f"警告：前端未构建，正在构建前端...")
    os.chdir(FRONTEND_DIR)
    if os.system('npm install') != 0:
        print("错误：前端依赖安装失败")
        sys.exit(1)
    if os.system('npm run build') != 0:
        print("错误：前端构建失败")
        sys.exit(1)
    os.chdir(ROOT_DIR)
    print("前端构建完成")

# 构建参数
args = [
    os.path.join(BACKEND_DIR, 'main.py'),  # 入口文件
    '--name=IE造价审报平台',  # 输出文件名
    '--onefile',  # 单文件模式
    '--windowed',  # 无控制台窗口
    '--paths', BACKEND_DIR,  # 将 backend 加入模块搜索路径
    '--add-data', f'{FRONTEND_DIST}{os.pathsep}frontend/dist',  # 前端文件
    '--hidden-import', 'uvicorn.logging',
    '--hidden-import', 'uvicorn.loops',
    '--hidden-import', 'uvicorn.loops.auto',
    '--hidden-import', 'uvicorn.loops.asyncio',
    '--hidden-import', 'uvicorn.protocols',
    '--hidden-import', 'uvicorn.protocols.http',
    '--hidden-import', 'uvicorn.protocols.http.auto',
    '--hidden-import', 'uvicorn.protocols.http.h11_impl',
    '--hidden-import', 'uvicorn.protocols.http.httptools_impl',
    '--hidden-import', 'uvicorn.protocols.websockets',
    '--hidden-import', 'uvicorn.protocols.websockets.auto',
    '--hidden-import', 'uvicorn.protocols.websockets.wsproto_impl',
    '--hidden-import', 'uvicorn.lifespan',
    '--hidden-import', 'uvicorn.lifespan.on',
    '--hidden-import', 'uvicorn.lifespan.off',
    '--hidden-import', 'sqlalchemy.dialects.sqlite',
    '--hidden-import', 'sqlalchemy.orm',
    '--hidden-import', 'sqlalchemy.pool',
    '--hidden-import', 'config',
    '--hidden-import', 'database',
    '--hidden-import', 'models',
    '--hidden-import', 'schemas',
    '--hidden-import', 'auth',
    '--hidden-import', 'routers',
    '--hidden-import', 'routers.projects',
    '--hidden-import', 'routers.templates',
    '--hidden-import', 'routers.reports',
    '--hidden-import', 'routers.auth',
    '--hidden-import', 'routers.logs',
    '--hidden-import', 'routers.settings',
    '--hidden-import', 'routers.backup',
    '--hidden-import', 'routers.dictionary',
    '--hidden-import', 'routers.users',
    '--hidden-import', 'services',
    '--hidden-import', 'services.excel_parser',
    '--hidden-import', 'services.report_generator',
    '--hidden-import', 'lxml',
    '--hidden-import', 'lxml.etree',
    '--hidden-import', 'lxml._elementpath',
    '--hidden-import', 'docx',
    '--hidden-import', 'docx.opc',
    '--hidden-import', 'docx.opc.constants',
    '--hidden-import', 'docx.opc.part',
    '--hidden-import', 'docx.opc.package',
    '--hidden-import', 'docx.oxml',
    '--hidden-import', 'docx.oxml.ns',
    '--hidden-import', 'docx.oxml.parser',
    '--hidden-import', 'openpyxl',
    '--hidden-import', 'openpyxl.reader',
    '--hidden-import', 'openpyxl.reader.excel',
    '--hidden-import', 'openpyxl.reader.workbook',
    '--hidden-import', 'openpyxl.workbook',
    '--hidden-import', 'openpyxl.worksheet',
    '--hidden-import', 'fastapi',
    '--hidden-import', 'fastapi.middleware',
    '--hidden-import', 'fastapi.middleware.cors',
    '--hidden-import', 'fastapi.staticfiles',
    '--hidden-import', 'fastapi.responses',
    '--hidden-import', 'pydantic',
    '--hidden-import', 'pydantic.fields',
    '--hidden-import', 'pydantic.validators',
    '--hidden-import', 'starlette',
    '--hidden-import', 'starlette.staticfiles',
    '--hidden-import', 'starlette.responses',
    '--hidden-import', 'starlette.routing',
    '--collect-all', 'fastapi',
    '--collect-all', 'uvicorn',
    '--collect-all', 'sqlalchemy',
    '--collect-all', 'pydantic',
    '--collect-all', 'openpyxl',
    '--collect-all', 'docx',
    '--collect-all', 'lxml',
    '--collect-all', 'starlette',
    '--hidden-import', 'passlib',
    '--hidden-import', 'passlib.context',
    '--hidden-import', 'passlib.handlers',
    '--hidden-import', 'passlib.handlers.bcrypt',
    '--hidden-import', 'bcrypt',
    '--hidden-import', 'jwt',
    '--hidden-import', 'python_jose',
    '--hidden-import', 'python_jose.backends',
    '--hidden-import', 'reportlab',
    '--hidden-import', 'reportlab.lib',
    '--hidden-import', 'reportlab.lib.pagesizes',
    '--hidden-import', 'reportlab.lib.styles',
    '--hidden-import', 'reportlab.lib.units',
    '--hidden-import', 'reportlab.lib.colors',
    '--hidden-import', 'reportlab.pdfgen',
    '--hidden-import', 'reportlab.pdfbase',
    '--hidden-import', 'reportlab.pdfbase.pdfmetrics',
    '--hidden-import', 'reportlab.pdfbase.cidfonts',
    '--hidden-import', 'reportlab.pdfbase.ttfonts',
    '--hidden-import', 'reportlab.platypus',
    '--collect-all', 'reportlab',
    '--collect-all', 'passlib',
    '--collect-all', 'pystray',
    '--collect-all', 'PIL',
    '--hidden-import', 'pystray._win32',
    '--icon', 'NONE',  # 可以指定图标路径
    '--clean',  # 清理临时文件
    '--noconfirm',  # 不确认覆盖
]

print("=" * 60)
print("IE造价审报平台 - 打包脚本")
print("=" * 60)
print(f"项目根目录：{ROOT_DIR}")
print(f"后端目录：{BACKEND_DIR}")
print(f"前端构建目录：{FRONTEND_DIST}")
print()

# 检查前端文件
if os.path.exists(FRONTEND_DIST):
    print("✓ 前端文件已就绪")
else:
    print("✗ 前端文件缺失")
    sys.exit(1)

print()
print("开始打包...")
print()

try:
    PyInstaller.__main__.run(args)
    print()
    print("=" * 60)
    print("打包完成！")
    print("=" * 60)
    exe_path = os.path.join(ROOT_DIR, 'dist', 'IE造价审报平台.exe')
    print(f"可执行文件位于：{exe_path}")

    if os.path.exists(exe_path):
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"文件大小：{size_mb:.2f} MB")
except Exception as e:
    print()
    print("=" * 60)
    print(f"打包失败：{e}")
    print("=" * 60)
    sys.exit(1)
