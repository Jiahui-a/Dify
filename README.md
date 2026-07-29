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

**只改一个配置文件：** `dify_config.py`

```python
DIFY_API_KEY = "app-你的真实key"
DIFY_API_BASE = "https://gongsi.com/v1"
DIFY_VERIFY_SSL = False
```

`llm_tag_andon_data.py` 与 `llm_tag_andon_top2000.py` **都读取这份配置**。

**只跑前 2000 条（可暂停续跑）：**

```bat
python llm_tag_andon_top2000.py
```

- 输出：`factory_andon_data_top2000.csv`
- 每 20 条自动保存；Ctrl+C 也会保存并续跑

**全量：**

```bat
python llm_tag_andon_data.py
```
