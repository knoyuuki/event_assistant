# 会务助手 (Meeting Assistant)

本地 Web 应用，用于辅助记忆同事的面孔和姓名。

## 项目架构

```
face-support/
├── CLAUDE.md              # 本文档
├── start.bat              # Windows 启动脚本
├── start.sh               # Linux/Mac 启动脚本
├── backend/               # Python FastAPI 后端
│   ├── main.py            # 入口，API 路由，CORS，启动事件
│   ├── database.py        # MySQL 连接，建库建表
│   ├── models.py          # Pydantic 数据模型
│   ├── scanner.py         # 照片目录扫描，文件名解析，数据同步
│   └── requirements.txt   # Python 依赖
└── frontend/              # Vue 3 + Vite 前端
    ├── index.html
    ├── package.json
    ├── vite.config.ts     # Vite 配置，API 代理到 10023
    ├── tsconfig.json
    └── src/
        ├── main.ts        # Vue 应用入口
        ├── App.vue        # 根组件，导航栏
        ├── env.d.ts       # TypeScript 声明
        ├── router/
        │   └── index.ts   # Vue Router (/browse, /test)
        ├── api/
        │   └── index.ts   # Axios 封装，所有 API 调用
        ├── views/
        │   ├── BrowseView.vue   # 浏览模式（顺序/乱序）
        │   └── TestView.vue     # 认人测试模式
        └── components/
            ├── PhotoCard.vue    # 单张照片卡片
            ├── DeptFilter.vue   # 部门筛选 + 模式切换
            └── ScoreBoard.vue   # 测试评分弹窗
```

## 数据库

### 连接信息
- **地址**: 127.0.0.1:3306
- **用户**: root
- **密码**: root
- **数据库**: face_support

### 表结构

**persons** - 人员信息表（从照片文件名自动解析同步）
| 字段       | 类型         | 说明              |
|-----------|-------------|-------------------|
| id        | INT PK AI   | 自增主键          |
| name      | VARCHAR(50) | 姓名              |
| department| VARCHAR(100)| 部门              |
| position  | VARCHAR(100)| 职位              |
| filename  | VARCHAR(255)| 照片文件名（唯一）  |
| created_at| DATETIME    | 创建时间           |

**test_results** - 测试成绩记录表
| 字段       | 类型          | 说明     |
|-----------|--------------|----------|
| id        | INT PK AI    | 自增主键 |
| total     | INT          | 总人数   |
| correct   | INT          | 正确数   |
| score     | DECIMAL(5,2) | 得分     |
| created_at| DATETIME     | 测试时间 |

## API 接口

所有接口前缀 `/api`，后端监听 **10023** 端口。

### 人员相关
| 方法 | 路径                   | 参数        | 说明                     |
|------|-----------------------|------------|--------------------------|
| GET  | /api/persons          | ?department| 列表（按ID排序）           |
| GET  | /api/persons/sequential| ?department| 列表（按文件名排序）        |
| GET  | /api/persons/random   | ?department| 列表（随机排序）           |
| GET  | /api/departments      | -          | 获取所有部门列表           |
| GET  | /api/photo/{filename} | -          | 获取照片文件              |
| POST | /api/rescan           | -          | 重新扫描 photos 目录       |

### 测试相关
| 方法 | 路径               | 请求体                          | 说明          |
|------|-------------------|---------------------------------|---------------|
| POST | /api/test/check   | {answers: [{id, name}]}        | 提交答案并评分 |
| POST | /api/test/results | {total, correct, score}        | 保存测试结果   |

### 评分计算
`score = round((correct_count / total_count) * 100, 2)`

全部答对 = 100 分。

## 照片命名规范

照片文件放入项目根目录的 `photos/` 目录，命名格式：

```
姓名-部门-职位.jpg
```

示例：
- `姜逸真-财务部-专业管理.jpg`
- `金巍-数字生活部-部领导.jpg`

## 启动方式

### 前置条件
- Python 3.10+（需安装依赖：`pip install -r backend/requirements.txt`）
- Node.js 18+（需安装依赖：`cd frontend && npm install`）
- MySQL 5.7+ 运行在 127.0.0.1:3306，root/root

### 启动步骤
1. 安装后端依赖：`pip install -r backend/requirements.txt`
2. 安装前端依赖：`cd frontend && npm install`
3. 双击 `start.bat`（Windows）或运行 `bash start.sh`（Linux/Mac）
4. 浏览器访问 `http://localhost:5173`

### 手动启动
```bash
# 终端1 - 后端 (端口 10023)
cd backend
python main.py

# 终端2 - 前端 (端口 5173，API 代理到 10023)
cd frontend
npm run dev
```

## 功能说明

### 浏览模式 (/browse)
- **顺序遍历**：按照片文件名排序，逐张展示照片、姓名、部门、职位
- **乱序遍历**：随机打乱顺序后逐张展示
- 可按部门筛选
- 上一个/下一个按钮导航

### 认人测试 (/test)
- 随机打乱所有照片顺序
- **默认隐藏姓名**，仅显示照片、部门、职位
- 手动输入姓名文本框，支持回车跳转下一张
- **查看答案**按钮：显示姓名并自动填入
- 提交测试后显示评分弹窗：
  - 总分（100分制）
  - 正确/总人数统计
  - 每道题的答题详情（正确/错误对照）
- 测试结果自动保存到数据库
- 可按部门筛选测试范围
