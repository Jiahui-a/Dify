# 安灯数据处理

## 1. 拉取原始数据（近一个月）

```bat
pip install -r requirements.txt
python fetch_andon_events.py
```

## 2. 数据提取与基础清洗

```bat
python prepare_andon_data.py
```

输出：`temp_cleaned_andon_data.csv`、`factory_andon_data.csv`

## 3. LLM 语义标签化（需 Dify API Key）

先在 `llm_tag_andon_data.py` 填写 `DIFY_API_KEY` / `DIFY_API_BASE`。

**只跑前 2000 条（推荐，可暂停续跑）：**

```bat
python llm_tag_andon_top2000.py
```

- 输出：`factory_andon_data_top2000.csv`
- 每 20 条自动保存；Ctrl+C 也会保存
- 再运行会从断点继续

**全量：**

```bat
python llm_tag_andon_data.py
```
