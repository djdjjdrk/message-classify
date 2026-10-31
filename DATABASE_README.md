# 数据库说明与方法读写对照

本文根据当前项目的 SQLAlchemy 模型、业务方法、HTTP 路由和迁移脚本整理，说明数据库保存什么，以及每个方法会新增、修改或读取哪些表和字段。本文描述代码定义的结构，未连接实际 MySQL 实例核对已部署结构。

## 1. 数据库与代码入口

项目使用 **MySQL + PyMySQL + SQLAlchemy 2.x ORM**。四张业务表均使用 `InnoDB` 引擎和 `utf8mb4` 字符集。数据库名取决于连接配置，示例名称为 `campus_message`。

| 入口 | 作用 |
| --- | --- |
| [database.py](backend/app/database.py) | 创建连接引擎、会话工厂、ORM 基类，提供 UTC 时间函数和请求会话 |
| [config.py](backend/app/config.py) | 从项目根目录 `.env` 读取 `DATABASE_URL` 等配置 |
| [models](backend/app/models/) | 定义四张表的字段、外键、索引和约束 |
| [service](backend/app/service/) | 实际执行查询、插入和更新的业务方法 |
| [api](backend/app/api/) | 接收 HTTP 请求，调用业务方法；完整路由前缀为 `/api/v1` |
| [scripts](scripts/) | 建表、初始化账号、升级旧表结构 |

连接配置格式见 [.env.example](.env.example)：

```dotenv
DATABASE_URL=mysql+pymysql://campus_app:your_password@127.0.0.1:3306/campus_message?charset=utf8mb4
```

`create_engine(..., pool_pre_ping=True)` 在取用连接时检查连接是否可用。`SessionLocal` 设置 `autoflush=False`；业务方法通过 `commit()` 提交写入。`get_db()` 负责提供和关闭会话，本身不自动提交业务修改。

## 2. 表关系

| 表名 | ORM 类 | 保存内容 |
| --- | --- | --- |
| `users` | `User` | 用户账号、昵称、密码哈希和角色 |
| `messages` | `Message` | 留言正文、作者、模型预测、人工标签、审核状态和软删除时间 |
| `annotation_records` | `AnnotationRecord` | 每次人工标签变化的历史 |
| `review_records` | `ReviewRecord` | 人工审核历史及审核依据；自动审核相关字段已预留 |

```mermaid
erDiagram
    users ||--o{ messages : author_id
    users ||--o{ annotation_records : annotator_id
    users |o--o{ review_records : reviewer_id
    messages ||--o{ annotation_records : message_id
    messages ||--o{ review_records : message_id
```

所有外键均设置 `ON DELETE RESTRICT`，存在引用时阻止物理删除被引用的记录。`review_records.reviewer_id` 可为空，为自动审核预留；其他外键不可为空。

ORM 中的 `message.author`、`record.annotator`、`record.reviewer` 等是关联对象，不是额外的数据库字段。

## 3. 字段字典

以下类型按 MySQL 含义表示；“可空”表示是否允许 SQL `NULL`。“ORM 默认”由 SQLAlchemy 写入时提供，与数据库服务端默认值不同。

### 3.1 `users`：用户表

模型文件：[user.py](backend/app/models/user.py)。

| 字段 | 类型 | 可空 | 含义、默认值与约束 |
| --- | --- | --- | --- |
| `id` | BIGINT | 否 | 自增主键 |
| `username` | VARCHAR(20) | 否 | 用户名，唯一约束；注册接口要求 3～20 个字符 |
| `nickname` | VARCHAR(20) | 否 | 昵称；注册时未填写则由业务方法使用用户名 |
| `password_hash` | VARCHAR(255) | 否 | 密码哈希，由 `hash_password()` 生成 |
| `role` | ENUM('student', 'admin') | 否 | 普通用户或管理员；ORM 和数据库默认均为 `student` |
| `created_at` | DATETIME | 否 | 创建时间；ORM 默认 UTC 当前时间 |
| `updated_at` | DATETIME | 否 | 更新时间；ORM 默认 UTC 当前时间，更新时自动刷新 |

