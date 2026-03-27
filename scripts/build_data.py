#!/usr/bin/env python3
"""
知行社信息中台 - 数据聚合脚本
从 memory 目录、草稿、情报、待办等来源汇聚为 data.json
"""

import os, json, re, glob
from datetime import datetime, timezone, timedelta

WORKSPACE = "/root/.openclaw/workspace"
BOTS = f"{WORKSPACE}/bots"
OUTPUT = f"{WORKSPACE}/info-dashboard/data.json"

CST = timezone(timedelta(hours=8))
now = datetime.now(CST)
today_str = now.strftime("%Y-%m-%d")

items = []
item_id = 0

def add(category, title, body="", date=None, priority="low", tags=None, source=None, url=None):
    global item_id
    item_id += 1
    items.append({
        "id": item_id,
        "category": category,
        "title": title,
        "body": body if body else "",  # 不截断，前端自行处理
        "date": date or today_str + "T00:00",
        "priority": priority,
        "tags": tags or [],
        "source": source,
        "url": url,
    })

# ─── 1. 待办（从主 memory 提取未完成 [ ] ）───────────────────────────────
def load_todos():
    memory_dir = f"{WORKSPACE}/memory"
    # 扫描最近14天日志
    for i in range(14):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        f = f"{memory_dir}/{d}.md"
        if not os.path.exists(f):
            continue
        with open(f) as fp:
            content = fp.read()
        for line in content.split("\n"):
            if re.match(r"\s*- \[ \]", line):
                text = re.sub(r"\s*- \[ \]\s*", "", line).strip()
                if len(text) < 5:
                    continue
                # 优先级判断
                priority = "mid"
                if any(kw in text for kw in ["紧急","立即","今天","今日","🔴"]):
                    priority = "high"
                add("todo", text, date=f"{d}T08:00", priority=priority,
                    tags=["待办"], source=f"memory/{d}.md")

# ─── 2. 草稿（从笔杆子 memory 抓 final / 近期 draft）────────────────────
def load_drafts():
    ghost_mem = f"{BOTS}/ghostwriter/memory"
    for f in sorted(glob.glob(f"{ghost_mem}/*draft*.md"), reverse=True)[:20]:
        fname = os.path.basename(f)
        with open(f) as fp:
            lines = fp.readlines()
        title = ""
        for l in lines[:5]:
            m = re.match(r"^#+\s+(.+)", l.strip())
            if m:
                title = m.group(1).strip("《》")
                break
        if not title:
            continue
        # 读取全文（供详情展示）
        full_body = "".join(lines)
        # 摘要（前3段非空行）
        body_lines = [l.strip() for l in lines[5:15] if l.strip() and not l.startswith("#")]
        body = full_body  # 保存全文到 body
        # 日期从文件名
        dm = re.match(r"(\d{4}-\d{2}-\d{2})", fname)
        date = dm.group(1) + "T09:00" if dm else today_str + "T09:00"
        # 是否已审核
        is_final = "final" in fname
        priority = "mid" if is_final else "low"
        tags = ["草稿", "已审核" if is_final else "待审核"]
        add("draft", f"《{title}》", body=body, date=date,
            priority=priority, tags=tags, source="笔杆子")

