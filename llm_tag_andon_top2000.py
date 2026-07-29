"""
LLM 语义标签化 - 仅前 2000 条

Dify 配置统一读取 dify_config.py（与 llm_tag_andon_data.py 共用同一套 Key/URL）
- 每 20 条落盘；Ctrl+C 暂停也会保存；再运行可续跑
"""

from __future__ import annotations

import time
from pathlib import Path

import pandas as pd
import urllib3

import llm_tag_andon_data as tagger
from dify_config import DIFY_API_BASE, DIFY_API_KEY, DIFY_VERIFY_SSL, SLEEP_SECONDS
from prepare_andon_data import OUTPUT_DIR, TEMP_CSV_PATH

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

TOP_N = 2000
SAVE_EVERY = 20
OUTPUT_CSV = OUTPUT_DIR / "factory_andon_data_top2000.csv"
TAG_COLS = [
    "action_category",
    "extracted_parts",
    "is_reset_only",
    "extracted_fault_reason",
]


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

    if not DIFY_API_KEY or DIFY_API_KEY == "YOUR_DIFY_APP_API_KEY":
        raise RuntimeError("请先在 dify_config.py 中配置 DIFY_API_KEY")

    if OUTPUT_CSV.exists():
        print(f"发现进度文件，继续: {OUTPUT_CSV}")
        work = pd.read_csv(OUTPUT_CSV)
        work.columns = [str(c).lower() for c in work.columns]
    else:
        df = pd.read_csv(cleaned_csv)
        df.columns = [str(c).lower() for c in df.columns]
        work = df.head(TOP_N).copy().reset_index(drop=True)
        work["full_reaction_text"] = tagger.build_full_reaction_text(work)
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
            # 真正调用 llm_tag_andon_data.call_dify_for_tagging（内部读 dify_config）
            tags = tagger.call_dify_for_tagging(work.at[i, "full_reaction_text"])
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
    print("配置来源: dify_config.py（两脚本共用）")
    print(f"Dify URL : {DIFY_API_BASE}")
    print(f"Verify SSL: {DIFY_VERIFY_SSL}")
    key_preview = (DIFY_API_KEY[:8] + "***") if DIFY_API_KEY else "(空)"
    print(f"API Key  : {key_preview}")
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
