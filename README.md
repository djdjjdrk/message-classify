# 校园留言分类与垃圾信息识别系统

三天课程设计，使用 **Streamlit + FastAPI + uv + MySQL**。本文件是唯一开发文档。

当前已完成 Python 3.12.13 环境、依赖安装、基础配置、数据库连接、四张表的 ORM、交互式账号初始化脚本和注册登录流程（Argon2 密码哈希、JWT、身份查询、权限依赖、Streamlit 注册、登录与退出）。已在本地 MySQL 的 `message-classify` 数据库中建表；普通用户可自行注册，预置账号通过下方命令设置密码后创建，四个业务页面仍为占位，留言业务接口与模型训练尚未实现。不提供健康检查接口。

## 当前实际结构

下面与磁盘上的项目结构一致，省略 `.venv/` 内部文件和 Python 运行缓存。空目录用于后续开发，不代表功能已经实现。

```text
message-classify/
├── .venv/                        # uv 虚拟环境，不提交
├── .env.example                  # 配置样例，无真实密码
├── .gitignore
├── .python-version
├── pyproject.toml                # 项目依赖
├── uv.lock                       # 锁定依赖版本
├── README.md
├── backend/
│   ├── __init__.py
│   ├── common/
│   │   ├── __init__.py           # 公共定义统一导出
│   │   ├── response.py           # Response、PageResponse
│   │   └── exceptions.py         # 业务异常、认证异常和全局异常处理器
│   └── app/
│       ├── __init__.py
│       ├── config.py             # .env 配置：数据库、JWT 和模型路径
│       ├── database.py           # Engine、Session、ORM 基类和 get_db
│       ├── models/               # 一张表一个模型文件
│       │   ├── __init__.py       # 统一导出模型并注册表
│       │   ├── user.py
│       │   ├── message.py
│       │   ├── annotation_record.py
│       │   └── review_record.py
│       ├── main.py               # FastAPI 入口，注册认证路由，自带 /docs
│       ├── dependencies/
│       │   ├── __init__.py       # 统一导出请求级依赖
│       │   ├── database.py       # 数据库会话依赖
│       │   ├── auth.py           # 当前用户认证依赖
│       │   └── permissions.py    # 管理员权限依赖
│       ├── api/
│       │   ├── __init__.py
│       │   └── auth.py           # 注册、登录、查询当前用户
│       ├── schemas/
│       │   ├── __init__.py
│       │   └── auth.py           # 注册、登录请求和认证响应
│       ├── service/
│       │   ├── __init__.py
│       │   └── auth.py           # 注册用户、校验账号密码与事务处理
│       ├── utils/
│       │   ├── __init__.py
│       │   ├── password.py       # Argon2 哈希和密码校验
│       │   └── jwt.py            # JWT 签发与解析
│       └── ml/
│           └── __init__.py
├── frontend/
│   ├── __init__.py
│   ├── main.py                   # 登录检查与按角色导航
│   ├── auth.py                   # 登录表单和会话清理
│   ├── api_client.py             # HTTPX 请求和错误提示
│   └── app_pages/                # 认证页面和四个业务占位页面
│       ├── login.py
│       ├── register.py
│       ├── messages.py
│       ├── review.py
│       ├── statistics.py
│       └── model.py
├── scripts/
│   ├── __init__.py
│   └── init_db.py                # 创建缺少的表；可选交互式初始化账号
├── data/
│   ├── raw/                      # 空：初始标注数据
│   └── processed/                # 空：固定数据划分和训练快照
├── artifacts/
│   └── models/                   # 空：模型和指标
└── tests/
    ├── conftest.py               # 内存数据库和认证测试依赖
    └── unit/                     # 认证、账号初始化和前端登录流程测试
```

## 接下来创建的文件

以下文件**还不存在**，按开发顺序逐步创建。请求模型放入现有 schemas 目录，业务逻辑放入现有 service 目录，通用工具放入 utils 目录。

