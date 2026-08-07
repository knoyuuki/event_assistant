# 📋 会务助手 (Meeting Assistant)

本地 Web 应用，用于辅助记忆同事的面孔和姓名，并辅助会务工作（人员名单排序、部门排序存档等）。

- **后端**：Python FastAPI（端口 10023）
- **前端**：Vue 3 + Vite（端口 5173，开发时 API 代理到后端）
- **数据库**：MySQL，库名 `event_assistant`（连接配置见下文「配置与密钥」）

> ⚠️ `photos/`（人员照片）、`people/`（通讯录、会议资料等内部资料）、`config/secret.key`（解密密钥）与本地 `config/*.json` 均已被 `.gitignore` 排除，不入版本库。

---

## ✨ 功能模块

| 页面 | 路由 | 说明 |
|------|------|------|
| 浏览模式 | `/browse` | 按文件名顺序或随机顺序逐张展示照片、姓名、部门、职位，可按部门筛选 |
| 认人测试 | `/test` | 随机出题，默认隐藏姓名，手动输入姓名评分（100 分制），结果自动保存 |
| 人员管理 | `/persons` | 人员的增删改查、模糊搜索、分页、按职位等级/部门排序，可从 Excel 通讯录批量导入 |
| 部门管理 | `/departments` | 部门分类树的维护、排序、**排序存档**（保存/恢复当前部门树顺序，供会议排序引用） |
| 会议排序 | `/meetings` | 输入参会部门/人员名单，按职位等级 → 部门树顺序 → 组内顺序自动排序，生成排位名单 |

### 认人测试评分
`score = round((correct_count / total_count) * 100, 2)`，全部答对 = 100 分。

---

## 🏗️ 项目结构

```
face-support/
├── .gitignore            # 忽略 photos/、people/ 等
├── start.bat             # Windows 一键启动脚本
├── start.sh              # Linux/Mac 启动脚本
├── backend/              # Python FastAPI 后端
│   ├── main.py           # 入口，全部 API 路由
│   ├── database.py       # MySQL 连接、建库建表、部门树种子数据
│   ├── models.py         # Pydantic 数据模型、职位等级映射
│   ├── importer.py       # Excel 通讯录 / Markdown 领导层级导入、照片匹配
│   ├── scanner.py        # 照片目录扫描、文件名解析、数据同步
│   └── requirements.txt  # Python 依赖
└── frontend/             # Vue 3 + Vite 前端
    ├── index.html
    ├── package.json
    ├── vite.config.ts    # 开发代理 → 10023
    └── src/
        ├── App.vue       # 根组件、导航栏
        ├── router/       # 路由定义
        ├── api/          # Axios 封装
        ├── views/        # BrowseView / TestView / PersonManageView / DeptManageView / MeetingView
        └── components/   # PhotoCard / DeptFilter / DeptTreeSelect / ScoreBoard
```

---

## 🚀 快速启动

### 前置条件
- Python 3.10+
- Node.js 18+
- MySQL 5.7+（数据库与表会在启动时自动创建）

### 安装依赖
```bash
pip install -r backend/requirements.txt
cd frontend && npm install
```

### 配置数据库（首次）
数据库连接信息通过配置文件管理（密码加密存储，密钥不入库）：

```bash
# 生成密钥并写入加密后的配置（把 '你的密码' 换成 MySQL 密码）
cd backend
python encrypt_password.py --password '你的密码'
```

首次运行会自动生成 `config/secret.key` 密钥文件，并把加密后的密码写入 `config/dev.json`。配置文件与密钥文件均不入版本库。

### 启动
- **Windows**：双击 `start.bat`
- **Linux/Mac**：`bash start.sh`

### 手动启动
```bash
# 终端 1 — 后端（端口 10023）
cd backend
python main.py

# 终端 2 — 前端（端口 5173，API 代理到 10023）
cd frontend
npm run dev
```

浏览器访问 **http://localhost:5173**。

