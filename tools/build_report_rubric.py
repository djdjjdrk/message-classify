# -*- coding: utf-8 -*-
"""按评分表权重重写第四部分：前端、后台、数据库、交付、OOP 为主，算法压缩。"""

import sys
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from docx import Document  # noqa: E402

from build_report import (  # noqa: E402
    FIGS,
    TEMPLATE,
    add_body,
    add_code,
    add_figure,
    add_h3,
    add_table,
    style_run,
)

OUTPUT = Path(r"C:\Users\zz\Desktop\py实验报告\校园留言分类与垃圾信息识别系统_实验报告（按评分表）.docx")

INTRO = (
    "本实验完成校园留言分类与垃圾信息识别系统。系统采用前后端分离结构：前端用 Vue 3 与 Vite 实现六个页面，"
    "后端用 FastAPI 提供接口，SQLAlchemy 负责对象关系映射，数据保存在 MySQL 8 中；垃圾信息识别使用 jieba 分词、"
    "词级 TF-IDF 特征和自行实现的多项式朴素贝叶斯。前端负责交互与展示，后端负责输入校验、权限判断、审核流转和"
    "统计口径。下面按“总体结构—数据库—后台业务—前端界面—面向对象—算法—交付”的顺序说明运行过程。"
)

SECTION_1 = [
    ("h3", "（1）系统总体结构与一次请求的处理流程"),
    ("p", "系统分为前端展示层、接口层、业务服务层、数据访问层和数据库五部分，机器学习模块作为业务服务层的支撑"
          "组件，各层的文件位置与职责见表4-1，调用关系如图4-1所示。一次操作由前端发起，经 HTTP 到达接口层；"
          "接口层完成参数解析和身份校验后调用业务服务；业务服务通过 SQLAlchemy 读写数据库，需要分类时再调用"
          "机器学习模块。"),
    ("table", {
        "caption": "表4-1 各层的文件位置与职责",
        "header": ["层次", "主要文件", "职责"],
        "rows": [
            ["前端展示层", "frontend/src/views、components", "六个页面与通用组件，负责表单、列表、分页和操作提示"],
            ["接口层", "backend/app/api/*.py", "路由、参数解析、注入登录用户与数据库会话、统一响应与异常"],
            ["业务服务层", "backend/app/service/*.py", "发布、检索、删除、审核、标注、统计的规则与事务"],
            ["数据模型层", "backend/app/models/*.py", "四张表的 ORM 映射、字段约束与表间关系"],
            ["机器学习模块", "backend/app/ml/*.py", "文本预处理、TF-IDF 特征、朴素贝叶斯、训练评估与在线预测"],
            ["命令与配置", "backend/app/commands、config.py", "建表、数据准备、重训脚本与运行参数"],
        ],
        "widths": [2.6, 4.4, 7.8],
        "aligns": ["center", "left", "left"],
    }),
    ("fig", FIGS / "fig_pipeline.png", 12.2, "图4-1 系统分层结构与模块调用关系"),
    ("p", "以发布留言为例：前端提交正文，接口层校验 JWT 并取得当前用户；请求模型去除首尾空白后检查长度在 1 至"
          " 2000 字之间；业务服务调用预测函数得到标签、垃圾概率和贡献词；审核规则判断是否直接通过；最后在同一个"
          "事务中写入留言与审核记录。每一层只做自己的事，规则集中在业务服务层，因此网页、接口文档和自动化测试"
          "看到的行为一致。"),
    ("p", "系统按角色划分可见范围：学生可以发布、查看本人留言、浏览公开留言、删除本人留言；管理员额外拥有分类"
          "标注、留言审核和留言统计三个页面。前端路由守卫按角色拦截页面，后端接口再校验一次身份与权限，避免只改"
          "前端就绕过限制。"),

    ("h3", "（2）数据库设计：表结构、关联与增删改查"),
    ("p", "数据库共四张业务表：用户表 users、留言表 messages、标注记录表 annotation_records、审核记录表"
          " review_records，均使用 BIGINT 自增主键与 InnoDB / utf8mb4。留言通过 author_id 关联用户，标注与审核"
          "记录通过 message_id 关联留言，并分别通过 annotator_id、reviewer_id 关联操作人；外键统一设置为"
          " ON DELETE RESTRICT，保证历史记录不被误删。用户名唯一，正文用 CHECK 限定 1 至 2000 字，垃圾概率限定"
          " 0 至 1，标签与状态用 ENUM 限定取值，模型依据以 JSON 保存；author_id、review_status、deleted_at 建有"
          "索引，列表与统计查询可以走索引。"),
    ("table", {
        "caption": "表4-2 四张业务表及主要字段",
        "header": ["表名", "主要字段", "约束与作用"],
        "rows": [
            ["users", "id、username、nickname、password_hash、role", "username 唯一；role 限 student / admin；密码只存 Argon2 哈希"],
            ["messages", "id、author_id、content、predicted_label、prediction_status、predicted_probability、prediction_explanation、manual_label、review_status、deleted_at", "外键关联用户；正文 1 至 2000 字；概率 0 至 1；预测依据存 JSON；删除只写时间"],
            ["annotation_records", "id、message_id、annotator_id、previous_label、new_label、reason、created_at", "外键关联留言与用户，记录每次纠正的原标签、新标签与原因"],
            ["review_records", "id、message_id、reviewer_id、review_source、decision、label_snapshot、comment", "外键关联留言与用户；区分自动与人工审核，保存模型名、概率与阈值快照"],
        ],
        "widths": [3.6, 6.2, 5.0],
        "aligns": ["center", "left", "left"],
    }),
    ("p", "增删改查都落在业务服务里：发布是带约束的 INSERT；列表与检索是带条件和分页的 SELECT；审核与标注是"
          " UPDATE 加一条记录 INSERT；删除只更新 deleted_at，不物理删除，历史与统计因此可以追溯。统计接口不查"
          "明细，而是一条带 CASE 的聚合语句，一次得到总数、正常、垃圾、未分类以及待审核、通过、驳回数量，保证"
          "两个维度的合计都等于总数。"),
    ("code", "message = Message(author_id=author_id, content=content, review_status=\"pending\")\n"
             "db.add(message)\n"
             "try:\n"
             "    auto_approve_message(db, message, settings.AUTO_APPROVE_SPAM_THRESHOLD)\n"
             "    db.commit()      # 留言、审核状态与审核记录同一事务提交\n"
             "except SQLAlchemyError:\n"
             "    db.rollback()\n"
             "    raise"),
    ("p", "建表由 python -m backend.app.commands.init_db 调用 Base.metadata.create_all 完成，只补缺失的表、"
          "不改已有数据，可以重复执行；数据库连接与模型路径集中在 .env，换环境时只需改配置。"),

    ("h3", "（3）后台业务功能：流程、规则与异常处理"),
    ("p", "后台覆盖题目要求的四类基础功能：留言发布、浏览、检索和删除；分类、审核状态与人工标注；待审核列表和"
          "审核操作；留言数量、类别分布与审核情况统计。主要接口、规则与异常见表4-3。"),
    ("table", {
        "caption": "表4-3 主要接口与业务规则",
        "header": ["接口", "作用", "规则与异常"],
        "rows": [
            ["POST /auth/register", "注册账号", "用户名唯一，重复返回 409；密码只存哈希"],
            ["POST /auth/login", "登录", "校验通过签发 JWT；密码错误返回 401"],
            ["POST /messages", "发布留言", "正文去空白后 1 至 2000 字；调用模型；命中规则自动通过，否则待审核"],
            ["GET /messages/mine、/public", "本人列表与公开列表", "分页与关键词检索；公开列表只含已通过且未删除的留言"],
            ["DELETE /messages/{id}", "删除留言", "本人或管理员可删；只写 deleted_at；重复删除返回 404"],
            ["POST /reviews/messages/{id}", "人工审核", "通过或驳回；驳回必填原因；已审核再提交返回 409"],
            ["POST /classification/…/annotations", "人工标注", "写入人工标签与标注历史；同一标签不重复写"],
            ["GET /statistics", "留言统计", "一次聚合；分类与审核两个维度合计均等于总数"],
        ],
        "widths": [5.2, 3.4, 6.2],
        "aligns": ["left", "left", "left"],
    }),
    ("p", "审核是一个明确的状态机：新留言为待审核，自动通过或人工通过后变为已通过，人工驳回后变为已驳回；已审核"
          "的留言再次提交返回 409，避免重复审核覆盖结果。自动通过要求“预测成功、标签为正常、垃圾概率不超过 0.25”"
          "三条同时成立，其余一律进入人工审核；驳回必须填写原因，原因随审核记录保存，便于复查。"),
    ("p", "异常处理分三层：请求模型负责字段校验，空正文、超长或非法标签返回 422；业务服务把规则冲突转成带业务码"
          "的异常，如 404、403、409；统一异常处理器再转换成 {code, message, data} 结构，未登录 401、越权 403、"
          "未找到 404、冲突 409、参数错误 422、数据库异常 500。所有写操作都包在事务里，出错回滚。模型文件缺失或"
          "预测抛出异常时不阻断发布，留言的预测状态记为 no_model 或 error 并转人工审核，保证主流程仍然可用。"),

    ("h3", "（4）前端界面与交互反馈"),
    ("p", "前端是 Vue 3 单页应用，路由采用 hash 模式，共登录、注册、留言管理、分类标注、留言审核和留言统计六个"
          "页面；顶部导航随登录角色显示入口，登录后默认进入留言管理。页面结构与主要交互见表4-4。"),
    ("table", {
        "caption": "表4-4 前端页面与主要交互",
        "header": ["页面", "主要操作", "反馈方式"],
        "rows": [
            ["登录 / 注册", "输入账号密码并提交", "失败显示具体原因；成功后进入留言管理"],
            ["留言管理", "发布、我的/公共切换、关键词检索、刷新、删除", "字数 0/2000 计数、状态徽章、空列表提示"],
            ["分类标注", "按分类筛选、查看模型结论与依据、选择人工标签并填原因", "保存结果提示、标注历史对照"],
            ["留言审核", "查看待审核、通过并公开、驳回并填写原因", "驳回原因必填校验、操作结果提示"],
            ["留言统计", "查看总数、分类分布与审核情况", "刷新按钮、加载态、失败可重试"],
            ["全局", "顶部导航、按角色显示入口、退出登录", "401 自动回到登录页；超时显示可读错误"],
        ],
        "widths": [2.8, 6.2, 5.8],
        "aligns": ["center", "left", "left"],
    }),
    ("p", "交互上重点处理三件事。一是操作完整：发布、切换“我的/公共”、关键词检索、刷新、分页、删除、审核、标注、"
          "统计刷新都能在页面上完成，不需要命令行。二是反馈明确：发布框显示 0/2000 字数，提交后给出成功提示或失败"
          "原因，列表用“已通过 / 待审核 / 已驳回”徽章标出状态，空列表和加载中都有独立提示。三是异常友好：请求"
          "统一 10 秒超时，401 清除令牌并回到登录页，网络失败在页面上显示可读信息而不是白屏。"),
    ("p", "前端只做展示与调用：不判断审核规则，也不计算统计口径，页面显示的分类、概率和贡献词都来自接口返回；"
          "列表请求会取消过期响应，快速切换页面时旧数据不会覆盖新页面。"),

    ("h3", "（5）面向对象设计：类职责与协作"),
    ("p", "系统按“数据、算法、业务、接口”四类职责划分对象，主要类见表4-5。数据模型类只描述表结构与关系，不写业务"
          "规则；TextPreprocessor 只负责规范化与分词；MultinomialNaiveBayes 只负责统计与预测；业务服务接收会话和"
          "参数，负责事务与状态流转；接口层只做 HTTP 适配。"),
    ("table", {
        "caption": "表4-5 主要类与职责",
        "header": ["类或模块", "位置", "职责与封装"],
        "rows": [
            ["Message / User / AnnotationRecord / ReviewRecord", "models/*.py", "表映射、字段约束与关系，不写业务规则"],
            ["TextPreprocessor", "ml/preprocessing.py", "规范化与分词；训练和预测共用同一入口"],
            ["MultinomialNaiveBayes", "ml/naive_bayes.py", "fit、predict_proba、predict 与阈值判断，沿用 sklearn 估计器约定"],
            ["PredictionResult", "ml/predict.py", "预测结果数据对象：状态、标签、概率、贡献词"],
            ["业务服务", "service/*.py", "事务边界、权限判断与状态流转，只依赖模型和会话"],
            ["接口层", "api/*.py", "HTTP 适配、依赖注入、统一响应与异常转换"],
        ],
        "widths": [4.2, 3.4, 7.2],
        "aligns": ["left", "left", "left"],
    }),
    ("p", "这些对象通过明确的接口协作：业务服务在发布时调用预测函数，预测函数组合 TextPreprocessor、已保存的"
          "向量器和 MultinomialNaiveBayes，返回一个 PredictionResult；审核服务只读 Message 的字段，不关心模型"
          "细节。分类器实现 fit、predict_proba、predict 三个方法并沿用 sklearn 的估计器约定，既能放进 Pipeline，"
          "也能整体替换成其他模型而不改动业务层。职责分离也带来可测试性：测试用内存 SQLite 和临时模型路径替换"
          "真实依赖，业务规则可以脱离 MySQL 与模型独立验证。"),

    ("h3", "（6）AI 算法应用：预处理、朴素贝叶斯与业务接入"),
    ("p", "分类任务把留言分为正常（0）和垃圾广告或诈骗引流（1）。训练与预测共用 TextPreprocessor 和"
          " tokenize_with_signals：先做 NFKC 规范化、去掉格式控制字符、合并连续空白，再用 jieba 分词并过滤纯标点；"
          "另外按联系方式、收益承诺、代办服务、医疗美容、博彩充值五类规则生成内部信号 token，每类最多三次，使"
          "“加微信”“日赚”“扫码”这类搭配成为独立特征。"),
    ("p", "特征使用词级 TF-IDF（min_df=2、sublinear_tf），向量器只用训练集正文拟合，测试集、来源留出集和在线"
          "预测一律调用 transform，避免测试信息进入词表。语料来自人大校园树洞、ChineseHarm-Bench 与 IAD 三部分，"
          "清洗合并后 4184 条；按模板与近似重复组划分，训练 3271 条、同分布测试 817 条，IAD 的 96 条广告整体留出"
          "做来源压力测试；最终模型再补充 1551 条规则弱标注广告和 649 条校园交易类困难负样本，训练输入 6120 条。"),
    ("code", "for label in (0, 1):\n"
             "    counts = np.asarray(X[y == label].sum(axis=0)).ravel()\n"
             "    total = counts.sum() + self.alpha * word_count\n"
             "    for word_index in range(word_count):\n"
             "        self.feature_log_prob_[label, word_index] = (\n"
             "            math.log(counts[word_index] + self.alpha) - math.log(total)\n"
             "        )"),
    ("p", "分类器是自行实现的多项式朴素贝叶斯：按类别累加特征权重，用 α=1 的拉普拉斯平滑计算条件概率并对数化，"
          "两类先验设为 0.5；预测时把先验对数与各词加权条件概率相加，减去最大得分后再归一化，避免长文本下溢。"
          "分类阈值在训练集内部按模板组切出的 965 条验证数据上选择，精确率不低于 95% 时取 F2 最大，最终为 0.36。"),
    ("p", "模型接入业务有三个落点：发布时预测并驱动自动审核；分类标注页展示预测标签、垃圾概率、模型名和最多五个"
          "贡献词，贡献词按“TF-IDF 权重乘以两类对数概率差”排序，可以看到某条留言为什么被判为垃圾；管理员纠正"
          "标签后，retrain_from_annotations 导出人工标签、排除评估集关联样本重训，并用同一测试集比较新旧模型。"
          "边界输入也有约定：空白正文在参数校验阶段拒绝，部分未见词被忽略，全部未见词返回 no_features 并转人工"
          "审核，不给出猜测标签。"),

    ("h3", "（7）运行交付：依赖、初始化与启动"),
    ("p", "后端依赖写在 pyproject.toml 并用 uv.lock 锁定，前端依赖写在 package.json 与 package-lock.json；"
          "数据库连接、JWT 密钥和模型路径集中在 .env，示例见 .env.example。启动分三步：安装依赖、初始化数据库、"
          "启动服务。"),
    ("code", "uv sync --project backend --group dev\n"
             "uv run --project backend python -m backend.app.commands.init_db\n"
             "uv run --project backend uvicorn backend.app.main:app --port 8000\n"
             "cd frontend; npm ci; npm run dev          # http://127.0.0.1:5173"),
    ("p", "配套材料包括建表与演示账号脚本、模型文件与训练摘要、数据划分与评估结果、前后端测试、README 和数据库"
          "说明。数据库初始化只创建缺失的表，不删除已有数据，重复执行是安全的；前端用相对路径 /api/v1 访问接口，"
          "开发与预览由 Vite 代理转发到后端。"),
]

