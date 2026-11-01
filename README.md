# 校园留言分类与垃圾信息识别系统

基于 FastAPI、MySQL 和 Vue 3 的校园留言系统，支持用户发布留言以及管理员进行分类标注和审核。

## 功能

- 用户注册、登录和退出；普通用户和管理员按角色访问功能。
- 发布留言，查看个人留言和已通过审核的公共留言，按正文关键词检索、分页及删除留言。
- 管理员查看分类结果、人工标注正常或垃圾信息，并审核待处理留言。
- 后端提供留言搜索、标注及审核历史接口；人工标注和审核记录保存在数据库中。
- 管理员查看留言总数、分类分布及审核情况统计，排除已删除留言，支持刷新。

离线数据划分、词频特征、手写多项式朴素贝叶斯训练、模型保存和评估已实现，本地已有 `baseline_v1` 模型及评估产物。主测试集 837 条，准确率 98.33%、垃圾类 F1 97.81%；另有 201 条合成补充样本，准确率 80.60%、垃圾类 F1 77.97%。发布时已接入现有模型，分类标注页和审核页展示原始预测、垃圾概率、模型名和最多 5 个带方向的贡献词；人工标签优先，原始预测保留。线上全未知词返回 `no_features` 交给人工标注，离线评估仍按先验预测全零样本；新发布留言预测正常且垃圾概率 ≤25% 时自动通过，其余交给人工审核；阈值可通过 `AUTO_APPROVE_SPAM_THRESHOLD` 调整。

管理员纠正的人工标签可导出重训：`uv run python -m scripts.retrain_from_annotations` 会更新/补充训练集、排除与固定测试集重合的正文，训练 `retrained` 模型并用同一测试集输出前后指标对照（`artifacts/models/retrained/comparison.md`）。算法、预测与重训命令见 [ML 使用说明](backend/app/ml/README.md)，交付报告见 [REPORT.md](REPORT.md)。

数据集、特征和模型产物未纳入 Git，拉取代码不会自动获得这些文件。要启用预测，请单独取得可信的 `pipeline.joblib` 并放入 `MODEL_PATH` 指定的位置，或按 [ML 使用说明](backend/app/ml/README.md) 准备数据并训练。缺少模型时，留言仍可发布，交由管理员人工审核。

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

## 数据集来源

本项目当前按来源独立保存校园树洞、IAD 和 ChineseHarm-Bench 三份候选数据，原始文件保存在本地 `data/raw/`，必要的样本 CSV 和统计报告保存在 `data/processed/`。