| 文件 | 职责 |
| --- | --- |
| `backend/app/schemas/messages.py` | 留言请求和响应校验 |
| `backend/app/service/messages.py` | 留言业务、事务和统计 |
| `backend/app/service/review.py` | 审核和标注业务 |
| `backend/app/ml/preprocessing.py` | TextPreprocessor，统一归一化和分词 |
| `backend/app/ml/classifier.py` | NaiveBayesClassifier，预测、解释、保存加载 |
| `scripts/train_model.py` | 首次训练、纠正后重训及评估 |
| `tests/unit/test_classifier.py` | 文本边界和模型保存加载验证 |

调用关系：Streamlit → HTTPX → FastAPI → Service → SQLAlchemy / 分类 Pipeline。前端不直接访问数据库或加载模型。

已有入口已接入登录，四个页面后续原地补充业务功能。前端通过 HTTPX 调用后端认证接口；使用 st.navigation 显式导航，页面目录为 app_pages，不使用旧版 pages 自动发现方式。

## 功能与业务约定

- 两个角色：普通用户 student、管理员 admin；支持普通用户注册，不做用户管理页面。管理员仍由初始化脚本创建。
- 注册用户名去除首尾空白后为 3～64 个字符，支持中文、字母、数字、下划线或连字符；admin（不区分大小写）为保留用户名。用户名唯一性最终由数据库唯一约束保证。
- 注册密码为 8～128 字符且不能全部为空白，不自动去除密码首尾空白。后端固定新账号角色为 student，注册请求不接收 role 等额外字段。注册成功后返回登录页，使用新账号密码登录。
- 用户发布 1～2000 字符留言，空白拒绝；初始 pending，管理员通过后才进入大厅。
- 审核状态为 pending / approved / rejected；内容类别为 normal / spam，两者分别保存。
- 展示类别优先人工标签，再用模型标签，均为空显示未分类。模型不自动审核。
- 普通用户只能查看公开留言及本人留言，只能删除本人留言；管理员可审核、标注及删除任意留言。权限在后端验证。
- 删除采用软删除，列表、统计和后续训练默认排除；正文暂不支持编辑。
- 人工纠正保留原预测和历史；标注、审核相关更新在同一事务内完成。驳回必须填写原因；重复提交同一审核状态不追加记录，改标签走标注操作。
- 统计按未删除留言计数，包含未分类；类别数量之和、审核状态数量之和都等于总数。

## 四张表

MySQL 8.0+，本地已创建的库名为 `message-classify`，实际连接由 .env 中的 `DATABASE_URL` 指定。四张表使用 InnoDB、utf8mb4，主键自增 BIGINT，时间按 UTC 存储、上海时区展示。

| 表 | 主要字段 |
| --- | --- |
| users | id、username（唯一）、password_hash、role、created_at |
| messages | id、author_id、content、predicted_label、prediction_status、predicted_probability、prediction_explanation（JSON）、model_name、manual_label、review_status、created_at、updated_at、deleted_at |
| annotation_records | id、message_id、annotator_id、previous_label、new_label、reason、created_at |
| review_records | id、message_id、reviewer_id、previous_status、decision、label_snapshot、comment、created_at |

作者和操作人关联 users，历史记录关联 messages；外键使用 RESTRICT，不级联删除历史。用户名唯一；留言长度限制为 1～2000 字符，预测概率限制在 0～1，审核驳回时必须填写非空原因。空白正文的完整校验、权限校验和审核状态流转由后续业务层实现。

`prediction_status` 支持 pending / success / no_features / no_model / error，默认 pending；`review_status` 独立保存，默认 pending。预测类别、人工类别和预测结果可为空，人工修正不会覆盖原始预测。ORM 写入时间使用 UTC，`updated_at` 在 ORM 更新留言时自动刷新。

建表脚本只创建缺少的表，不清空数据；添加 `--seed-users` 时交互输入密码，创建缺少的 student / admin 账号。密码为 8～128 字符且不能全为空白，使用 Argon2 哈希；已有账号保留密码和角色，中途取消会回滚本轮账号写入。首版不用 Alembic；create_all 不会自动修改已有列。`get_db` 提供请求级 Session 并在结束时关闭，业务层自行提交或回滚事务。

## 必要接口