SECTION_2 = [
    ("h3", "（1）启动与接口可用性"),
    ("p", "实验在 Windows 11、Python 3.12.13、MySQL 8.4、Node.js 24 环境下完成。启动后端时的控制台输出如下，"
          "服务在 8000 端口持续运行。"),
    ("code", "INFO:     Started server process [28320]\n"
             "INFO:     Application startup complete.\n"
             "INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)"),
    ("p", "随后访问 /openapi.json 与 /docs 均返回 200，接口文档列出认证、留言、分类标注、审核、统计共 6 组 14 个"
          "接口；未携带令牌访问 /api/v1/messages/public 返回 401 和统一错误体 "
          "{\"code\":401,\"message\":\"登录已失效，请重新登录\",\"data\":null}，说明鉴权在业务查询之前生效。"),

    ("h3", "（2）界面运行结果"),
    ("p", "图4-2 是四个页面的实际运行截图，数据来自本次演示：共 9 条留言，正常 4 条、垃圾 5 条，待审核 2 条、"
          "已通过 6 条、已驳回 1 条。"),
    ("fig", FIGS / "fig_ui.png", 13.6, "图4-2 四个主要页面的运行界面"),
    ("p", "留言管理页（a）上方是发布表单，下方可在“我的留言/公共留言”之间切换，检索框按正文关键词过滤，列表按"
          "时间倒序并显示状态徽章和删除入口；分类标注页（b）每条留言给出分类、预测标签、垃圾概率、模型名和主要"
          "依据，并提供人工标签下拉与原因输入；审核页（c）展示待审核留言，“通过并公开”和“驳回”两个按钮，驳回"
          "时原因必填；统计页（d）用三块卡片展示留言总数、分类分布和审核情况。四个页面的数字与统计接口一致。"),
    ("p", "页面在 1440×900 窗口下布局正常，导航、按钮、输入框和徽章都可读；列表为空时显示“暂无留言”，加载和刷新"
          "期间按钮禁用并给出进度反馈，操作成功或失败都有文字提示。"),

    ("h3", "（3）业务闭环运行结果"),
    ("p", "一次完整业务闭环的步骤与结果见表4-6。"),
    ("table", {
        "caption": "表4-6 业务闭环演示",
        "header": ["步骤", "操作", "结果"],
        "rows": [
            ["1", "学生登录", "返回 JWT，进入留言管理"],
            ["2", "发布正常留言", "概率 0.01–0.24，自动通过并公开"],
            ["3", "发布广告留言", "概率约 0.99，进入待审核"],
            ["4", "管理员审核", "一条通过、一条驳回，记录原因"],
            ["5", "公开列表核对", "只显示已通过留言，条数一致"],
            ["6", "删除本人留言", "软删除，列表与统计同步减少"],
            ["7", "人工标注与统计", "统计 4/5/0 与 2/6/1，与页面一致"],
        ],
        "widths": [1.2, 5.0, 8.6],
        "aligns": ["center", "left", "left"],
    }),
    ("p", "闭环中可以看到规则的实际效果：正常留言概率低，自动通过后立刻公开；广告留言概率接近 1，停在待审核；"
          "管理员驳回后公开列表不再出现该留言；人工标注后统计中的类别数量随之变化，标注历史保留原标签，删除后"
          "列表与统计同时减少，三个页面的数字保持一致。"),

    ("h3", "（4）数据库持久化与统计核对"),
    ("p", "演示数据写入后，先结束后端进程，再重新启动服务并查询统计接口，返回的总数仍为 7 条（正常 4、垃圾 3、"
          "待审核 0、已通过 6、已驳回 1），与重启前一致；随后新增 2 条广告，统计变为 9 条（正常 4、垃圾 5、待审核"
          " 2、已通过 6、已驳回 1），与统计页（d）显示相同。说明留言、审核记录和标注记录都持久化在 MySQL 中，"
          "服务重启不会丢失。"),
    ("p", "直接查询数据库同样可以核对：messages 表 9 行、review_records 表 7 行（5 条自动通过、1 条人工通过、"
          "1 条人工驳回）、annotation_records 表 1 行、users 表 2 行；分类合计 4+5=9，审核合计 2+6+1=9，与页面"
          "数字一一对应。"),

    ("h3", "（5）分类模型结果"),
    ("p", "用保存的 campus_spam_final_v1 模型对 6 条自拟文本调用预测函数，结果见表4-7，概率保留两位小数。"),
    ("table", {
        "caption": "表4-7 单条文本的预测结果",
        "header": ["编号", "输入正文", "预测", "垃圾概率", "主要贡献词"],
        "rows": [
            ["1", "请问图书馆今晚几点关门？想去看书。", "正常", "0.01", "图书馆、几点"],
            ["2", "有没有人拼车去高铁站，周日下午三点出发。", "正常", "0.03", "拼车、周日"],
            ["3", "出一本高等数学教材，九成新，30 元，信息楼自取。", "正常", "0.06", "教材、自取"],
            ["4", "兼职刷单日赚三百，加微信 13800000000 详聊。", "垃圾", "0.99", "兼职、赚"],
            ["5", "低价代发各类广告，扫码进群领取名额。", "垃圾", "0.99", "代发、广告"],
            ["6", "zxqv 8492 hjkl", "无特征", "—", "no_features"],
        ],
        "widths": [1.2, 6.9, 1.7, 2.0, 3.0],
        "aligns": ["center", "left", "center", "center", "left"],
    }),
    ("p", "正常留言的垃圾概率都在 0.06 以下，广告接近 0.99；二手教材含“出”“自取”“30 元”等容易被误判的词，"
          "仍被判为正常，说明困难负样本起了作用；随机字母返回 no_features，空白正文在参数校验阶段被拒绝。"
          "模型在固定测试集与 IAD 来源压力测试集上的指标见表4-8。"),
    ("table", {
        "caption": "表4-8 两种评估口径的指标",
        "header": ["评估口径", "样本数", "准确率", "平衡准确率", "垃圾精确率", "垃圾召回率", "F1"],
        "rows": [
            ["同分布测试集", "817", "98.16%", "98.55%", "95.24%", "100.00%", "97.56%"],
            ["IAD 来源集", "613", "94.29%", "88.13%", "83.52%", "79.17%", "81.28%"],
        ],
        "widths": [3.2, 1.6, 1.8, 2.2, 2.2, 2.2, 1.6],
        "aligns": ["left", "center", "center", "center", "center", "center", "center"],
    }),
    ("p", "同分布测试的 817 条中，300 条垃圾全部检出，召回率 100%，15 条正常被误判，垃圾精确率 95.24%，准确率"
          " 98.16%；IAD 留出的 96 条新来源广告检出 76 条、漏判 20 条，召回率 79.17%，平衡准确率 88.13%，比"
          "同分布测试低 10.42 个百分点。两组共享 517 条正常样本，指标不能合并计算。"),
    ("p", "高分主要来自语料来源差异：正常留言来自校园树洞，垃圾来自公开广告语料，模型容易学到来源风格。虽然划分"
          "时已经按模板与近似重复组分隔、交叉为 0，但换一个来源后召回明显下降，说明真实校园广告还需要更多样本"
          "验证；15 条误判会因自动通过上限 0.25 留在待审核，不会被直接公开。"),

    ("h3", "（6）自动化测试结果"),
    ("p", "后端用 pytest 在内存 SQLite 上运行，测试前替换数据库连接、JWT 密钥和模型路径，不依赖本地 MySQL 与模型"
          "文件；前端用 Node.js 内置测试运行器验证请求封装、分页、统计刷新和分类展示。"),
    ("code", "$ python -m pytest -q\n"
             "332 passed, 1 warning in 43.32s\n"
             "$ node --test tests/*.test.js\n"
             "tests 22 / pass 22 / fail 0"),
    ("p", "332 项后端测试覆盖注册登录、发布边界、检索分页、软删除、审核状态机、重复审核、标注历史、统计口径，以及"
          "模型缺失、全未知词和预测异常等分支；22 项前端测试覆盖超时重试、401 处理、分页与统计竞态。"),

    ("h3", "（7）结果分析与改进方向"),
    ("p", "按评分项回顾：GUI 前端的六个页面覆盖全部操作，输入校验和操作反馈明确；后台业务功能覆盖发布、检索、"
          "删除、审核、标注、统计，规则集中在服务层并有统一异常处理；数据库四张表关系完整，增删改查和持久化都"
          "经过实测；面向对象设计以职责划分和可替换接口为主，没有追求类的数量；AI 部分核心算法自行实现、接入"
          "业务且可解释，并在两个口径上给出评价。"),
    ("p", "不足与改进：前端还没有做移动端适配和无障碍检查；审核页一次加载全部待审核留言，数据量大时应改为分页；"
          "统计接口每次实时聚合，留言规模上来后可以加缓存；模型的弱标注数据尚未逐条人工复核；垃圾概率未校准，"
          "只能用于排序和阈值比较，不能当作真实正确率。后续可以补充真实校园广告与含广告词的正常反例，用人工"
          "纠正数据定期重训，并在同一测试集上比较新旧模型。"),
]