注册接口会去除用户名和昵称首尾空白，拒绝保留用户名 `admin`，密码要求 8～32 个字符且不能全为空白。长度、保留名等请求规则见 [schemas/auth.py](backend/app/schemas/auth.py)，不能全部视为数据库约束。

### 3.2 `messages`：留言表

模型文件：[message.py](backend/app/models/message.py)。

| 字段 | 类型 | 可空 | 含义、默认值与约束 |
| --- | --- | --- | --- |
| `id` | BIGINT | 否 | 自增主键 |
| `author_id` | BIGINT | 否 | 作者，外键指向 `users.id`，有索引 |
| `content` | TEXT | 否 | 留言正文；CHECK 要求字符数为 1～2000 |
| `predicted_label` | ENUM('normal', 'spam') | 是 | 模型预测标签；初始为 NULL |
| `prediction_status` | ENUM('pending', 'success', 'no_features', 'no_model', 'error') | 否 | 预测状态；ORM 和数据库默认均为 `pending` |
| `predicted_probability` | FLOAT | 是 | **垃圾信息 spam 的概率**，不是预测标签的置信度；CHECK 限制在 0～1 |
| `prediction_explanation` | JSON | 是 | 特征及贡献列表，例如 `[{"feature":"刷单","weight":1.28}]`；Python `None` 保存为 SQL NULL |
| `model_name` | VARCHAR(128) | 是 | 实际预测使用的模型版本 |
| `manual_label` | ENUM('normal', 'spam') | 是 | 人工标签；初始为 NULL |
| `review_status` | ENUM('pending', 'approved', 'rejected') | 否 | 待审核、通过、驳回；ORM 和数据库默认均为 `pending`，有索引 |
| `created_at` | DATETIME | 否 | 创建时间；ORM 默认 UTC 当前时间 |
| `updated_at` | DATETIME | 否 | 更新时间；ORM 默认 UTC 当前时间，更新时自动刷新 |
| `deleted_at` | DATETIME | 是 | 软删除时间，NULL 表示未删除，有索引 |

发布接口先去除正文首尾空白，再拒绝空白正文。数据库的正文长度 CHECK 不负责判断内容是否全为空白。

`prediction_status` 的含义为：`pending` 尚未预测，`success` 成功，`no_features` 无有效特征，`no_model` 缺少模型，`error` 预测失败。当前发布方法仅保存 `pending` 状态，尚未调用模型预测。

### 3.3 `annotation_records`：人工标注历史表

模型文件：[annotation_record.py](backend/app/models/annotation_record.py)。提交人工标注和查询标注历史的接口位于 [api/annotation.py](backend/app/api/annotation.py)，业务函数位于 [service/annotation.py](backend/app/service/annotation.py)。

| 字段 | 类型 | 可空 | 含义、默认值与约束 |
| --- | --- | --- | --- |
| `id` | BIGINT | 否 | 自增主键 |
| `message_id` | BIGINT | 否 | 被标注的留言，外键指向 `messages.id`，有索引 |
| `annotator_id` | BIGINT | 否 | 操作人，外键指向 `users.id`，有索引 |
| `previous_label` | ENUM('normal', 'spam') | 是 | 标注前的有效分类；优先取旧人工标签，其次取成功的模型标签，否则 NULL |
| `new_label` | ENUM('normal', 'spam') | 否 | 本次人工标签 |
| `reason` | TEXT | 是 | 标注原因；接口最多接受 500 个字符，去除首尾空白后为空则保存 NULL |
| `created_at` | DATETIME | 否 | 创建时间；ORM 默认 UTC 当前时间 |
| `updated_at` | DATETIME | 否 | 更新时间；ORM 默认 UTC 当前时间，更新时自动刷新 |

每次标签变化新增一条记录，当前业务没有修改或删除历史记录的方法。原因长度限制来自请求模型，数据库字段本身为 TEXT。

### 3.4 `review_records`：审核历史表

模型文件：[review_record.py](backend/app/models/review_record.py)。人工审核及历史查询由 [审核业务函数](backend/app/service/review.py) 实现，自动审核相关快照字段已预留。

