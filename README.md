# 第一步：获取安灯原始数据

## 结论

| 项 | 内容 |
|---|---|
| 存储位置 | 公司 **OData API**（不是直连 MySQL/SQL Server/PostgreSQL） |
| 地址 | `https://gongsi.com:8092/andon`（按你环境改） |
| 表/实体 | `o_d_andon_eventsrawdata_cur` |
| 鉴权 | Header `X-Api-Key` |
| 脚本 | `fetch_andon_events.py` |

## 运行

```bat
pip install -r requirements.txt
python fetch_andon_events.py
```

默认拉取 **近 30 天**（`$filter=begintime ge ...`），超过 2000 条会自动翻页。  
在 `main()` 里可改：`days_back=30`、`top_n=2000`。

输出（`output` 目录）：
- `andon_events_raw.json`：近一个月原始数据
- `andon_events_core.json` / `andon_events_core.csv`：重要字段
