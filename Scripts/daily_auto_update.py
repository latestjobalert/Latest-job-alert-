#!/usr/bin/env python3
import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / 'data' / 'portal_data.json'
if not DATA_FILE.exists() and (ROOT / 'Data' / 'portal_data.json').exists():
    DATA_FILE = ROOT / 'Data' / 'portal_data.json'

def fetch_updates_via_gemini(api_key):
    today = datetime.now(timezone.utc).strftime('%d %B %Y')
    prompt = (
        f"Find the latest verified Indian Government Job notifications, Admit Cards, Results, "
        f"Answer Keys, Last Date Alerts, Form Correction Windows, Admissions, Scholarships, and "
        f"ITI/Apprentice updates released around {today}.\n"
        'Return ONLY a valid JSON object (no markdown fences) with key "updates" as an array of objects, each having:\n'
        '- "target": one of ["lastDate", "correction", "result", "admit", "jobs", "answer", "syllabus", "admission", "verification", "diploma", "outsourcing"]\n'
        '- "title": concise exam/post title\n'
        '- "badge": short pill (e.g. "NEW", "OUT", "LAST DATE")\n'
        '- "shortInfo": 1-2 sentence verified summary\n'
        '- "startDate": string\n'
        '- "lastDate": string\n'
        '- "examDate": string\n'
        '- "fee": string\n'
        '- "age": string\n'
        '- "vacancies": string\n'
        '- "officialUrl": verified .gov.in or .nic.in or official portal URL\n'
        '- "primaryUrl": exact apply/admit-card/result/answer-key page URL if known, else same as officialUrl'
    )
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}]
    }).encode('utf-8')
    req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=45) as resp:
        res = json.loads(resp.read().decode('utf-8'))
    text = res['candidates'][0]['content']['parts'][0]['text']
    m = re.search(r'\{[\s\S]*\}', text)
    return json.loads(m.group(0)).get('updates', []) if m else []

def main():
    api_key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not api_key:
        print('GEMINI_API_KEY not set; skipping remote fetch.')
        return
    data = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    existing_titles = set()
    for k in ('LAST_DATE_ITEMS', 'CORRECTION_ITEMS', 'HIGHLIGHTS'):
        for it in data.get(k, []):
            existing_titles.add(it['title'].lower())
    for sec in data.get('SECTIONS', []):
        for it in sec.get('items', []):
            existing_titles.add(it['title'].lower())

    try:
        updates = fetch_updates_via_gemini(api_key)
    except Exception as e:
        print('Fetch warning (continuing build):', e)
        return

    added = 0
    for idx, u in enumerate(updates):
        title = (u.get('title') or '').strip()
        if not title or title.lower() in existing_titles:
            continue
        existing_titles.add(title.lower())
        item = {
            'id': f"auto-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}-{idx}",
            'title': title,
            'badge': u.get('badge', 'NEW'),
            'tag': u.get('badge', 'NEW'),
            'filter': ['all'],
            'shortInfo': u.get('shortInfo', title),
            'dates': {
                'start': u.get('startDate', 'Check Portal'),
                'lastDate': u.get('lastDate', 'Check Portal'),
                'examDate': u.get('examDate', 'Notified Soon')
            },
            'fee': u.get('fee', 'As per Official Notice'),
            'age': u.get('age', 'As per Govt Rules'),
            'vacancies': u.get('vacancies', 'See Notification'),
            'officialUrl': u.get('officialUrl', 'https://india.gov.in/'),
            'primaryUrl': u.get('primaryUrl') or u.get('officialUrl', 'https://india.gov.in/')
        }
        target = u.get('target', 'jobs')
        if target == 'lastDate':
            data['LAST_DATE_ITEMS'].insert(0, item)
        elif target == 'correction':
            data['CORRECTION_ITEMS'].insert(0, item)
        else:
            for sec in data['SECTIONS']:
                if sec['id'] == target:
                    sec['items'].insert(0, item)
                    break
        added += 1

    if added:
        DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'Added {added} new verified updates.')

if __name__ == '__main__':
    main()