| 字段 | 类型 | 可空 | 含义、默认值与约束 |
| --- | --- | --- | --- |
| `id` | BIGINT | 否 | 自增主键 |
| `message_id` | BIGINT | 否 | 被审核的留言，外键指向 `messages.id`，有索引 |
| `reviewer_id` | BIGINT | 是 | 审核人，外键指向 `users.id`，有索引；允许自动审核不关联用户 |
| `review_source` | ENUM('manual', 'automatic') | 否 | 人工或自动审核；ORM 和数据库默认均为 `manual` |
| `previous_status` | ENUM('pending', 'approved', 'rejected') | 否 | 审核前的状态 |
| `decision` | ENUM('approved', 'rejected') | 否 | 本次审核结论 |
| `label_snapshot` | ENUM('normal', 'spam') | 是 | 审核时的分类快照 |
| `model_name_snapshot` | VARCHAR(128) | 是 | 审核时使用的模型版本快照 |
| `spam_probability_snapshot` | FLOAT | 是 | 审核时的垃圾信息概率快照 |
| `normal_threshold_snapshot` | FLOAT | 是 | 审核时采用的正常留言判定阈值快照 |
| `comment` | TEXT | 是 | 审核说明 |
| `created_at` | DATETIME | 否 | 创建时间；ORM 默认 UTC 当前时间 |
| `updated_at` | DATETIME | 否 | 更新时间；ORM 默认 UTC 当前时间，更新时自动刷新 |

当前模型没有对审核来源与审核人组合、驳回原因必填、快照概率范围等设置 CHECK。人工审核服务会校验驳回原因及说明长度；自动审核和模型快照写入尚未实现，不能将字段用途理解为数据库已经强制执行的约束。

## 4. 写入方法：具体修改哪个表、哪些字段

本节列出当前已实现的业务写入。`id` 由数据库自增生成；创建和更新时间由 ORM 自动提供。

| 方法与源码 | HTTP 入口 | 表及操作 | 显式写入字段 | 自动生成或更新字段 |
| --- | --- | --- | --- | --- |
| [`register_user()`](backend/app/service/auth.py) | `POST /api/v1/auth/register` → `register()` | `users`：INSERT | `username`、`nickname`、`password_hash`、`role='student'` | `id`、`created_at`、`updated_at` |
| [`create_message()`](backend/app/service/message.py) | `POST /api/v1/messages` → `publish_message()` | `messages`：INSERT | `author_id`、`content` | `id`、`created_at`、`updated_at`；状态默认见下文 |
| [`delete_message()`](backend/app/service/message.py) | `DELETE /api/v1/messages/{message_id}` → `remove_message()` | `messages`：UPDATE，按 `id` 定位 | `deleted_at=utc_now()` | `updated_at` |
| [`annotate_message()`](backend/app/service/annotation.py) | `POST /api/v1/classification/messages/{message_id}/annotations` → `create_annotation()` | `messages`：UPDATE，按 `id` 定位 | `manual_label=label` | `updated_at` |
| 同一次 `annotate_message()` 调用 | 同上 | `annotation_records`：INSERT | `message_id`、`annotator_id`、`previous_label`、`new_label`、`reason` | `id`、`created_at`、`updated_at` |
| [`review_message()`](backend/app/service/review.py) | `POST /api/v1/reviews/messages/{message_id}` → `review_message()` | `messages`：UPDATE，按 `id` 定位 | `review_status=decision` | `updated_at` |
| 同一次 `review_message()` 调用 | 同上 | `review_records`：INSERT | `message_id`、`reviewer_id`、`review_source='manual'`、`previous_status`、`decision`、`label_snapshot`、`comment` | `id`、`created_at`、`updated_at` |

### 4.1 注册 `register_user()`

先按 `users.username` 检查重名；重名时不插入。未提供昵称则使用用户名，密码经过哈希后写入 `password_hash`。普通注册始终写入 `role='student'`。方法调用 `add()`、`commit()`，再用 `refresh()` 读取生成后的字段。