---

## 🔐 配置与密钥

### 配置文件
- 配置目录为项目根 `config/`，格式为 JSON
- **仓库仅提交模板** `config/example.json`；实际的 `config/dev.json`、`config/prod.json` 及密钥文件 `config/secret.key` 均被 `.gitignore` 忽略

### 指定活跃配置
通过环境变量选择加载哪个配置文件（默认 `dev`）：

| 环境变量 | 作用 | 示例 |
|----------|------|------|
| `APP_ENV` | 加载 `config/{APP_ENV}.json` | `APP_ENV=prod python backend/main.py` |
| `APP_CONFIG` | 直接指定配置文件路径（优先级更高） | `APP_CONFIG=/path/to/custom.json python backend/main.py` |

### 密码加密
- 数据库密码不以明文存储在配置文件中，而是经 **Fernet 对称加密** 后的密文（`password_encrypted` 字段）
- 解密密钥来源：环境变量 `APP_ENC_KEY` > 本地文件 `config/secret.key`；均不存在时首次运行自动生成密钥文件
- 密钥文件一旦丢失，已加密的配置将无法解密——请妥善备份
- 生成/更新加密配置：`python backend/encrypt_password.py --password '你的密码'`（可选 `--config prod` 指定环境）

```json
// config/dev.json（本地生成，含密文）
{
  "server": { "host": "0.0.0.0", "port": 10023 },
  "database": {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password_encrypted": "gAAAAABq...（Fernet 密文）",
    "database": "event_assistant",
    "charset": "utf8mb4"
  }
}
```

---

## 📸 照片命名规范

照片放入项目根目录 `photos/` 目录（不入 git），命名格式：

```
姓名-部门-职位.jpg
```

示例：
- `姜逸真-财务部-专业管理.jpg`
- `金巍-数字生活部-部领导.jpg`

文件名中的部门别名会自动映射到规范化部门名（如 `数智办` → `企发部/数智办`），照片与人员记录按姓名匹配关联。

---

## 🗄️ 数据库

库名 `event_assistant`（启动时自动建库建表，连接信息来自 `config/` 下活跃配置，密码加密存储），主要表：

| 表 | 说明 |
|----|------|
| `persons` | 人员信息（姓名、部门、职位、职位等级、类型、手机、邮箱、分管部门等） |
| `test_results` | 认人测试成绩 |
| `meetings` | 会议名单及排序结果 |
| `dept_sort_snapshots` | 部门排序存档（含排位 JSON 数据） |
| `dept_categories` | 部门一级分类 |
| `departments` | 部门（关联分类、排序） |

---

## 📡 API 概览

所有接口前缀 `/api`。常用接口：

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/persons` | 人员列表（支持部门/类型/职位等级筛选、模糊搜索、分页） |
| GET | `/api/persons/sequential` | 按文件名排序的人员列表 |
| GET | `/api/persons/random` | 随机排序的人员列表 |
| GET | `/api/photo/{filename}` | 获取照片文件 |
| GET | `/api/departments?tree=true` | 部门分类树（分类 → 部门） |
| GET | `/api/departments/names` | 部门名称列表（树序，用于筛选下拉） |
| GET | `/api/dept-snapshots` | 部门排序存档列表 |
| POST | `/api/dept-snapshots` | 保存当前部门树顺序为存档 |
| POST | `/api/dept-snapshots/{id}/apply` | 应用存档恢复部门树顺序 |
| POST | `/api/meetings` | 创建会议并自动排序名单 |
| POST | `/api/test/check` | 提交测试答案并评分 |
| POST | `/api/test/results` | 保存测试结果 |
| POST | `/api/rescan` | 重新扫描照片目录并匹配人员 |
| POST | `/api/import-excel` | 从 Excel 通讯录导入人员 |
| POST | `/api/import-markdown-leaders` | 从 Markdown 层级文件导入公司领导 |

完整接口见 `backend/main.py`。