# ─── 3. 情报（从侦察兵 memory 抓 intel 日志）─────────────────────────────
def load_intel():
    scout_mem = f"{BOTS}/scout/memory"
    for f in sorted(glob.glob(f"{scout_mem}/*intel*.md"), reverse=True)[:5]:
        fname = os.path.basename(f)
        dm = re.match(r"(\d{4}-\d{2}-\d{2})", fname)
        date_prefix = dm.group(1) if dm else today_str

        with open(f) as fp:
            content = fp.read()

        # 提取每条情报（### 标题开头）
        blocks = re.split(r"\n---\n", content)
        for block in blocks:
            # 找标题
            title_m = re.search(r"###.*?｜\s*(.+)", block)
            if not title_m:
                title_m = re.search(r"^###\s+(.+)", block, re.MULTILINE)
            if not title_m:
                continue
            title = title_m.group(1).strip()
            if len(title) < 5:
                continue

            # 评分
            score_m = re.search(r"评分[：:]\s*(\d+)分", block)
            score = int(score_m.group(1)) if score_m else 60
            priority = "high" if score >= 80 else "mid" if score >= 65 else "low"

            # 摘要
            summary_m = re.search(r"摘要[：:]\s*(.+?)(?:\n|$)", block, re.DOTALL)
            body = summary_m.group(1).strip()[:250] if summary_m else ""

            # URL
            url_m = re.search(r"https?://\S+", block)
            url = url_m.group(0) if url_m else None

            # 时间（从抓取时间行）
            time_m = re.search(r"抓取时间[：:]\s*\S+\s*（(\S+)）", block)
            time_str = time_m.group(1) if time_m else "08:00"

            add("intel", title, body=body, date=f"{date_prefix}T{time_str[:5] if len(time_str)>=5 else '08:00'}",
                priority=priority, tags=["情报", f"评分{score}"], source="侦察兵", url=url)

# ─── 4. AI简报（从今日 memory 日志抓 cron 推送摘要）──────────────────────
def load_news():
    for i in range(7):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        f = f"{WORKSPACE}/memory/{d}.md"
        if not os.path.exists(f):
            continue
        with open(f) as fp:
            content = fp.read()
        # 找 cron 任务块
        for m in re.finditer(r"## (0[68]:00|08:[13]0|14:|16:|21:).+\n([\s\S]{50,400}?)(?=\n## |$)", content):
            section_title = m.group(0).split("\n")[0].replace("##","").strip()
            body_text = m.group(2).strip()
            if len(body_text) < 20:
                continue
            # 提炼要点
            bullets = [l.strip() for l in body_text.split("\n") if re.match(r"[-*•]", l.strip())]
            body = " · ".join(bullets[:3]) if bullets else body_text[:150]
            add("news", section_title, body=body, date=f"{d}T08:00",
                priority="mid", tags=["简报", d], source="猫巴士")

# ─── 5. Idea Bank（从 memory/idea_bank.md）───────────────────────────────
def load_ideas():
    f = f"{WORKSPACE}/memory/idea_bank.md"
    if not os.path.exists(f):
        return
    with open(f) as fp:
        content = fp.read()
    # 提取每个 idea 块
    for m in re.finditer(r"#+\s+(.+?)\n([\s\S]{30,500}?)(?=\n#+|\Z)", content):
        title = m.group(1).strip()
        body = m.group(2).strip()
        if len(title) < 3 or title.startswith("Idea Bank"):
            continue
        # 商业潜力
        stars = len(re.findall(r"⭐", body))
        priority = "high" if stars >= 5 else "mid" if stars >= 3 else "low"
        add("idea", title, body=body[:200], date=today_str+"T00:00",
            priority=priority, tags=["创意", "Idea Bank"], source="idea_bank.md")

# ─── 6. 从 Telegram 记录抓「记下这个想法」──────────────────────────────────
def load_telegram_ideas():
    """
    扫描今日 memory 日志，找「记下」「想法」「idea」关键词记录的条目
    这些来自 Telegram 对话中董事长说「记下这个想法：xxx」的内容
    """
    for i in range(7):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        f = f"{WORKSPACE}/memory/{d}.md"
        if not os.path.exists(f):
            continue
        with open(f) as fp:
            lines = fp.readlines()
        for j, line in enumerate(lines):
            if re.search(r"(记下|想法|idea|Idea|点子).*[：:]", line, re.IGNORECASE):
                title = re.sub(r"^[-*#\s]+", "", line).strip()
                if len(title) < 5:
                    continue
                body = ""
                for k in range(j+1, min(j+4, len(lines))):
                    if lines[k].strip() and not lines[k].startswith("#"):
                        body += lines[k].strip() + " "
                add("idea", title, body=body[:200], date=f"{d}T00:00",
                    priority="mid", tags=["创意", "Telegram"], source="Telegram")