登录方法 `authenticate_user()` 只查询用户并校验密码，不更新用户时间，也没有登录次数或最后登录时间字段。

### 4.2 发布 `create_message()`

`author_id` 来自后端验证后的登录用户，正文来自请求校验结果。新增后的状态为：

```text
prediction_status = 'pending'
review_status = 'pending'
predicted_label = NULL
predicted_probability = NULL
prediction_explanation = NULL
model_name = NULL
manual_label = NULL
deleted_at = NULL
```

该方法提交失败时执行 `rollback()`；成功后 `refresh()` 获取生成字段。当前发布流程只新增留言，不新增标注记录或审核记录。

### 4.3 删除 `delete_message()`

按 `messages.id` 读取留言，校验当前用户是作者或管理员，再写入 `deleted_at` 并提交。不存在或已删除返回业务错误，提交失败时回滚。

这是软删除：原文、作者、标签、预测和审核状态保留，关联的标注和审核历史也保留。列表查询排除 `deleted_at IS NOT NULL` 的留言；标注及标注历史接口也拒绝访问已删除留言。

### 4.4 人工标注 `annotate_message()`

接口要求管理员身份，`annotator_id` 由后端当前用户提供。方法先查询指定且未删除的留言，计算 `previous_label`，然后更新留言的人工标签并新增历史，两项写入在同一次 `commit()` 中完成；数据库错误或业务错误时回滚。

标注前标签按以下顺序确定：已有 `manual_label` → `prediction_status='success'` 时的 `predicted_label` → NULL。

若提交标签与已有 `manual_label` 相同，返回 `False`（接口 `changed=false`），不修改留言字段，不新增历史，也不更新原有原因。首次人工确认与模型预测相同的标签仍会新增历史，因为此前尚无人工标签。

人工标注只改变 `manual_label` 和对应更新时间，保留模型预测及 `review_status`。例如把待审核留言标为 `normal`，其审核状态仍为 `pending`，不会因此出现在公共列表。

### 4.5 人工审核 `review_message()`

接口要求管理员身份，`reviewer_id` 来自当前登录用户。方法只接受 `approved` 或 `rejected`；驳回必须填写去除首尾空白后的非空原因，说明最多 500 个字符。留言必须存在、未删除且当前 `review_status='pending'`；已审核的留言返回 409 业务错误。

审核时把 `messages.review_status` 改为本次决定，并新增一条 `review_records`：`previous_status` 保存修改前的状态，`review_source='manual'`，`label_snapshot` 优先取人工标签，其次取成功的模型预测，否则为 NULL。当前人工审核不填充 `model_name_snapshot`、`spam_probability_snapshot` 和 `normal_threshold_snapshot`，新记录的这三列为 NULL。

状态更新与历史插入在同一次提交中完成，数据库错误或业务错误时回滚。审核不改变 `manual_label` 和模型预测；通过审核且未删除的留言会进入公共列表，驳回的留言不会进入公共列表。该方法没有将已审核留言重新改为待审核的功能。

## 5. 查询方法：读取什么、是否修改

下表的字段列列出主要筛选、排序和展示字段；ORM 查询实体时可能读取完整记录。所有这些方法均无业务写入。

