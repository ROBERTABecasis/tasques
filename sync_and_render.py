"""
Dashboard tasques de la llar — Sync + genera data.json
"""

import os
import sys
import json
from collections import defaultdict
from datetime import datetime
import urllib.request
import urllib.error

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


def sync_historial(tasks, history):
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
        http_request("POST", f"{BASE_URL}/pages", payload)
        new_entries.append({"task": task_name, "date": last_done, "who": who})

    return new_entries


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

    if new_entries:
        history = query_data_source(HISTORIAL_DS_ID)

    print("\n📊 Generant data.json...")
    entries = []
    for entry in history:
        title = get_title(prop(entry, "Tasca feta"))
        date = get_date(prop(entry, "Data"))
        who = get_select(prop(entry, "Qui"))
        if title and date and who:
            entries.append({"task": title, "date": date, "who": who})

    data = {
        "entries": sorted(entries, key=lambda e: e["date"], reverse=True),
        "updated": datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),
        "new_count": len(new_entries),
    }

    with open("data.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"✅ data.json generat ({len(entries)} entrades)")


if __name__ == "__main__":
    main()