接口统一前缀 `/api/v1`，其中注册、登录和当前用户查询已实现，其余业务接口待实现。注册和登录无需令牌，其余业务接口需要 Bearer JWT；分页查询参数 page_size 默认 20、最多 100，返回数据使用 `PageResponse(list, total)`。所有业务 API 使用下方统一响应格式，保留框架自带的 /docs、/redoc 和 /openapi.json。

统一返回定义在 `backend/common/`，参考 Timetable-Agent 的公共模块：

```json
{"code": 200, "message": "请求成功", "data": {}}
```

- `Response.success(message="请求成功", data=...)`：HTTP 200、code 200；数据放入 data。
- `Response.error(code=500, message="请求失败")`：生成错误响应体，data 为 null；HTTP 状态由异常处理器决定。
- `PageResponse(list=[...], total=...)`：作为成功响应的 data，分页参数仍通过请求传入。
- `BusinessException(message, code=500)`：返回 HTTP 200，通过非 200 的 code 标识业务失败。
- HTTP 异常保留原始状态码和响应头，包括登录 401、权限 403、路由 404、方法 405；参数校验返回 HTTP 422、code 422、message 为“请求参数校验错误”。
- 未预期异常返回 HTTP 500、code 500、message 为“服务器内部错误”，详细异常只写入服务端日志。

异常类和四类处理器集中在 `exceptions.py`，在 FastAPI 入口统一注册。前端 HTTP 客户端同时检查 HTTP 状态与 code，将成功响应解包为 data，失败时使用 message 提示。框架文档与 OpenAPI 保持原生格式。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| POST | `/auth/register` | username / password 注册普通用户，返回用户信息 |
| POST | `/auth/login` | username / password 登录，返回令牌与用户 |
| GET | `/auth/me` | 校验 Bearer JWT，返回当前用户 id / username / role |
| GET / POST | `/messages` | 查询 / 发布；列表支持 scope=public或mine、keyword、label、分页 |
| GET / DELETE | `/messages/{id}` | 详情 / 软删除；按身份限制范围 |
| GET | `/moderation/messages` | 管理员查询，支持审核状态筛选，默认 pending |
| POST | `/messages/{id}/annotations` | 管理员提交 label、reason |
| POST | `/messages/{id}/reviews` | 管理员提交 decision、label、comment |
| GET | `/statistics` | 管理员查看总数与分布 |
| POST | `/predictions` | 管理员提交 content 试预测 |
| GET | `/models/metrics` | 管理员读取基线与重训结果 |

详情中管理员可看完整历史，作者可看审核意见。JWT 默认有效期 2 小时，密码存哈希，令牌仅保存用户 ID 和时间；角色每次从数据库读取。后续业务接口通过 `dependencies` 包的 `CurrentUser` / `AdminUser` 校验权限，数据库会话依赖在 `dependencies/database.py`，认证依赖在 `dependencies/auth.py`，管理员权限依赖在 `dependencies/permissions.py`。

登录请求使用 JSON，例如 `{"username":"student","password":"你设置的密码"}`，成功响应的 data 包含 `access_token`、`token_type`、`expires_in` 和 `user`；用户名不存在和密码错误统一返回 401。访问 `/auth/me` 时带上 `Authorization: Bearer <access_token>`。前端每次页面运行时查询当前身份，401 会清理会话并回到登录页，网络错误显示重试提示。令牌仅存在当前 Streamlit 会话中，浏览器刷新重建会话后需要重新登录；退出清理本地会话，已签发 JWT 在过期前仍有效，首版没有服务端撤销机制。

## 分类与重训

统一保存完整 Pipeline：TextPreprocessor（NFKC、英文转小写、jieba 分词、过滤纯标点）→ TF-IDF → MultinomialNB，alpha=1.0。前端不另写预处理。

初始数据至少包含 sample_id、text、label，记录来源。去重并解决标签冲突后，按组固定约 80% 训练、20% 测试，确保两侧都有两类。向量器只在训练集拟合。人工纠正后加入新的训练快照，与固定测试集同组的文本不得进入训练。

