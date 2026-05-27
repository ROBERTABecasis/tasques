"""
Dashboard tasques de la llar
=============================
Script que:
1. Sincronitza l'historial (si alguna tasca de la BD principal té una data nova
   que no està al historial, l'afegeix).
2. Genera un dashboard HTML (index.html) amb les estadístiques.

S'executa cada dia via GitHub Actions i publica el HTML a GitHub Pages.
"""

import os
import sys
import json
from collections import defaultdict
from datetime import datetime
import urllib.request
import urllib.error

# ---------- Configuració ----------
NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
if not NOTION_TOKEN:
    print("❌ Falta NOTION_TOKEN")
    sys.exit(1)

TASKS_DS_ID = "0f191b14-c6b0-4baa-976d-d4ef7065ddec"
HISTORIAL_DS_ID = "41bb1478-0e6f-4976-831d-4eddf599af01"
NOTION_API_VERSION = "2025-09-03"
BASE_URL = "https://api.notion.com/v1"

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": NOTION_API_VERSION,
    "Content-Type": "application/json",
}

# Colors per cada persona
COLORS = {
    "Emma": {"main": "#ff7eb0", "bg": "#ffd0e0", "text": "#b03060", "gradient": "linear-gradient(135deg, #ffe1ec 0%, #ffd0e0 100%)"},
    "Robert": {"main": "#5b8def", "bg": "#bcd0ff", "text": "#2851b0", "gradient": "linear-gradient(135deg, #d6e4ff 0%, #bcd0ff 100%)"},
    "Els dos": {"main": "#6dd58c", "bg": "#c5ecd0", "text": "#1f7a3a", "gradient": "linear-gradient(135deg, #d8f5e0 0%, #c5ecd0 100%)"},
}


# ---------- Helpers HTTP ----------
def http_request(method, url, payload=None):
    data = json.dumps(payload).encode() if payload else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP {e.code}: {e.read().decode()}")
        raise


def query_data_source(ds_id):
    """Recupera totes les pàgines amb paginació."""
    results = []
    payload = {"page_size": 100}
    url = f"{BASE_URL}/data_sources/{ds_id}/query"

    while True:
        data = http_request("POST", url, payload)
        results.extend(data.get("results", []))
        if not data.get("has_more"):
            break
        payload["start_cursor"] = data["next_cursor"]

    return results


# ---------- Property extractors ----------
def prop(page, name):
    return page.get("properties", {}).get(name)


def get_date(p):
    if not p or p.get("type") != "date" or not p.get("date"):
        return None
    return p["date"].get("start")


def get_select(p):
    if not p or p.get("type") != "select" or not p.get("select"):
        return None
    return p["select"].get("name")


def get_title(p):
    if not p or p.get("type") != "title":
        return ""
    return "".join(rt.get("plain_text", "") for rt in p.get("title", []))


def get_relation(p):
    if not p or p.get("type") != "relation":
        return []
    return [r["id"] for r in p.get("relation", [])]


# ---------- Sync logic ----------
def sync_historial(tasks, history):
    """Si una tasca té una data que no està al historial, la registra."""
    history_by_task = defaultdict(set)
    for entry in history:
        date = get_date(prop(entry, "Data"))
        for tid in get_relation(prop(entry, "Tasca")):
            if date:
                history_by_task[tid].add(date)

    new_entries = []
    for task in tasks:
        task_id = task["id"]
        task_name = get_title(prop(task, "Tasca"))
        last_done = get_date(prop(task, "Darrera vegada fet"))
        who = get_select(prop(task, "Qui ho ha fet per ultim cop"))

        if not last_done or not who:
            continue
        if last_done in history_by_task[task_id]:
            continue

        print(f"➕ {task_name} - {last_done} - {who}")
        payload = {
            "parent": {"type": "data_source_id", "data_source_id": HISTORIAL_DS_ID},
            "properties": {
                "Tasca feta": {"title": [{"type": "text", "text": {"content": task_name}}]},
                "Data": {"date": {"start": last_done}},
                "Qui": {"select": {"name": who}},
                "Tasca": {"relation": [{"id": task_id}]},
            },
        }
        result = http_request("POST", f"{BASE_URL}/pages", payload)
        new_entries.append({
            "title": task_name,
            "date": last_done,
            "who": who,
        })

    return new_entries


