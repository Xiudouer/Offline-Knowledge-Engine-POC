"""需要完整离线包已启动；本示例不包含凭据。"""
import json
from pathlib import Path
import urllib.request

root = Path(__file__).resolve().parents[1]
token = (root / "private-state/access-token.txt").read_text("utf8").strip()
request = urllib.request.Request(
    "http://127.0.0.1:18787/api/ask",
    data=json.dumps({"question": "示例制度的备份周期和保留时间是什么？"}).encode("utf8"),
    headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    method="POST",
)
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open(request, timeout=180) as response:
    result = json.load(response)
print(json.dumps(result, ensure_ascii=False, indent=2))
