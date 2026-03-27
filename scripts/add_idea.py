#!/usr/bin/env python3
"""
快速添加想法到 info-dashboard
用法: python3 add_idea.py "想法内容" [标签1,标签2]
由猫巴士在 Telegram 收到「记下想法」时调用
"""
import sys, json, os
from datetime import datetime, timezone, timedelta

CST = timezone(timedelta(hours=8))
now = datetime.now(CST)

IDEAS_FILE = "/root/.openclaw/workspace/info-dashboard/ideas.json"

# 读取现有
if os.path.exists(IDEAS_FILE):
    with open(IDEAS_FILE) as f:
        ideas = json.load(f)
else:
    ideas = []

# 新想法
text = sys.argv[1] if len(sys.argv) > 1 else ""
tags_raw = sys.argv[2] if len(sys.argv) > 2 else ""
tags = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []
tags = ["Telegram想法"] + tags

if not text:
    print("❌ 请提供想法内容")
    sys.exit(1)

idea = {
    "id": len(ideas) + 1,
    "text": text,
    "tags": tags,
    "date": now.strftime("%Y-%m-%dT%H:%M"),
    "source": "Telegram"
}

ideas.insert(0, idea)  # 最新的放最前

with open(IDEAS_FILE, "w", encoding="utf-8") as f:
    json.dump(ideas, f, ensure_ascii=False, indent=2)

print(f"✅ 已记录：{text}")
print(f"   标签：{', '.join(tags)}")
print(f"   时间：{idea['date']}")
