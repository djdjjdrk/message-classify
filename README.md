# 校园留言分类与垃圾信息识别系统

基于 FastAPI、MySQL 和 Vue 3 的校园留言系统，支持用户发布留言以及管理员进行分类标注和审核。

## 功能

- 用户注册、登录和退出；普通用户和管理员按角色访问功能。
- 发布留言，查看个人留言和已通过审核的公共留言，按正文关键词检索、分页及删除留言。
- 管理员查看分类结果、人工标注正常或垃圾信息，并审核待处理留言。
- 后端提供留言搜索、标注及审核历史接口；人工标注和审核记录保存在数据库中。
- 管理员查看留言总数、分类分布及审核情况统计，排除已删除留言，支持刷新。

当前使用 sklearn Pipeline 封装的 `campus_spam_final_v1` 模型，统一保存在 `backend/artifacts/models/final/`。模型以原有 3,271 条训练集为基础，从 ChineseHarm 原始语料自动补充 1,551 条规则弱标注广告，并加入广告信号 token、平衡先验和训练集内部验证选择的 0.36 阈值。模板隔离同分布测试准确率为 98.16%；IAD 来源压力测试准确率为 94.29%、平衡准确率为 88.13%、垃圾召回率为 79.17%。两种评估共享正常样本，不能合并计分；弱标注未逐条人工复核，高同分布分数仍不代表真实校园效果，详见 [交付报告](REPORT.md)。

发布时使用已保存模型预测，分类标注页和审核页展示预测、概率、模型名及最多 5 个贡献词。人工标签优先；全未知词交人工标注。预测正常且垃圾概率 ≤25% 时自动通过，其余人工审核；阈值通过 `AUTO_APPROVE_SPAM_THRESHOLD` 调整。

管理员纠正的人工标签可导出重训：`uv run --project backend python -m backend.app.commands.retrain_from_annotations` 会更新/补充训练集、排除与同分布测试及来源留出集重合的正文、模板和近似重复组，训练 `retrained` 模型并用同一测试集输出前后指标对照（`backend/artifacts/models/retrained/comparison.md`）。当前最终模型由 `uv run --project backend python -m backend.app.ml.train` 生成，训练代码、弱标注候选和评估结果都在 `backend/artifacts/models/final/`。算法、预测与重训命令见 [ML 使用说明](backend/app/ml/README.md)，交付报告见 [REPORT.md](REPORT.md)。

数据集、特征和模型产物未纳入 Git，拉取代码不会自动获得这些文件。要启用预测，请单独取得可信的 `pipeline.joblib` 并放入 `MODEL_PATH` 指定的位置，或按 [ML 使用说明](backend/app/ml/README.md) 准备数据并训练。缺少模型时，留言仍可发布，交由管理员人工审核。

## 环境要求

- Python 3.12、[uv](https://docs.astral.sh/uv/)
- Node.js 22.12+ 或 24 LTS、npm
- MySQL，预先创建数据库和有访问权限的用户

## 本地运行

1. 在包含 `backend`、`frontend` 的目录安装依赖，将 `backend/.env.example` 复制为 `backend/.env`，填写 MySQL 连接和至少 32 个随机 ASCII 字符的 `JWT_SECRET_KEY`。

   ```powershell
   uv sync --project backend --no-dev
   Copy-Item backend/.env.example backend/.env
   ```

2. 初始化数据库。可选的 `--seed-users` 会交互式创建缺失的 `student` 和 `admin` 账号；已有账号不会被修改。

   ```powershell
   uv run --project backend python -m backend.app.commands.init_db --seed-users
   ```

3. 启动后端，接口文档位于 http://127.0.0.1:8000/docs。

   ```powershell
   uv run --project backend uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
   ```

4. 在另一个终端启动前端，访问 http://127.0.0.1:5173。

   ```powershell
   cd frontend
   npm ci
   npm run dev
   ```

开发环境通过 Vite 将 `/api` 代理至 `http://127.0.0.1:8000`。如需更改目标，复制 `frontend/.env.example` 为 `frontend/.env.local` 并修改配置。生产环境可参考 [Nginx 配置示例](frontend/nginx.conf.example)。

## 答辩版本与构建

当前目录为最终答辩版本，已清理自动化测试、隔离测试服务、报告与演示辅助脚本，以及旧数据库迁移和原始数据处理脚本。保留数据库初始化、基于固定数据快照的模型训练、预测、评估和人工纠正后重训入口。

完整测试及辅助脚本可在 Git 提交 `4201ecd` 中查看。

```powershell
npm --prefix frontend run build
```

前端构建产物位于 `frontend/dist/`。更多前端使用说明见 [前端 README](frontend/README.md)。

## 数据库结构

新数据库按“本地运行”中的初始化命令创建当前结构。最终答辩版本已移除旧数据库迁移脚本，历史版本升级流程可在 Git 提交 `4201ecd` 中查看。

表结构、字段和初始化说明见 [数据库文档](DATABASE_README.md)。

## 数据与训练

| 来源 | 候选数量 | 用途 |
| --- | ---: | --- |
| [人大校园树洞（RUC AI Competition 2025）](https://huggingface.co/datasets/mathmonkeyliu/ruc-ai-competition-2025) | 2,588（正常 2,585、垃圾 3） | 训练与分组测试；第三方公开语料，并非学校官方发布 |
| [ChineseHarm-Bench](https://github.com/zjunlp/ChineseHarm-bench) | 1,500 条广告/引流候选 | 训练与分组测试，未将谩骂等类别整体视为垃圾 |
| [IAD Part 1](https://github.com/socknice/IAD-dataset) | 96 条广告候选 | 整来源留出，训练不接触 |

IAD 原始文件有 5,167 条记录，清洗后只有 96 条不同的有效广告候选，未重复或合成补足。论文：Zebo Liu、Kehan Li、Xu Tan、Jiming Chen，*IAD: A Benchmark Dataset and a New Method for Illegal Advertising Classification*，ECAI 2020，[DOI](https://doi.org/10.3233/FAIA200331)。

标签为 `0=正常`、`1=垃圾广告/诈骗引流`，正常吐槽、批评、玩梗不因语气判为垃圾。`source` 只用于追溯、分组和分析，不进入分类特征。候选标签尚未完整人工复核，正常与垃圾来源严重混杂，尚需补充真实校园广告及困难正常反例。

准备好 `backend/data/split/` 下的固定划分和 `backend/data/processed/weak_spam.csv` 后，运行训练入口：

```powershell
uv run --project backend python -m backend.app.ml.train
```

已有模型时使用新的 `--output-dir`，避免覆盖固定实验。具体流程和独立复评命令见 [ML 使用说明](backend/app/ml/README.md)，原始数据、处理步骤和许可说明见 [数据目录说明](backend/data/README.md)。项目仅保留当前模型与对应评估，旧实验及合成演示数据已移出工作目录。

ChineseHarm 上游 README 声明数据采用 CC BY-NC 4.0，软件 LICENSE 为 MIT；IAD 未声明独立数据集许可证，不推定其许可。原始数据不纳入 Git。
