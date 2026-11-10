# 后端

在包含 `backend`、`frontend` 的目录执行以下命令。

## 安装和配置

```powershell
uv sync --project backend
Copy-Item backend/.env.example backend/.env
```

在 `backend/.env` 中填写 MySQL 连接和 `JWT_SECRET_KEY`。

## 初始化和启动

```powershell
uv run --project backend python -m backend.app.commands.init_db --seed-users
uv run --project backend uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

接口文档位于 http://127.0.0.1:8000/docs。

## 模型入口

```powershell
uv run --project backend python -m backend.app.ml.train
uv run --project backend python -m backend.app.ml.predict "图书馆几点关门"
uv run --project backend python -m backend.app.ml.evaluate
```

模型保存于 `backend/artifacts/models/final/pipeline.joblib`。已有模型时，可用 `--output-dir` 指定新的训练输出目录。

固定划分位于 `backend/data/split/`，弱标注样本快照位于 `backend/data/processed/weak_spam.csv`。

## 代码阅读顺序

1. `app/ml/train.py` 用 sklearn Pipeline 串起特征提取和训练，用 TunedThresholdClassifierCV 选择阈值。
2. `app/ml/naive_bayes.py` 实现贝叶斯训练和概率计算。
3. `app/ml/predict.py` 预测新留言并计算贡献词。
4. `app/service/message.py` 在发布留言时调用模型。
