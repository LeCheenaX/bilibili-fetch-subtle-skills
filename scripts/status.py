#!/usr/bin/env python3
"""
状态管理 — 读取/更新 B站字幕提取状态文件。

状态文件路径: ~/.hermes/credentials/bilibili-subtitle-status.json

自动创建，每日首次使用重置 Kedou 配额。
"""
import os
import json
from datetime import date

STATUS_FILE = os.path.expanduser("~/.hermes/credentials/bilibili-subtitle-status.json")


def load():
    """加载状态文件，每日自动重置配额"""
    today = str(date.today())
    
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE) as f:
            data = json.load(f)
        if data.get("date") == today:
            return data  # 今天已初始化
    
    # 新的一天，重置
    return reset()


def reset():
    """重置为新的一天"""
    data = {
        "date": str(date.today()),
        "api_available": 1,
        "kedou_remaining": 20,
        "base_exists": 1 if os.path.exists(os.path.expanduser(
            "~/.hermes/skills/media/bilibili-subtitle-hybrid/models/base.pt")) else 0,
        "small_exists": 1 if os.path.exists(os.path.expanduser(
            "~/.hermes/skills/media/bilibili-subtitle-hybrid/models/small.pt")) else 0,
    }
    save(data)
    return data


def save(data):
    """保存状态文件"""
    os.makedirs(os.path.dirname(STATUS_FILE), exist_ok=True)
    with open(STATUS_FILE, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def use_kedou(n=1):
    """消耗 Kedou 配额"""
    data = load()
    data["kedou_remaining"] = max(0, data["kedou_remaining"] - n)
    save(data)
    return data["kedou_remaining"]


def set_api_available(val):
    """设置 API 可用状态"""
    data = load()
    data["api_available"] = 1 if val else 0
    save(data)


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "reset":
        data = reset()
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif len(sys.argv) > 2 and sys.argv[1] == "use-kedou":
        remaining = use_kedou(int(sys.argv[2]))
        print(f"kedou_remaining: {remaining}")
    else:
        data = load()
        print(json.dumps(data, indent=2, ensure_ascii=False))
