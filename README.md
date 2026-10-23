# IE 工程造价审报平台 · 小学期实训交付仓库

> 上传 Excel 工程量清单 → 自动识别多级表头 → 套打 Word 模板 → 生成标准化工程造价评审报告。
>
> 面向市政工程量结算审核场景，替代「手工抄表 + 手工排版 Word」的传统流程。

本仓库包含**系统全部源码、技术文档、测试用例、脱敏样例数据**。构建产物、虚拟环境、本地数据库等均不入库（见 `.gitignore`）。

---

## 一、核心能力

| 模块 | 能力 |
| --- | --- |
| 项目管理 | 项目增删改查，状态流转，关联 Excel 源文件与历史报告 |
| Excel 解析 | 识别合并单元格多级表头，自动映射 9 个业务字段，按 Sheet 名判定工程类型 |
| 模板管理 | 上传 Word 模板，自动扫描占位符变量，模板可用性校验 |
| 报告生成 | 占位符替换 + 章节结构定位 + 自动生成审减/审增造价分析表 |
| 报告治理 | 版本派生、版本对比、三级审核流（草稿/审核中/通过/驳回）、填充命中率反馈 |
| 系统后台 | 账号管理、数据字典、系统设置、数据备份恢复、操作日志 |

支持的工程类型：**道路、排水、交安、桥涵、照明、电力、通信**。

---

## 二、仓库脉络

```
.
├── README.md                          本文件
├── .gitignore / .gitattributes
│
├── IE造价审报平台/                     系统主体源码
│   ├── backend/                       Python 后端（约 5,157 行）
│   │   ├── main.py                    FastAPI 入口：中间件、路由注册、DB 迁移、SPA 托管
│   │   ├── config.py                  路径管理，兼容开发环境与 PyInstaller 打包
│   │   ├── database.py                SQLAlchemy 引擎 + SQLite 性能 PRAGMA
│   │   ├── models.py                  10 张数据表定义
│   │   ├── schemas.py                 Pydantic 出入参模型
│   │   ├── auth.py                    JWT 签发校验、密码哈希、权限依赖
│   │   ├── routers/                   9 个路由模块，共 55 个 REST 端点
│   │   ├── services/                  业务内核
│   │   │   ├── excel_parser.py        多级表头识别与字段映射（698 行）
│   │   │   └── report_generator.py    Word 模板套打与造价分析表生成（908 行）
│   │   └── test_files/                9 份本地测试用 Excel / Word 样例
│   ├── frontend/                      Vue 3 前端（约 5,301 行）
│   │   ├── src/api/index.ts           接口封装
│   │   ├── src/router/index.ts        路由与权限守卫
│   │   ├── src/views/                 11 个页面视图 + App.vue
│   │   ├── src/views/system/          系统管理页（账号/字典/设置/日志/备份）
│   │   ├── vite.config.ts             Vite 构建配置
│   │   └── package.json
│   ├── tests/                         pytest 用例：认证 / Excel 解析 / 报告生成 / 接口
│   ├── requirements.txt               Python 依赖（已锁版本）
│   ├── pytest.ini
│   ├── build_exe.py                   PyInstaller 打包脚本
│   ├── IE造价审报平台.spec             打包配置
│   ├── 启动系统.bat                    一键启动前后端
│   ├── start_backend.bat / start_frontend.bat
│   │
│   ├── 产品白皮书.md                   产品定义、功能详述、API 概览
│   ├── 软件工程计划书.md
│   ├── 项目说明文档.txt
│   ├── 部署文档.txt
│   ├── API文档.txt
│   └── 通用预算评审报告模板.docx        系统内置默认报告模板
│
└── 脱敏模板（项目一）/                  输入输出样例（已脱敏）
    ├── 工程耗材情况表/XX路项目.xlsx      输入：工程量清单
    └── 示例效果/【评审报告】XX路项目.docx 输出：生成的评审报告
```

---

## 三、技术栈

**后端** Python 3.12 · FastAPI 0.115 · SQLAlchemy 2.0 · Pydantic 2.9 · SQLite · openpyxl · python-docx · python-jose + passlib(bcrypt) · reportlab

**前端** Vue 3.4 · TypeScript 5.3 · Vite 5 · Element Plus 2.6 · Pinia · Vue Router 4 · Axios

**打包** PyInstaller → 单文件 exe（含内置 uvicorn + 系统托盘图标）

---

## 四、快速开始

### 环境要求

- Windows 10/11（推荐）、Linux、macOS 均可
- Python 3.9+（开发实际使用 3.12.9）
- Node.js 18+

### 开发模式

```bash
# 1. 建 Python 虚拟环境（必须位于仓库根目录，启动脚本依赖此路径）
python -m venv venv
venv\Scripts\activate            # Linux/macOS: source venv/bin/activate
pip install -r IE造价审报平台/requirements.txt

# 2. 安装前端依赖
cd IE造价审报平台/frontend
npm install

# 3. 启动后端（默认 http://localhost:8000）
cd IE造价审报平台/backend
python main.py

# 4. 另开终端，启动前端（默认 http://localhost:5173）
cd IE造价审报平台/frontend
npm run dev
```

