#!/bin/bash
# 知行社信息中台 - 每日数据更新
cd /root/.openclaw/workspace/info-dashboard
python3 scripts/build_data.py
git add data.json
git diff --cached --quiet || git commit -m "🔄 数据更新 $(date '+%Y-%m-%d %H:%M')" && git push origin master
