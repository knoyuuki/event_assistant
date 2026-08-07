# 📋 会务助手 (Meeting Assistant)

本地 Web 应用，用于辅助记忆同事的面孔和姓名，并辅助会务工作（人员名单排序、部门排序存档等）。

- **后端**：Python FastAPI（端口 10023）
- **前端**：Vue 3 + Vite（端口 5173，开发时 API 代理到后端）
- **数据库**：MySQL（127.0.0.1:3306，库名 `face_support`）

> ⚠️ `photos/`（人员照片）与 `people/`（通讯录、会议资料等内部资料）包含个人信息，已被 `.gitignore` 排除，不入版本库。

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
- MySQL 5.7+，运行在 `127.0.0.1:3306`，账号 `root` / 密码 `root`（数据库与表会在启动时自动创建）

### 安装依赖
```bash
pip install -r backend/requirements.txt
cd frontend && npm install
```

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

库名 `face_support`，主要表：

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