Windows 下可直接双击 `IE造价审报平台/启动系统.bat`，一键拉起前后端。

> **首次启动会自动完成**：建库建表（`data/database.db`）、创建默认管理员、写入默认系统设置与数据字典。
> **默认账号：`admin` / `admin123`** —— 登录后请立即修改密码，详见「七、安全提示」。

### 为什么仓库里没有 `dist/`、`venv/`、`node_modules/`

这些都是可再生产物，已由 `.gitignore` 排除。运行时目录（`data/`、`uploads/`、`logs/`）首次启动自动创建，同样不入库。

若需要可直接分发的 exe：

```bash
pip install pyinstaller
cd IE造价审报平台
python build_exe.py
# 产物：dist/IE造价审报平台.exe（约 55 MB）
```

> 打包前必须已执行 `npm run build`，否则 exe 内置的前端页面为空。

---

## 五、运行测试

```bash
cd IE造价审报平台
pytest                     # 全部用例
pytest tests/test_excel_parser.py -v
```

用例覆盖：用户认证、Excel 解析（含多级表头与异常输入）、报告生成、项目与报告接口。测试使用独立 SQLite 实例，不污染业务库。

---

## 六、API 概览

全部前缀 `/api`，共 55 个端点。完整字段说明见 `IE造价审报平台/API文档.txt`。

| 前缀 | 模块 | 端点数 | 说明 |
| --- | --- | --- | --- |
| `/api/auth` | 认证 | 3 | 注册、登录、获取当前用户 |
| `/api/projects` | 项目管理 | 12 | CRUD、Excel 上传、预览、明细、汇总、校验、导出 |
| `/api/templates` | 模板管理 | 8 | 上传、列表、详情、变量扫描、可用性校验 |
| `/api/reports` | 报告管理 | 14 | 生成、下载、预览、PDF 导出、填充结果、版本、审核、对比 |
| `/api/users` | 账号管理 | 4 | 列表、新增、重置密码、删除（管理员） |
| `/api/dictionary` | 数据字典 | 5 | 工程类型/单位/状态维护 |
| `/api/settings` | 系统设置 | 4 | 键值对读写 |
| `/api/backup` | 数据备份 | 4 | 创建、列表、恢复、删除 |
| `/api/logs` | 操作日志 | 1 | 日志查询 |

健康检查：`GET /api/health`

---

## 七、安全提示（公开仓库必读）

源码 `backend/auth.py` 中存在**硬编码的默认值**，仅用于本地开发，请勿在生产或公网环境沿用：

| 变量 | 默认值 | 正确做法 |
| --- | --- | --- |
| `JWT_SECRET_KEY` | `ie-cost-platform-secret-key-2026-prod` | 启动时注入环境变量，值用 `secrets.token_urlsafe(32)` 生成 |
| `DEFAULT_ADMIN_PASSWORD` | `admin123` | 首次部署后立即登录改密，或用环境变量预设强密码 |
| `CORS_ORIGINS` | `localhost:5173 / 3000` | 按实际域名配置，禁止使用 `*` 且同时携带凭证 |

Windows 设置示例：

```bat
set JWT_SECRET_KEY=<随机长字符串>
set DEFAULT_ADMIN_PASSWORD=<强密码>
cd backend && python main.py
```

另外，`.gitignore` 已排除 `*.db`、`uploads/`、`logs/` —— 这些目录存有**账号密码哈希、操作日志 IP、真实上传原件**，任何时候都不要提交。

---

## 八、文档索引

| 文档 | 用途 |
| --- | --- |
| `IE造价审报平台/产品白皮书.md` | 产品定位、完整功能详述、数据结构、部署方式、质量保障 |
| `IE造价审报平台/软件工程计划书.md` | 开发计划与进度安排 |
| `IE造价审报平台/项目说明文档.txt` | 详细项目说明 |
| `IE造价审报平台/部署文档.txt` | 环境准备与安装部署步骤 |
| `IE造价审报平台/API文档.txt` | 接口逐项参数说明 |

---

## 九、已知问题与后续建议

- **缺数据库迁移工具**：`main.py` 中以裸 SQL `ALTER TABLE` 补齐字段，建议引入 Alembic 统一管理。
- **SQLite 文件位置遗留**：历史路径下存在 `backend/data/database.db`、`backend/ie_platform.db` 等冗余文件，实际生效库为 `IE造价审报平台/data/database.db`。
- **无用户遗忘的前后端分离部署方案**：当前仅支持桌面单机部署，若需多人协同，需改造为独立 Web 服务 + PostgreSQL。
- **前端未做单元测试**：仅后端具备 pytest 覆盖。
