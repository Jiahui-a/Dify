"""
Dify 连接配置（两个打标签脚本共用）

只改这个文件里的 Key / 地址即可。
"""

# 在 Dify 应用「访问 API」里复制 API Key
DIFY_API_KEY = "YOUR_DIFY_APP_API_KEY"

# 自建 Dify 地址（需带 /v1）
DIFY_API_BASE = "https://gongsi.com/v1"

# 内网自签证书：关闭 SSL 校验
DIFY_VERIFY_SSL = False

# 每次调用间隔（秒）
SLEEP_SECONDS = 0.1