# ---------- Dashboard generation ----------
def generate_dashboard(history, new_entries_count):
    """Genera index.html amb les estadístiques."""
    # Extraure entrades vàlides
    entries = []
    for entry in history:
        title = get_title(prop(entry, "Tasca feta"))
        date = get_date(prop(entry, "Data"))
        who = get_select(prop(entry, "Qui"))
        if title and date and who:
            entries.append({"title": title, "date": date, "who": who})

    # Afegim les que acabem de crear (per si el sync no està reflectit encara)
    # (En realitat ja són dins, però per si de cas refresquem)

    # Comptadors
    by_person = defaultdict(int)
    by_task = defaultdict(lambda: defaultdict(int))
    for e in entries:
        if e["who"] == "Els dos":
            by_person["Emma"] += 1
            by_person["Robert"] += 1
        else:
            by_person[e["who"]] += 1
        by_task[e["title"]][e["who"]] += 1

    emma_score = by_person.get("Emma", 0)
    robert_score = by_person.get("Robert", 0)
    total = emma_score + robert_score
    emma_pct = (emma_score / total * 100) if total else 0
    robert_pct = (robert_score / total * 100) if total else 0

    # Determinar "guanyador"
    if emma_score > robert_score:
        emma_badge = "🏆 al podi"
        robert_badge = "💪 puja, puja"
    elif robert_score > emma_score:
        emma_badge = "💪 puja, puja"
        robert_badge = "🏆 al podi"
    else:
        emma_badge = "🤝 empat"
        robert_badge = "🤝 empat"

    # Ordre per tasca: més freqüents primer
    task_totals = {t: sum(v.values()) for t, v in by_task.items()}
    sorted_tasks = sorted(by_task.items(), key=lambda x: -task_totals[x[0]])

    # Últimes 10 entrades
    recent = sorted(entries, key=lambda e: e["date"], reverse=True)[:10]

    # Render HTML
    bars_html = ""
    for task_name, counts in sorted_tasks:
        total_task = sum(counts.values())
        # Convertim "Els dos" en 50/50 a Emma i Robert per la barra
        emma_t = counts.get("Emma", 0) + counts.get("Els dos", 0) * 0.5
        robert_t = counts.get("Robert", 0) + counts.get("Els dos", 0) * 0.5

        bar_total = emma_t + robert_t
        if bar_total == 0:
            continue
        emma_w = (emma_t / bar_total) * 100
        robert_w = (robert_t / bar_total) * 100

        # Truncar nom llarg
        display_name = task_name if len(task_name) <= 18 else task_name[:17] + "…"

        bars_html += f"""
        <div class="bar-row">
          <div class="bar-label" title="{task_name}">{display_name}</div>
          <div class="bar-container">
            <div class="bar-emma" style="width: {emma_w}%;"></div>
            <div class="bar-robert" style="width: {robert_w}%;"></div>
          </div>
          <div class="bar-count">{total_task}</div>
        </div>
        """

    recent_html = ""
    for e in recent:
        dt = datetime.strptime(e["date"], "%Y-%m-%d")
        date_label = dt.strftime("%d/%m")
        who_class = {"Emma": "who-emma", "Robert": "who-robert", "Els dos": "who-both"}.get(e["who"], "who-emma")
        recent_html += f"""
        <div class="recent-item">
          <span class="recent-task">{e['title']}</span>
          <div class="recent-meta">
            <span class="recent-date">{date_label}</span>
            <span class="recent-who {who_class}">{e['who']}</span>
          </div>
        </div>
        """

    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    new_badge = f"<span class='new-badge'>+{new_entries_count} avui</span>" if new_entries_count else ""

    html = f"""<!DOCTYPE html>
<html lang="ca">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<meta name="theme-color" content="#fafaf8">
<title>🏠 Dashboard de la llar</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    color: #2d2d2d;
    padding: 20px;
    background: #fafaf8;
    max-width: 600px;
    margin: 0 auto;
    -webkit-font-smoothing: antialiased;
  }}
  .header {{ text-align: center; margin-bottom: 28px; }}
  .header h1 {{ font-size: 24px; margin-bottom: 4px; }}
  .header p {{ color: #888; font-size: 13px; }}
  .new-badge {{
    display: inline-block;
    background: #6dd58c;
    color: #1f5a2e;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 8px;
    border-radius: 8px;
    margin-left: 6px;
  }}

  .score {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 24px; }}
  .card {{ border-radius: 14px; padding: 18px; text-align: center; }}
  .card.emma {{ background: {COLORS['Emma']['gradient']}; }}
  .card.robert {{ background: {COLORS['Robert']['gradient']}; }}
  .card .name {{ font-size: 13px; font-weight: 600; margin-bottom: 4px; opacity: 0.65; letter-spacing: 0.5px; }}
  .card .num {{ font-size: 42px; font-weight: 700; line-height: 1; }}
  .card .label {{ font-size: 11px; opacity: 0.6; margin-top: 4px; }}
  .winner {{ margin-top: 10px; font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 12px; display: inline-block; background: rgba(255,255,255,0.7); }}

  .ratio-bar {{ height: 12px; border-radius: 6px; overflow: hidden; display: flex; margin-bottom: 8px; background: #eee; }}
  .ratio-emma {{ background: {COLORS['Emma']['main']}; }}
  .ratio-robert {{ background: {COLORS['Robert']['main']}; }}
  .ratio-labels {{ display: flex; justify-content: space-between; font-size: 11px; color: #888; margin-bottom: 28px; }}

  .section {{ margin-bottom: 26px; }}
  .section h2 {{ font-size: 15px; font-weight: 600; margin-bottom: 14px; color: #444; }}

  .bar-row {{ display: flex; align-items: center; margin-bottom: 10px; gap: 10px; }}
  .bar-label {{ width: 115px; font-size: 12px; color: #555; flex-shrink: 0; line-height: 1.2; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
  .bar-container {{ flex: 1; height: 22px; background: #f0f0ee; border-radius: 6px; display: flex; overflow: hidden; }}
  .bar-emma {{ background: {COLORS['Emma']['main']}; height: 100%; }}
  .bar-robert {{ background: {COLORS['Robert']['main']}; height: 100%; }}
  .bar-count {{ font-size: 11px; font-weight: 600; color: #555; min-width: 22px; text-align: right; }}

  .recent-list {{ background: white; border-radius: 12px; padding: 4px 14px; border: 1px solid #f0f0ee; }}
  .recent-item {{ display: flex; justify-content: space-between; align-items: center; padding: 9px 0; font-size: 13px; border-bottom: 1px solid #f5f5f3; }}
  .recent-item:last-child {{ border-bottom: none; }}
  .recent-task {{ color: #333; }}
  .recent-meta {{ display: flex; gap: 8px; align-items: center; }}
  .recent-who {{ font-weight: 600; padding: 3px 9px; border-radius: 8px; font-size: 11px; }}
  .who-emma {{ background: {COLORS['Emma']['bg']}; color: {COLORS['Emma']['text']}; }}
  .who-robert {{ background: {COLORS['Robert']['bg']}; color: {COLORS['Robert']['text']}; }}
  .who-both {{ background: {COLORS['Els dos']['bg']}; color: {COLORS['Els dos']['text']}; }}
  .recent-date {{ color: #aaa; font-size: 11px; }}

  .footer {{ text-align: center; color: #aaa; font-size: 11px; margin-top: 30px; }}
</style>
</head>
<body>

<div class="header">
  <h1>🏠 Dashboard de la llar</h1>
  <p>{len(entries)} tasques registrades {new_badge}</p>
</div>

<div class="score">
  <div class="card emma">
    <div class="name">EMMA</div>
    <div class="num">{emma_score}</div>
    <div class="label">tasques fetes</div>
    <div class="winner">{emma_badge}</div>
  </div>
  <div class="card robert">
    <div class="name">ROBERT</div>
    <div class="num">{robert_score}</div>
    <div class="label">tasques fetes</div>
    <div class="winner">{robert_badge}</div>
  </div>
</div>

<div class="ratio-bar">
  <div class="ratio-emma" style="width: {emma_pct:.1f}%;"></div>
  <div class="ratio-robert" style="width: {robert_pct:.1f}%;"></div>
</div>
<div class="ratio-labels">
  <span>Emma {emma_pct:.0f}%</span>
  <span>Robert {robert_pct:.0f}%</span>
</div>

<div class="section">
  <h2>Per tasca</h2>
  {bars_html}
</div>

<div class="section">
  <h2>Últimes tasques fetes</h2>
  <div class="recent-list">
    {recent_html}
  </div>
</div>

<div class="footer">Actualitzat: {now}</div>

</body>
</html>
"""

    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html)
    print("✅ index.html generat")


# ---------- Main ----------
def main():
    print("🔍 Llegint tasques...")
    tasks = query_data_source(TASKS_DS_ID)
    print(f"   {len(tasks)} tasques")

    print("🔍 Llegint historial...")
    history = query_data_source(HISTORIAL_DS_ID)
    print(f"   {len(history)} entrades")

    print("\n🔄 Sincronitzant...")
    new_entries = sync_historial(tasks, history)
    print(f"   {len(new_entries)} entrades noves")

    # Si hi ha entrades noves, les afegim a l'historial local per al render
    if new_entries:
        history = query_data_source(HISTORIAL_DS_ID)

    print("\n📊 Generant dashboard...")
    generate_dashboard(history, len(new_entries))
    print("✅ Tot llest")


if __name__ == "__main__":
    main()
