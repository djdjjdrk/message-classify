# 校园留言分类与垃圾信息识别系统

基于 FastAPI、MySQL 和 Vue 3 的校园留言系统，支持用户发布留言以及管理员进行分类标注和审核。

## 功能

- 用户注册、登录和退出；普通用户和管理员按角色访问功能。
- 发布留言，查看个人留言和已通过审核的公共留言，分页及删除留言。
- 管理员查看分类结果、人工标注正常或垃圾信息，并审核待处理留言。
- 后端提供留言搜索、标注及审核历史接口；人工标注和审核记录保存在数据库中。

模型预测、训练和自动审核尚未实现；模型接口约定见 [ML 对接文档](backend/app/ml/README.md)。

## 环境要求

- Python 3.12、[uv](https://docs.astral.sh/uv/)
- Node.js 22.12+ 或 24 LTS、npm
- MySQL，预先创建数据库和有访问权限的用户

## 本地运行

1. 在项目根目录安装依赖，将 `.env.example` 复制为 `.env`，填写 MySQL 连接和至少 32 个随机 ASCII 字符的 `JWT_SECRET_KEY`。

   ```powershell
   uv sync --group dev
   Copy-Item .env.example .env
   ```

2. 初始化数据库。可选的 `--seed-users` 会交互式创建缺失的 `student` 和 `admin` 账号；已有账号不会被修改。

   ```powershell
   uv run python -m scripts.init_db --seed-users
   ```

3. 启动后端，接口文档位于 http://127.0.0.1:8000/docs。

   ```powershell
   uv run uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
   ```

4. 在另一个终端启动前端，访问 http://127.0.0.1:5173。

   ```powershell
   cd frontend
   npm ci
   npm run dev
   ```

开发环境通过 Vite 将 `/api` 代理至 `http://127.0.0.1:8000`。如需更改目标，复制 `frontend/.env.example` 为 `frontend/.env.local` 并修改配置。生产环境可参考 [Nginx 配置示例](frontend/nginx.conf.example)。

## 测试与构建

```powershell
uv run python -m pytest -q
npm --prefix frontend test
npm --prefix frontend run build
```

前端构建产物位于 `frontend/dist/`。更多前端使用说明见 [前端 README](frontend/README.md)。

## 数据库升级

新数据库使用初始化脚本建表。升级已有数据库前请备份并停止后端，按已有结构需要运行以下脚本：

```powershell
uv run python -m scripts.migrate_users
uv run python -m scripts.migrate_record_timestamps
uv run python -m scripts.migrate_review_sources
```

表结构、字段和迁移说明见 [数据库文档](DATABASE_README.md)。

## 项目结构

- `backend/app/api`、`service`、`schemas`：接口、业务逻辑和数据校验。
- `backend/app/models`：数据库模型；`backend/app/ml`：模型接口契约。
- `frontend/src`：Vue 页面、组件、路由及 API 客户端。
- `scripts`：数据库初始化与迁移；`tests`：后端测试。
