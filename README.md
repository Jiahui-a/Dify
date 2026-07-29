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

1. 在 Dify 创建 **文本生成 / Completion** 应用（或 Chat 应用）
2. 打开 `llm_tag_andon_data.py`，填写：
   - `DIFY_API_KEY`
   - `DIFY_API_BASE`（云端默认 `https://cloud.dify.ai/v1`，自建改成你的地址）
3. 建议先设 `MAX_ROWS = 5` 试跑，再改回 `None` 全量

```bat
python llm_tag_andon_data.py
```

会先清洗，再逐条调用 Dify，写出带标签的：

`factory_andon_data.csv`

新增列：
- `action_category`
- `extracted_parts`
- `is_reset_only`
- `extracted_fault_reason`
- `full_reaction_text`

> 有 API 成本与限速；大量数据请分批或只跑增量。
