# SQL 目录说明

本项目数据库脚本存放约定：

```
sql/
├── init.sql                     # 当前完整表结构（全新部署基线）
├── README.md                    # 本说明
└── migrations/                  # 表结构增量变更，按编号递增
    ├── 001_api_apps_api_call_logs.sql
    └── ...
```

## 约定

1. **`init.sql`**：维护为「当前最新完整表结构」，`CREATE TABLE IF NOT EXISTS` 幂等，可重复执行。
   全新部署时只需执行它；它始终包含已应用的所有迁移。

2. **`migrations/NNN_描述.sql`**：每次表结构变动新增一个文件，编号从 `001` 递增、不得修改已提交的迁移文件。
   文件头必须写明：日期、变动背景、幂等性说明。

3. **同步规则**：新增迁移后，把最终结构合并进 `init.sql`（保持两者一致）。

4. **执行方式**：
   - 全新部署：`mysql -h <host> -P <port> -u <user> -p < init.sql`
   - 存量升级：按编号顺序执行 `migrations/` 中未应用的脚本：
     ```bash
     for f in sql/migrations/*.sql; do
         mysql -h <host> -P <port> -u <user> -p event_assistant < "$f"
     done
     ```

5. **后端兜底**：应用启动时（`database.py` / `api_keys.py`）会用等价的幂等 DDL 自动建表/补列，
   因此日常更新不强制手工执行 SQL；SQL 脚本用于文档化、审计与手工运维场景。

6. **回滚**：生产环境原则上不回滚表结构；如确需回滚，新建一个反向迁移文件（编号递增），
   不要修改历史迁移文件。

## 当前结构（8 张表）

| 表 | 说明 | 来源 |
|----|------|------|
| `persons` | 人员信息 | 业务核心表 |
| `test_results` | 认人测试成绩 | 业务表 |
| `meetings` | 会议名单与排序结果 | 业务表 |
| `dept_sort_snapshots` | 部门排序存档 | 业务表 |
| `dept_categories` | 部门一级分类 | 业务表 |
| `departments` | 部门 | 业务表 |
| `api_apps` | 外部应用密钥 | 迁移 001 |
| `api_call_logs` | 外部接口调用日志（保留 7 天） | 迁移 001 |