空白输入返回 422；仅标点或全未见词返回 no_features，不给类别和概率；部分未见词使用已知特征。无模型 / 推理失败时仍允许发布 pending 留言，手动试预测无模型返回 503。

显示预测类别、未经校准的模型概率和最多 5 个贡献词；按 TF-IDF × 两类词对数概率差计算贡献，不能只按词频选依据。

训练脚本分别输出 artifacts/models/baseline 和 retrained，每个目录含 pipeline.joblib、metrics.json、metadata.json；data/processed 保存固定划分和数据快照。只比较相同测试集摘要下的指标，展示准确率、垃圾类 Precision / Recall / F1、混淆矩阵及分类覆盖率。拒判必须单独计数，整体准确率分母保留全部测试样本，子集指标明确标注。

重训通过离线脚本完成，切换 MODEL_PATH 后重启后端；历史预测保留。首版不做在线任务、热切换和模型版本表。

## 三天顺序与常用命令

| 时间 | 工作与完成标准 |
| --- | --- |
| 第 1 天，约 6 小时 | 配置、数据库、四张表、初始化账号、登录、留言接口与页面；可发布和查询 |
| 第 2 天，约 6 小时 | 人工标注、审核历史、统计；发布到审核展示流程完整 |
| 第 3 天，约 6 小时 | 分类、依据、纠正后重训比较、关键检查、截图与报告 |

另留约 2 小时处理问题，第一天确认数据库可用及标注数据来源；优先保证基础功能。

环境已安装，不要重复 uv init。日常命令：

```powershell
cd D:\message-classify
uv sync --locked
uv run python --version
```

复制 .env.example 为 .env，填写真实的 `DATABASE_URL` 与至少 32 字符的随机 `JWT_SECRET_KEY`（可通过 `uv run python -c "import secrets; print(secrets.token_urlsafe(48))"` 生成）。`backend/app/config.py` 使用 Pydantic Settings 从项目根目录的 .env 读取配置，通过 `from backend.app.config import settings` 使用；环境变量可覆盖 .env 中的值。JWT 使用 HS256，有效期默认 2 小时，配置范围为 1～24 小时；模型路径默认是 `artifacts/models/baseline/pipeline.joblib`，相对路径以项目根目录运行时解析。.env 已被 Git 忽略；样例中的库和账号尚未创建。前端独立读取 `API_BASE_URL`，不导入数据库或 JWT 配置。

数据库已存在且 .env 配置正确后，在项目根目录执行建表命令，可重复执行：

```powershell
uv run python -m scripts.init_db
```

首次使用时执行下列命令，分别输入预置 student 和 admin 的密码（输入时不回显）。可重复执行，已有账号不会被覆盖；普通用户也可以通过前端注册页面自行创建账号：

```powershell
uv run python -m scripts.init_db --seed-users
```

现在可以在项目根目录的两个终端分别启动：

```powershell
uv run uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

```powershell
uv run streamlit run frontend/main.py --server.address 127.0.0.1 --server.port 8501
```

访问前端 http://127.0.0.1:8501，后端文档 http://127.0.0.1:8000/docs。点击顶部“注册”创建普通用户账号，或使用初始化时设置的账号密码登录；student 仅显示留言管理，admin 显示四个页面，目前业务页面仍为占位。后端根路径 / 返回 404。停止各自服务使用 Ctrl+C；后端必须配置数据库 URL 和有效 JWT 密钥，数据库不在线时仍可启动，但不能完成注册或登录。

认证和前端登录流程测试无需 MySQL，测试使用独立内存数据库和测试密钥：

```powershell
uv run pytest tests/unit -q
```

以下命令须等对应工具和测试实现后才能执行：

```powershell
uv run python -m scripts.train_model --name baseline
uv run python -m scripts.train_model --name retrained --include-annotations
```

训练参数是后续脚本约定，重训必须复用固定测试集。

验收重点：权限有效、未审核不公开、标注审核可追溯、删除后统计正确、空文本和未见词处理明确、训练预测一致、重训指标真实可比较。最后准备页面截图、数据来源、模型指标和运行说明用于答辩。