def main():
    doc = Document(TEMPLATE)
    cell = doc.tables[3].rows[0].cells[0]

    keep_heading = None
    keep_placeholder = None
    for p in cell.paragraphs:
        if p.text.strip() == "3、心得体会":
            keep_heading = deepcopy(p._p)
        elif "写课程和实验报告的心得体会" in p.text:
            keep_placeholder = deepcopy(p._p)

    from docx.oxml.ns import qn

    tc = cell._tc
    for child in list(tc):
        if child.tag in (qn("w:p"), qn("w:tbl")):
            tc.remove(child)

    p = cell.add_paragraph()
    p.style = doc.styles["报告一级标题"]
    style_run(p.add_run("四、实验结果及分析"), size=None, bold=True, cn="黑体")

    p = cell.add_paragraph()
    p.style = doc.styles["报告二级标题"]
    p.add_run("1、实验运行过程及分析")

    add_body(cell, INTRO)
    for block in SECTION_1:
        kind = block[0]
        if kind == "p":
            add_body(cell, block[1])
        elif kind == "h3":
            add_h3(cell, block[1], block[2] if len(block) > 2 else 8)
        elif kind == "code":
            add_code(cell, block[1])
        elif kind == "table":
            add_table(cell, block[1])
        elif kind == "fig":
            add_figure(cell, block[1], block[2], block[3])

    p = cell.add_paragraph()
    p.style = doc.styles["报告二级标题（2字符）"]
    p.add_run(" 2、运行结果")
    for block in SECTION_2:
        kind = block[0]
        if kind == "p":
            add_body(cell, block[1])
        elif kind == "h3":
            add_h3(cell, block[1], block[2] if len(block) > 2 else 8)
        elif kind == "code":
            add_code(cell, block[1])
        elif kind == "table":
            add_table(cell, block[1])
        elif kind == "fig":
            add_figure(cell, block[1], block[2], block[3])

    if keep_heading is not None:
        tc.append(keep_heading)
    if keep_placeholder is not None:
        tc.append(keep_placeholder)

    doc.save(OUTPUT)
    print("saved", OUTPUT)


if __name__ == "__main__":
    main()
