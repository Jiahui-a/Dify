"""
LLM 语义标签化（需 Dify API Key）

读取基础清洗后的 CSV，调用 Dify Completion API，
为每条安灯记录打上 action_category / extracted_parts 等标签。
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pandas as pd
import requests
import urllib3

from prepare_andon_data import OUTPUT_DIR, TEMP_CSV_PATH, fetch_and_clean_data

# --- Dify API 配置 ---
DIFY_API_KEY = "YOUR_DIFY_APP_API_KEY"
DIFY_API_BASE = "https://gongsi.com/v1"  # 自建 Dify 地址
DIFY_VERIFY_SSL = False  # 内网自签证书：关闭 SSL 校验

# 内网 HTTPS 关闭校验时的告警静默
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 输出：带 LLM 标签的最终 CSV
OUTPUT_CSV_PATH = OUTPUT_DIR / "factory_andon_data.csv"

# 可选：只处理前 N 条做试跑；None 表示全量
MAX_ROWS = None

# 每次调用间隔（秒），降低限速风险
SLEEP_SECONDS = 0.1

LLM_TAGGING_PROMPT = """
你是一个资深的生产安灯数据分析助手。你的任务是从安灯记录中提取关键的维修动作和涉及的备件信息，并进行分类。

请根据以下安灯记录的文本内容，输出一个JSON对象，包含以下字段：
- "action_category": 维修动作类别，可能值包括："复位/重启", "清理/检查", "参数调整", "更换备件", "维修/调试", "其他"。
- "extracted_parts": 如果有明确的备件更换，提取备件的名称，用逗号分隔。如果没有，则为空字符串。
- "is_reset_only": 如果主要动作是复位/重启/清理，且没有涉及更复杂的维修或换件，则为 true，否则为 false。
- "extracted_fault_reason": 从文本中尝试提取故障的根本原因，用精炼的语言描述。如果没有明确原因，则为空字符串。

请根据提供的文本，尽力提取并分类。即使文本很短或口语化，也要尝试分析。
如果信息不明确，对应字段可以为空字符串或根据默认类别填写。

示例输入：
"t信息不对 更换t盘"

示例输出：
{{
  "action_category": "更换备件",
  "extracted_parts": "T盘",
  "is_reset_only": false,
  "extracted_fault_reason": "T盘信息错误"
}}

请处理以下安灯记录文本：
TEXT: {text_to_analyze}
"""

DEFAULT_TAGS = {
    "action_category": "其他",
    "extracted_parts": "",
    "is_reset_only": False,
    "extracted_fault_reason": "",
}


def _default_tags() -> dict:
    return dict(DEFAULT_TAGS)


def _parse_llm_json(text: str) -> dict:
    """从 LLM 返回中解析 JSON（兼容 ```json 代码块）。"""
    if not text:
        raise ValueError("empty llm output")
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError(f"no json object in: {text[:200]}")
    return json.loads(match.group(0))


def call_dify_for_tagging(text_to_analyze) -> dict:
    if text_to_analyze is None or (isinstance(text_to_analyze, float) and pd.isna(text_to_analyze)):
        return _default_tags()
    text = str(text_to_analyze).strip()
    if not text or text.lower() == "nan":
        return _default_tags()

    if not DIFY_API_KEY or DIFY_API_KEY == "YOUR_DIFY_APP_API_KEY":
        raise RuntimeError(
            "请先在 llm_tag_andon_data.py 中配置有效的 DIFY_API_KEY"
        )

    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json",
    }

    # Completion 应用：inputs 变量名需与 Dify 应用里定义一致
    # 若应用用 query/prompt，可改成 "query": prompt
    prompt = LLM_TAGGING_PROMPT.format(text_to_analyze=text)
    data = {
        "inputs": {"text_to_analyze": text},
        "query": prompt,
        "response_mode": "blocking",
        "user": "andon_analysis_script",
    }

    try:
        # 优先 Completion；若 404 再试 Chat
        url = f"{DIFY_API_BASE.rstrip('/')}/completion-messages"
        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=120,
            verify=DIFY_VERIFY_SSL,
        )
        if response.status_code == 404:
            chat_data = {
                "inputs": {"text_to_analyze": text},
                "query": prompt,
                "response_mode": "blocking",
                "user": "andon_analysis_script",
            }
            url = f"{DIFY_API_BASE.rstrip('/')}/chat-messages"
            response = requests.post(
                url,
                headers=headers,
                json=chat_data,
                timeout=120,
                verify=DIFY_VERIFY_SSL,
            )

        response.raise_for_status()
        result = response.json()
        llm_output_str = (
            result.get("answer")
            or result.get("text")
            or (result.get("data") or {}).get("outputs", {}).get("text")
            or ""
        )
        if isinstance(llm_output_str, dict):
            llm_tags = llm_output_str
        else:
            llm_tags = _parse_llm_json(str(llm_output_str))

        return {
            "action_category": llm_tags.get("action_category", "其他") or "其他",
            "extracted_parts": llm_tags.get("extracted_parts", "") or "",
            "is_reset_only": bool(llm_tags.get("is_reset_only", False)),
            "extracted_fault_reason": llm_tags.get("extracted_fault_reason", "") or "",
        }
    except Exception as e:
        print(f"Error calling Dify API for text: {text[:50]}... Error: {e}")
        return _default_tags()


def build_full_reaction_text(df: pd.DataFrame) -> pd.Series:
    text_cols = [
        c
        for c in ["reactionplan", "actions", "remark", "changedesc", "changeeventdesc"]
        if c in df.columns
    ]

    def _join(row) -> str:
        parts = []
        for col in text_cols:
            val = row.get(col)
            if pd.notna(val) and str(val).strip():
                parts.append(str(val).strip())
        return " ".join(parts)

    series = df.apply(_join, axis=1).str.strip()
    return series.replace("", pd.NA)


def process_with_llm(df_cleaned_path: str | Path = TEMP_CSV_PATH) -> pd.DataFrame:
    path = Path(df_cleaned_path)
    if not path.exists():
        raise FileNotFoundError(f"找不到清洗结果文件: {path}")

    df = pd.read_csv(path)
    df.columns = [str(c).lower() for c in df.columns]
    df["full_reaction_text"] = build_full_reaction_text(df)

    work = df
    if MAX_ROWS is not None:
        work = df.head(MAX_ROWS).copy()
        print(f"试跑模式：仅处理前 {len(work)} 条")

    llm_results = []
    total = len(work)
    for i, (_, row) in enumerate(work.iterrows(), start=1):
        print(f"Processing row {i}/{total}...")
        tags = call_dify_for_tagging(row.get("full_reaction_text"))
        llm_results.append(tags)
        time.sleep(SLEEP_SECONDS)

    llm_df = pd.DataFrame(llm_results)
    df_final = pd.concat([work.reset_index(drop=True), llm_df], axis=1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df_final.to_csv(OUTPUT_CSV_PATH, index=False, encoding="utf-8-sig")
    print(f"最终处理的安灯数据已保存到 {OUTPUT_CSV_PATH}")
    return df_final


if __name__ == "__main__":
    # 1) 基础提取与清洗
    print("=" * 60)
    print("1/2 基础清洗")
    print("=" * 60)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df_cleaned = fetch_and_clean_data()
    df_cleaned.to_csv(TEMP_CSV_PATH, index=False, encoding="utf-8-sig")
    print(f"清洗结果: {TEMP_CSV_PATH}")

    # 2) LLM 标签化
    print("=" * 60)
    print("2/2 LLM 语义标签化")
    print("=" * 60)
    process_with_llm(TEMP_CSV_PATH)