| 方法与源码 | HTTP 入口或调用方 | 读取表及主要字段 | 查询行为 |
| --- | --- | --- | --- |
| [`authenticate_user()`](backend/app/service/auth.py) | `POST /api/v1/auth/login` → `login()` | `users`：`username`、`password_hash`、用户身份信息 | 按用户名查找并校验密码，签发 JWT；不把 token 写入数据库 |
| [`get_current_user()`](backend/app/dependencies/auth.py) | 受保护接口的身份依赖；`GET /api/v1/auth/me` → `me()` | `users`：`id`、`role` 及用户信息 | 解码 token 后按用户 ID 查库，身份和角色以数据库为准 |
| [`require_admin()`](backend/app/dependencies/permissions.py) | 分类、标注、审核及相关历史接口 | 使用身份依赖已经读取的 `users.role` | 检查是否为 `admin`，自身不发起额外查询 |
| [`list_my_messages()`](backend/app/service/message.py) | `GET /api/v1/messages/mine` → `get_my_messages()` | `messages`：`author_id`、`deleted_at`、`content`、`created_at`、`id` 等 | 本人且未删除；可按正文关键词筛选，查询列表和总数 |
| [`list_public_messages()`](backend/app/service/message.py) | `GET /api/v1/messages/public` → `get_public_messages()` | `messages`：`review_status`、`deleted_at`、`content`、`author_id`、`created_at`、`id`；关联 `users.nickname` | 审核通过且未删除；可按正文关键词筛选，查询列表和总数 |
| [`list_classification_messages()`](backend/app/service/classification.py) | `GET /api/v1/classification/messages` → `get_classification_messages()` | `messages`：`deleted_at`、`manual_label`、`prediction_status`、`predicted_label`、`content`、`created_at`、`id`；关联 `users.nickname` | 管理员按 `all/unclassified/normal/spam` 筛选，查询列表和总数 |
| [`list_annotation_records()`](backend/app/service/annotation.py) | `GET /api/v1/classification/messages/{message_id}/annotations` → `get_annotation_records()` | `messages.id/deleted_at`；`annotation_records` 的留言、标签、原因、操作人和时间；关联 `users.username/nickname` | 管理员查看指定未删除留言的标注历史及总数 |
| [`list_pending_reviews()`](backend/app/service/review.py) | `GET /api/v1/reviews/pending` → `get_pending_messages()` | `messages`：`review_status`、`deleted_at`、正文、分类和时间；关联 `users.nickname` | 管理员查看未删除且 `review_status='pending'` 的留言及总数 |
| [`list_review_records()`](backend/app/service/review.py) | `GET /api/v1/reviews/history` → `get_review_history()` | `review_records`：审核人、来源、前后状态、标签快照、说明和时间；关联 `messages.content/deleted_at`、`users.username/nickname` | 管理员查看未删除留言的审核历史及总数；审核人可为空 |

留言列表按 `created_at DESC, id DESC` 排序，标注和审核历史按各自的 `created_at DESC, id DESC` 排序。HTTP 分页参数 `page >= 1`，`page_size` 为 1～100，默认 10。审核业务统一使用普通函数，第一个参数为当前请求的数据库会话 `db`。

个人和公共留言搜索去除关键词首尾空白，按正文包含匹配，并转义 SQL LIKE 的特殊符号；例如 `%` 按字符搜索。是否区分大小写等行为取决于实际数据库排序规则，模型没有显式指定排序规则。

分类接口返回的 `effective_label` 和 `label_source` 是即时计算的响应字段，**数据库没有这两列**。计算顺序为人工标签优先，其次是成功的模型预测，否则为未分类。公共列表的 `author_nickname`、`can_delete`，历史列表的操作人用户名和昵称同样来自关联或计算。

## 6. 建表、初始化与迁移方法

在项目根目录运行以下命令。先准备 MySQL 数据库、账号及 `.env`；初始化脚本只建表，不创建数据库和数据库账号。已有数据库升级前停止后端并备份数据；MySQL 的 `ALTER TABLE` 可能隐式提交，不能依赖外层事务保证所有结构变更一起回滚。

### 6.1 新数据库建表与初始化账号

```powershell
python -m scripts.init_db
# 可选：交互设置初始账号密码
python -m scripts.init_db --seed-users
```

| 方法 | 修改对象 | 具体效果 |
| --- | --- | --- |
| [`scripts.init_db.main()`](scripts/init_db.py) | 四张业务表的结构 | 调用 `Base.metadata.create_all()`，创建缺失表及模型定义的索引和约束；不修改已存在表的结构，不清空数据 |
| [`scripts.init_db.seed_users()`](scripts/init_db.py) | `users`：INSERT | 为缺失的 `student`、`admin` 账号写入 `username`、`nickname`、`password_hash`、`role`；自增 `id`，自动填充 `created_at/updated_at` |

