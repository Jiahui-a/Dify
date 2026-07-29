#!/usr/bin/env python3
"""本地 Mock OData 服务，便于在没有公司内网时联调拉取流程。"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse

SAMPLE_ROWS = [
    {
        "LineName": "Line-A",
        "StationName": "OP10",
        "FaultType": "设备",
        "EventsName": "气缸异常",
        "BeginTime": "2026-07-28T01:00:00Z",
        "ResponseTime": "2026-07-28T01:02:00Z",
        "EndTime": "2026-07-28T01:20:00Z",
        "ConfirmTime": "2026-07-28T01:21:00Z",
        "ReactionPlan": "更换密封圈",
        "Actions": "拆检更换",
        "Remark": "mock",
        "IsChangeParameter": False,
        "ParameterName": None,
        "OldValue": None,
        "NewValue": None,
        "IsChangeQuipment": True,
        "ChangeEventDesc": "更换气缸",
        "EquipmentPN": "CYL-001",
        "ResponseDuration": 120,
        "RepairDuration": 1080,
        "DowTimeDuration": 1200,
        "ClosePerson": "张三",
        "ResponsePerson": "李四",
    },
    {
        "LineName": "Line-B",
        "StationName": "OP20",
        "FaultType": "质量",
        "EventsName": "扭矩超差",
        "BeginTime": "2026-07-28T02:00:00Z",
        "ResponseTime": "2026-07-28T02:01:00Z",
        "EndTime": "2026-07-28T02:10:00Z",
        "ConfirmTime": "2026-07-28T02:11:00Z",
        "ReactionPlan": "复拧",
        "Actions": "复检放行",
        "Remark": "",
        "IsChangeParameter": True,
        "ParameterName": "Torque",
        "OldValue": "8",
        "NewValue": "10",
        "IsChangeQuipment": False,
        "ChangeEventDesc": None,
        "EquipmentPN": "TQ-002",
        "ResponseDuration": 60,
        "RepairDuration": 540,
        "DowTimeDuration": 600,
        "ClosePerson": "王五",
        "ResponsePerson": "赵六",
    },
]


class Handler(BaseHTTPRequestHandler):
    def _check_auth(self) -> bool:
        key = self.headers.get("api-key") or self.headers.get("X-API-Key")
        qs = parse_qs(urlparse(self.path).query)
        key = key or (qs.get("api-key") or qs.get("apiKey") or [None])[0]
        if key != "demo-key":
            self.send_response(401)
            self.end_headers()
            self.wfile.write(b'{"error":"unauthorized"}')
            return False
        return True

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if not self._check_auth():
            return

        if parsed.path.endswith("/$metadata"):
            body = b'<?xml version="1.0"?><edmx:Edmx Version="4.0"></edmx:Edmx>'
            self.send_response(200)
            self.send_header("Content-Type", "application/xml")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        if parsed.path.rstrip("/").endswith("/odata") or parsed.path.rstrip("/").endswith(
            "/odata/"
        ):
            payload = {
                "value": [
                    {"name": "AndonEvents", "kind": "EntitySet", "url": "AndonEvents"},
                ]
            }
        elif "AndonEvents" in parsed.path:
            qs = parse_qs(parsed.query)
            top = int((qs.get("$top") or ["100"])[0])
            skip = int((qs.get("$skip") or ["0"])[0])
            page = SAMPLE_ROWS[skip : skip + top]
            payload = {"@odata.count": len(SAMPLE_ROWS), "value": page}
        else:
            self.send_response(404)
            self.end_headers()
            return

        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt: str, *args) -> None:  # noqa: A003
        print("[mock]", fmt % args)


if __name__ == "__main__":
    host, port = "127.0.0.1", 8765
    print(f"Mock Andon OData at http://{host}:{port}/odata")
    print("API Key: demo-key  EntitySet: AndonEvents")
    HTTPServer((host, port), Handler).serve_forever()
