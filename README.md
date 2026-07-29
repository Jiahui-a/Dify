# 安灯数据处理

## 第一步：获取原始数据（近一个月）

```bat
pip install -r requirements.txt
python fetch_andon_events.py
```

- 来源：OData API（非直连数据库）
- 表：`o_d_andon_eventsrawdata_cur`
- 输出：`andon_events_raw.json` / `andon_events_core.csv`

## 数据提取与基础清洗

```bat
python prepare_andon_data.py
```

会再次按近 30 天从 OData 拉取，并做：
1. 字符串去空格  
2. 时间字段转 datetime  
3. 时长字段空值填 0  
4. 过滤无文本且无维修时长的空记录  

输出：
- `factory_andon_data.csv`
- `temp_cleaned_andon_data.csv`

配置在各自脚本的 `main` / `API_CONFIG` 中修改 `base_url`、`api_key`、`days_back`。
