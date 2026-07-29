"""
LLM 语义标签化 - 仅前 2000 条（自包含，不依赖 llm_tag_andon_data 导入）

- Dify 地址：https://gongsi.com/v1
- 已关闭 SSL 证书校验（verify=False）
- 每 20 条落盘；Ctrl+C 暂停也会保存；再运行可续跑
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pandas as pd
import requests
import urllib3

from prepare_andon_data import OUTPUT_DIR, TEMP_CSV_PATH

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Dify API 配置（在本文件直接改）---
DIFY_API_KEY = "YOUR_DIFY_APP_API_KEY"
DIFY_API_BASE = "https://gongsi.com/v1"
DIFY_VERIFY_SSL = False  # 关闭 SSL 证书校验
SLEEP_SECONDS = 0.1

TOP_N = 2000
SAVE_EVERY = 20
OUTPUT_CSV = OUTPUT_DIR / "factory_andon_data_top2000.csv"
TAG_COLS = [
    "action_category",
    "extracted_parts",
    "is_reset_only",
    "extracted_fault_reason",
]

LLM_TAGGING_PROMPT = """
你是一个资深的生产安灯数据分析助手。你的任务是从安灯记录中提取关键的维修动作和涉及的备件信息，并进行分类。

请根据以下安灯记录的文本内容，输出一个JSON对象，包含以下字段：
- "action_category": 维修动作类别，可能值包括："复位/重启", "清理/检查", "参数调整", "更换备件", "维修/调试", "其他"。
- "extracted_parts": 如果有明确的备件更换，提取备件的名称，用逗号分隔。如果没有，则为空字符串。
- "is_reset_only": 如果主要动作是复位/重启/清理，且没有涉及更复杂的维修或换件，则为 true，否则为 false。
- "extracted_fault_reason": 从文本中尝试提取故障的根本原因，用精炼的语言描述。如果没有明确原因，则为空字符串。

请处理以下安灯记录文本：
TEXT: {text_to_analyze}
"""

DEFAULT_TAGS = {
    "action_category": "其他",
    "extracted_parts": "",
    "is_reset_only": False,
    "extracted_fault_reason": "",
}


def _parse_llm_json(text: str) -> dict:
    text = (text or "").strip()
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
        return dict(DEFAULT_TAGS)
    text = str(text_to_analyze).strip()
    if not text or text.lower() == "nan":
        return dict(DEFAULT_TAGS)

    if not DIFY_API_KEY or DIFY_API_KEY == "YOUR_DIFY_APP_API_KEY":
        raise RuntimeError("请先在 llm_tag_andon_top2000.py 中配置 DIFY_API_KEY")

    headers = {
        "Authorization": f"Bearer {DIFY_API_KEY}",
        "Content-Type": "application/json",
    }
    prompt = LLM_TAGGING_PROMPT.format(text_to_analyze=text)
    data = {
        "inputs": {"text_to_analyze": text},
        "query": prompt,
        "response_mode": "blocking",
        "user": "andon_top2000_script",
    }

    try:
        url = f"{DIFY_API_BASE.rstrip('/')}/completion-messages"
        response = requests.post(
            url,
            headers=headers,
            json=data,
            timeout=120,
            verify=DIFY_VERIFY_SSL,
        )
        if response.status_code == 404:
            url = f"{DIFY_API_BASE.rstrip('/')}/chat-messages"
            response = requests.post(
                url,
                headers=headers,
                json=data,
                timeout=120,
                verify=DIFY_VERIFY_SSL,
            )
        response.raise_for_status()
        result = response.json()
        llm_output = (
            result.get("answer")
            or result.get("text")
            or (result.get("data") or {}).get("outputs", {}).get("text")
            or ""
        )
        if isinstance(llm_output, dict):
            tags = llm_output
        else:
            tags = _parse_llm_json(str(llm_output))
        return {
            "action_category": tags.get("action_category", "其他") or "其他",
            "extracted_parts": tags.get("extracted_parts", "") or "",
            "is_reset_only": bool(tags.get("is_reset_only", False)),
            "extracted_fault_reason": tags.get("extracted_fault_reason", "") or "",
        }
    except Exception as e:
        print(f"Error calling Dify API for text: {text[:50]}... Error: {e}")
        return dict(DEFAULT_TAGS)


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


def _is_tagged(row: pd.Series) -> bool:
    val = row.get("action_category")
    return pd.notna(val) and str(val).strip() != ""


def _save(df: pd.DataFrame) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8-sig")
    print(f"[save] 已写入 {OUTPUT_CSV}（当前 {len(df)} 条）")


def run_top2000(cleaned_csv: Path = TEMP_CSV_PATH) -> pd.DataFrame:
    if not cleaned_csv.exists():
        raise FileNotFoundError(
            f"找不到清洗文件: {cleaned_csv}\n请先运行: python prepare_andon_data.py"
        )

    if OUTPUT_CSV.exists():
        print(f"发现进度文件，继续: {OUTPUT_CSV}")
        work = pd.read_csv(OUTPUT_CSV)
        work.columns = [str(c).lower() for c in work.columns]
    else:
        df = pd.read_csv(cleaned_csv)
        df.columns = [str(c).lower() for c in df.columns]
        work = df.head(TOP_N).copy().reset_index(drop=True)
        work["full_reaction_text"] = build_full_reaction_text(work)
        for col in TAG_COLS:
            if col not in work.columns:
                work[col] = pd.NA
        print(f"仅处理前 {len(work)} 条（最多 {TOP_N}）")

    total = len(work)
    pending_idx = [i for i in range(total) if not _is_tagged(work.iloc[i])]
    print(f"总行数 {total}，待打标签 {len(pending_idx)}，已完成 {total - len(pending_idx)}")

    if not pending_idx:
        print("已全部打完，无需继续。")
        return work

    done_since_save = 0
    try:
        for n, i in enumerate(pending_idx, start=1):
            print(f"Processing {n}/{len(pending_idx)} (row {i + 1}/{total})...")
            tags = call_dify_for_tagging(work.at[i, "full_reaction_text"])
            for k, v in tags.items():
                work.at[i, k] = v
            done_since_save += 1
            time.sleep(SLEEP_SECONDS)
            if done_since_save >= SAVE_EVERY:
                _save(work)
                done_since_save = 0
    except KeyboardInterrupt:
        print("\n检测到暂停 (Ctrl+C)，正在保存已打标签...")
        _save(work)
        print("已保存，下次直接再运行本脚本即可续跑。")
        return work

    _save(work)
    print(f"前 {TOP_N} 条标签化完成 -> {OUTPUT_CSV}")
    return work


if __name__ == "__main__":
    print("=" * 60)
    print(f"Dify URL : {DIFY_API_BASE}")
    print(f"Verify SSL: {DIFY_VERIFY_SSL}")
    print(f"TOP_N    : {TOP_N}")
    print("=" * 60)

    if not TEMP_CSV_PATH.exists():
        print("未找到清洗结果，先执行基础清洗...")
        from prepare_andon_data import fetch_and_clean_data

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        df_cleaned = fetch_and_clean_data()
        df_cleaned.to_csv(TEMP_CSV_PATH, index=False, encoding="utf-8-sig")
        print(f"清洗结果: {TEMP_CSV_PATH}")

    run_top2000(TEMP_CSV_PATH)
