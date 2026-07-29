"""
数据提取与基础清洗

数据来源：公司 OData API（与 fetch_andon_events.py 相同，非直连 MySQL）
表/实体：o_d_andon_eventsrawdata_cur
输出：基础清洗后的 CSV，供后续分析 / LLM 使用
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from fetch_andon_events import CORE_FIELDS, ApiConfig, fetch_latest_events

# --- 配置（与已跑通脚本保持一致）---
API_CONFIG = ApiConfig(
    base_url="https://gongsi.com:8092/andon",
    endpoint="o_d_andon_eventsrawdata_cur",
    api_key="zidingyi",
    auth_header="X-Api-Key",
    verify_ssl=False,
    top_n=2000,
    days_back=30,  # 近一个月；若要一年可改 365
)

OUTPUT_DIR = Path(r"C:\Users\CHJ1WUJ\personal\api_anything\output")
OUTPUT_CSV_PATH = OUTPUT_DIR / "factory_andon_data.csv"
TEMP_CSV_PATH = OUTPUT_DIR / "temp_cleaned_andon_data.csv"

# 清洗用到的字段（含模板中的 changedesc；接口没有则自动忽略）
CLEAN_FIELDS = list(CORE_FIELDS) + ["changedesc"]


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """字段名统一小写，便于对齐。"""
    df = df.copy()
    df.columns = [str(c).lower() for c in df.columns]
    return df


def _ensure_columns(df: pd.DataFrame, fields: list[str]) -> pd.DataFrame:
    for col in fields:
        if col not in df.columns:
            df[col] = pd.NA
    return df


def basic_clean(df: pd.DataFrame) -> pd.DataFrame:
    """基础清洗（按你提供的规则）。"""
    df = _normalize_columns(df)
    df = _ensure_columns(df, CLEAN_FIELDS)

    # 只保留分析相关列（有则保留）
    keep = [c for c in CLEAN_FIELDS if c in df.columns]
    df = df[keep].copy()

    # 1. 字符串列 strip
    for col in df.select_dtypes(include=["object"]).columns:
        df[col] = df[col].apply(lambda x: x.strip() if isinstance(x, str) else x)

    # 2. 时间字段转 datetime
    time_cols = ["begintime", "responsetime", "endtime", "confirmtime"]
    for col in time_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # 3. 数字时长字段填 0
    for col in ["responseduration", "repairduration", "dowtimeduration"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    # 4. 过滤无意义空记录：
    #    reactionplan / actions / remark / changedesc / changeeventdesc 至少一个有内容
    #    或 repairduration > 0
    text_cols = [
        c
        for c in ["reactionplan", "actions", "remark", "changedesc", "changeeventdesc"]
        if c in df.columns
    ]
    has_text = False
    for col in text_cols:
        cond = df[col].notna() & (df[col].astype(str).str.strip() != "")
        has_text = cond if has_text is False else (has_text | cond)

    if has_text is False:
        has_text = pd.Series([False] * len(df), index=df.index)

    has_repair = (
        df["repairduration"] > 0
        if "repairduration" in df.columns
        else pd.Series([False] * len(df), index=df.index)
    )

    df_filtered = df[has_text | has_repair].copy()
    return df_filtered


def fetch_and_clean_data() -> pd.DataFrame:
    print("正在从 OData API 拉取近一个月原始数据...")
    print(f"地址: {API_CONFIG.base_url}")
    print(f"表/实体: {API_CONFIG.endpoint}")
    print(f"天数: 近 {API_CONFIG.days_back} 天")

    records = fetch_latest_events(API_CONFIG)
    print(f"拉取到 {len(records)} 条数据。")

    if not records:
        return pd.DataFrame(columns=CLEAN_FIELDS)

    df = pd.DataFrame(records)
    df_cleaned = basic_clean(df)
    print(f"基础清洗后剩余 {len(df_cleaned)} 条有效数据。")
    return df_cleaned


if __name__ == "__main__":
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    df_cleaned = fetch_and_clean_data()
    df_cleaned.to_csv(OUTPUT_CSV_PATH, index=False, encoding="utf-8-sig")
    df_cleaned.to_csv(TEMP_CSV_PATH, index=False, encoding="utf-8-sig")

    print(f"清洗结果已保存: {OUTPUT_CSV_PATH}")
    print(f"临时文件已保存: {TEMP_CSV_PATH}")