# ─── 7. 市场数据（从 data.json / eth-data.json 抓关键值）─────────────────
def load_market():
    btc_file = f"{WORKSPACE}/btc-dashboard/data.json"
    if os.path.exists(btc_file):
        try:
            with open(btc_file) as fp:
                d = json.load(fp)
            updated = d.get("updatedAt", today_str)
            rate = d.get("fundingRate", "--")
            stablecoin = d.get("stablecoinTrend", "--")
            body = f"资金费率：{rate} | 稳定币趋势：{stablecoin} | 数据时间：{updated}"
            add("market", "BTC 链上数据快照", body=body,
                date=today_str+"T08:00", priority="low",
                tags=["BTC","市场"], source="btc-dashboard",
                url="https://btc.zhixingshe.cc")
        except:
            pass



# ─── 图片库（Designer 生成图片）─────────────────────────────────────
def load_images():
    img_dir = f"{WORKSPACE}/info-dashboard/images/designer"
    if not os.path.exists(img_dir):
        return
    exts = (".png", ".jpg", ".jpeg", ".webp")
    files = sorted(
        [f for f in os.listdir(img_dir) if f.lower().endswith(exts)],
        reverse=True
    )
    for fname in files:
        # 从文件名提取日期
        dm = re.match(r"(\d{4}-\d{2}-\d{2})", fname)
        date = dm.group(1) + "T00:00" if dm else today_str + "T00:00"
        # 生成标题（去掉日期和扩展名）
        title = re.sub(r"^\d{4}-\d{2}-\d{2}[-_]?\d*[-_]?", "", fname)
        title = re.sub(r"\.(png|jpg|jpeg|webp)$", "", title, flags=re.IGNORECASE)
        title = title.replace("-", " ").replace("_", " ").strip() or fname
        # url = 相对路径（Vercel 托管）
        url = f"/images/designer/{fname}"
        add("image", title, body=fname,
            date=date, priority="low",
            tags=["图片", "Designer"],
            source="Designer", url=url)

# ─── 8. 直接记录的想法（来自 ideas.json）────────────────────────────────
def load_ideas_json():
    f = f"{WORKSPACE}/info-dashboard/ideas.json"
    if not os.path.exists(f):
        return
    with open(f) as fp:
        ideas = json.load(fp)
    for idea in ideas:
        add("idea", idea.get("text","")[:60], body=idea.get("text",""),
            date=idea.get("date", today_str+"T00:00"),
            priority="mid", tags=idea.get("tags", ["Telegram想法"]),
            source="Telegram")

# ─── 执行 ──────────────────────────────────────────────────────────────────
load_todos()
load_drafts()
load_intel()
load_news()
load_ideas()
load_telegram_ideas()
load_images()
load_ideas_json()
load_market()

# 按时间倒序排列
items.sort(key=lambda x: x["date"], reverse=True)

output = {
    "updatedAt": now.strftime("%Y-%m-%d %H:%M GMT+8"),
    "total": len(items),
    "items": items,
    "agents": [
        {"name": "猫巴士", "role": "总调度", "status": "在线"},
        {"name": "笔杆子", "role": "写作", "status": "在线"},
        {"name": "算盘",   "role": "分析",  "status": "在线"},
        {"name": "侦察兵", "role": "情报",  "status": "在线"},
        {"name": "视觉师", "role": "设计",  "status": "在线"},
        {"name": "图书管理员", "role": "归档", "status": "在线"},
        {"name": "知乎专员", "role": "知乎", "status": "在线"},
    ]
}

with open(OUTPUT, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"✅ 已生成 {len(items)} 条信息 → {OUTPUT}")
print(f"   待办:{sum(1 for i in items if i['category']=='todo')} "
      f"草稿:{sum(1 for i in items if i['category']=='draft')} "
      f"情报:{sum(1 for i in items if i['category']=='intel')} "
      f"简报:{sum(1 for i in items if i['category']=='news')} "
      f"创意:{sum(1 for i in items if i['category']=='idea')} "
      f"市场:{sum(1 for i in items if i['category']=='market')}")