已从 [ChineseHarm-Bench](https://github.com/zjunlp/ChineseHarm-bench) 的黑产广告、欺诈、博彩及低俗色情类别中，筛选并去重后抽取 1,500 条广告或引流类垃圾候选，保存在 `data/processed/chineseharm_spam.csv`，字段为 `content,label,source`。未将谩骂、吐槽等内容整类映射为垃圾。上游 README 声明基准数据采用 CC BY-NC 4.0，仓库 MIT 许可文件针对软件，二者分开记录。本地统计报告位于 `data/processed/chineseharm_report.md`。

### 1. 正常留言数据：人大校园树洞数据集

- **数据集名称**：RUC AI Competition 2025
- **原始内容来源**：中国人民大学校园树洞平台
- **数据集发布者**：mathmonkeyliu
- **数据托管平台**：Hugging Face
- **Hugging Face 地址**：[https://huggingface.co/datasets/mathmonkeyliu/ruc-ai-competition-2025](https://huggingface.co/datasets/mathmonkeyliu/ruc-ai-competition-2025)
- **GitHub 项目地址**：[https://github.com/mathmonkeyliu/ruc-ai-competition-2025](https://github.com/mathmonkeyliu/ruc-ai-competition-2025)
- **数据集目录**：`tree_hole/raw_data/`
- **原始数据格式**：JSONL（JSON Lines）
- **数据类型**：中文校园树洞帖子

本数据集由第三方账号公开发布，不代表中国人民大学官方发布。本项目拟选用约 2,600 条校园树洞帖子正文作为正常留言候选样本。

主要内容包括：

- 校园日常生活。
- 学习、考试与考研交流。
- 宿舍、食堂及校园设施讨论。
- 校园求助与咨询。
- 日常吐槽、闲聊及情感交流。

数据处理流程及计划：

1. 读取原始 JSONL 文件。
2. 提取每条记录中的 `detail` 字段作为帖子正文。
3. 不提取评论 `comment_list`、用户标识及其他与分类无关的字段。
4. 清理空文本、重复文本及无效内容。
5. 对可能包含的个人敏感信息进行脱敏。
6. 检查是否存在广告、诈骗等垃圾内容，避免将所有原始帖子直接认定为正常留言。原始帖子主题分类不能直接作为本项目的二分类标签。

目前已提取正文、去除首尾空白并去重，得到 3,076 条正文。辅助初标后已剔除 488 条不确定（`-1`）样本，当前 `data/processed/campus_posts.csv` 保留 2,588 条，其中正常候选 2,585 条、垃圾候选 3 条；约 2,600 条正常候选的计划规模据此记录。用户人工复核、完整无效文本核查及敏感信息脱敏尚未完成，不能直接视为最终训练数据。清洗和初标方式见 [数据目录说明](data/README.md)，详细过程记录已归档。

### 2. 垃圾留言数据：IAD 中文违法广告数据集

- **数据集名称**：IAD-dataset（Illegal Advertising Dataset）
- **数据集发布者**：socknice
- **GitHub 地址**：[https://github.com/socknice/IAD-dataset](https://github.com/socknice/IAD-dataset)
- **原始数据名称**：Part 1（2018.3）
- **原始数据文件**：`data_p1.xlsx`
- **原始数据格式**：XLSX（Excel）
- **原始数据规模**：5,167 条中文违法广告
- **数据类型**：中文违法广告文本及对应法律条款
- **相关论文**：IAD: A Benchmark Dataset and a New Method for Illegal Advertising Classification
- **论文作者**：Zebo Liu、Kehan Li、Xu Tan、Jiming Chen
- **发表会议**：ECAI 2020
- **论文 DOI**：[https://doi.org/10.3233/FAIA200331](https://doi.org/10.3233/FAIA200331)

本项目计划从 Part 1 原始数据中筛选约 1,000 条有效广告文本，作为垃圾留言样本。主要内容包括违法商业广告、虚假宣传、违规服务推广及其他违法广告内容。

计划处理流程：

1. 读取 IAD-dataset 中的 Part 1 数据。
2. 提取广告正文。
3. 排除法律条款等非广告文本。
4. 清理空值及重复文本，并检查与其他来源是否重复。
5. 抽取约 1,000 条有效广告样本。
6. 根据本项目的分类标准确认后，将筛选后的广告文本标记为垃圾留言（`label=1`）。

当前已将原始文件保存为 `data/raw/iad/data_p1.xlsx`，只提取 `Sheet1` 的“广告内容描述”列，不拼接广告名称、违法条文或链接。实际读取到 5,167 条记录，其中正文空值 11 条；去空并按原始描述精确去重后仅有 111 条不同文本。进一步移除“违法内容：”说明前缀，排除审核说明、语境不足的片段和无法可靠判断的评价文本，再次精确去重后保留 96 条广告候选，映射为 `label=1`，保存在 `data/processed/iad_spam.csv`。

这份 IAD 文件的有效候选不足以达到原定约 1,000 条的抽取目标；未通过重复采样或合成文本补足。详细筛选记录和统计已归档，可用 [IAD 处理脚本](scripts/prepare_iad.py) 复现。候选已参与当前实验划分，但用户人工复核、敏感信息脱敏和相似模板检查尚未完成。

IAD 原始数据是违法广告分类语料，并非专门针对校园垃圾留言的数据集，本项目将其作为垃圾广告候选来源使用。

### 3. 当前候选数据构成

| 数据来源 | 当前记录数 | 标签 | 说明 |
| --- | --- | --- | --- |
| 人大校园树洞 | 2,588 条 | `0/1` | 正常候选 2,585 条、垃圾候选 3 条。 |
| IAD-dataset | 96 条 | `1` | 筛选后的违法广告候选。 |
| ChineseHarm-Bench | 1,500 条 | `1` | 按广告或商业引流标准筛选，优先黑产广告。 |

三份候选数据按来源独立存放。当前已实现三来源合并、正文规范化、跨来源精确去重、冲突标签整组排除和分层划分，本地训练集 3,347 条、测试集 837 条。此前树洞与 IAD 的重复合并版本已归档；候选标签的完整人工确认、脱敏和跨来源近似重复及模板组检查仍未完成，现有划分属于当前实验版本。

### 4. 标签定义

本项目采用二分类标签：

- `0`：正常留言。包括正常交流、校园讨论、吐槽、批评、网络玩梗及其他非垃圾内容。
- `1`：垃圾留言。包括广告推广、诈骗引流、虚假宣传及符合系统垃圾信息判定标准的内容。

本项目不以言论是否文明、是否积极作为分类依据。正常吐槽、讽刺、玩梗不应被直接判定为垃圾留言。

### 5. 数据格式与存储

原始数据分别按来源格式保存：校园树洞数据为 JSONL，IAD Part 1 数据为 XLSX。正文提取及辅助标注结果已输出为 CSV，并已基于当前候选标签生成实验划分、训练和评估产物；完整人工确认、脱敏及近似重复检查仍需补齐。

当前保留三份来源候选 CSV：

- `data/processed/campus_posts.csv`：校园树洞候选，字段为 `content,label`。
- `data/processed/iad_spam.csv`：IAD 广告候选，字段为 `content,label`。
- `data/processed/chineseharm_spam.csv`：ChineseHarm 广告候选，字段为 `content,label,source`。

合并后的训练和测试 CSV 统一采用以下字段：

| 字段 | 含义 |
| --- | --- |
| `content` | 留言正文。 |
| `label` | 分类标签，0 为正常留言，1 为垃圾留言。 |
| `source` | 原始数据来源。 |

模型训练使用 `content` 和 `label`，`source` 用于追踪数据来源及后续实验分析，不作为输入特征。ChineseHarm 通过 `source` 保留原始类别；校园和 IAD 的来源在读取合并时按文件名补齐。划分位于 `data/processed/split/`，词表及矩阵位于 `data/processed/features/`，另有 `extra_test.csv` 和 `extra_features/` 用于合成样本补充评估。目录、处理方法和归档位置见 [数据目录说明](data/README.md)。

### 6. 数据集使用说明

本项目使用上述公开数据集进行课程设计中的文本分类实验，核心分类算法已采用自行实现的多项式朴素贝叶斯，配合 jieba 分词和 CountVectorizer 词频特征。

数据来源用于提供训练语料，原始数据不等于已经完成本项目所需的二分类标注。当前已基于候选标签完成一版离线训练与评估，不能据此视为完整人工复核已完成。已有指标和运行命令见 [ML 使用说明](backend/app/ml/README.md)。

项目保留上述三个原始数据集的出处及 IAD 相关论文引用。IAD 数据集仓库未明确标注独立的数据集许可证，本项目不擅自将其声明为 MIT 或 Apache 2.0 许可；公开或再分发原始数据前，应核实相关使用条件。

## 项目结构

- `backend/app/api`、`service`、`schemas`：接口、业务逻辑和数据校验。
- `backend/app/models`：数据库模型；`backend/app/ml`：机器学习模块及使用说明。
- `frontend/src`：Vue 页面、组件、路由及 API 客户端。
- `scripts`：数据库初始化与迁移、数据初步清洗与辅助标注；`tests`：后端及数据脚本测试。