`seed_users()` 中昵称等于用户名，角色分别为 `student` 和 `admin`。已有同名账号会跳过，不重置密码和角色；新账号在同一账号初始化事务中提交，取消输入会回滚本次账号写入。它不回滚此前已经完成的建表操作。

### 6.2 旧数据库迁移

按旧库缺失的功能执行对应迁移；以下三个脚本均仅支持 MySQL，并设计为可重复运行。

```powershell
python -m scripts.migrate_users
python -m scripts.migrate_record_timestamps
python -m scripts.migrate_review_sources
```

| 方法 | 表 | 修改的字段或约束 | 旧数据处理 |
| --- | --- | --- | --- |
| [`scripts.migrate_users.main()`](scripts/migrate_users.py) | `users` | `username` 调整为 VARCHAR(20) NOT NULL；补充或调整 `nickname` 为 VARCHAR(20) NOT NULL；补充或调整 `updated_at` 为 DATETIME NOT NULL | NULL 或空白昵称用 `username` 回填；NULL 更新时间用 `created_at` 回填；修改前检查用户名为 3～20 字符、已有昵称不超 20 字符 |
| [`migrate_record_timestamps()`](scripts/migrate_record_timestamps.py) | `annotation_records`、`review_records` | 补充或调整 `updated_at` 为 DATETIME NOT NULL | 只对 NULL 的 `updated_at` 用 `created_at` 回填，保留已有非空值；修改前检查两表存在、创建时间字段存在且无 NULL |
| [`migrate_review_sources()`](scripts/migrate_review_sources.py) | `review_records`；只读 `users` 校验审核人 | 补充 `review_source`，必要时设为 NOT NULL 并默认 `manual`；补充可空的 `model_name_snapshot`、`spam_probability_snapshot`、`normal_threshold_snapshot`；将 `reviewer_id` 调整为可空；移除下述旧 CHECK | 新增来源列时旧记录标记为 `manual`；已有来源列时只回填来源为 NULL 且有审核人的记录；保留原审核人和已有快照，不推测旧模型依据 |

审核来源迁移在修改前拒绝无法确定来源的旧记录，以及引用不存在审核人的记录。它仅在约束存在时移除以下旧版本 CHECK：

```text
ck_review_records_rejection_reason
ck_review_records_source_reviewer
ck_review_records_spam_probability
ck_review_records_normal_threshold
ck_review_records_automatic_details
```

这些迁移只处理表中列出的变更，不是通用的结构同步工具。通过 `created_at` 回填的 `updated_at` 无法还原旧数据真实的修改时间。迁移里的原生 SQL UPDATE 也不会触发 ORM 的 `onupdate` 时间函数。

## 7. 时间、事务与当前功能边界

- 四张表均保存 `created_at` 和 `updated_at`。`utc_now()` 返回不带时区标记的 UTC 时间，配合不保存时区的 MySQL DATETIME；前端展示时转换为北京时间（UTC+8）。
- 时间使用 SQLAlchemy 的 `default=utc_now` 和 `onupdate=utc_now`，数据库没有对应的时间默认值或自动更新时间触发器。通过原生 SQL 写入时，需要自行提供和维护时间字段；无实际更新的只读查询不会刷新 `updated_at`。
- 业务方法负责提交事务，HTTP 路由主要负责参数校验、鉴权和响应组装。管理员限制由接口依赖执行；直接在其他 Python 代码中调用标注等服务方法时，需要调用方保证身份权限。
- 当前业务没有物理删除、修改留言正文、修改昵称或密码、修改角色、编辑标注历史的方法。模型允许的字段更新能力不代表已经提供对应接口。
- 当前人工审核及审核历史查询已有业务实现，预测结果落库和自动审核尚未实现。`MLBackend.predict()`、`train()`、`evaluate()` 目前只是协议签名，按约定不直接访问数据库，详见 [ML 对接文档](backend/app/ml/README.md)。
- 后续接入预测时，业务层需要保存 `messages.prediction_status/predicted_label/predicted_probability/prediction_explanation/model_name`；接入自动审核时，需要同步维护 `messages.review_status` 和新增 `review_records`，记录来源及模型依据快照。这是后续开发涉及的写入。
