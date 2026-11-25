#!/usr/bin/env python3
import json
import os
import re
import urllib.request
import urllib.error
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / 'data' / 'portal_data.json'
if not DATA_FILE.exists() and (ROOT / 'Data' / 'portal_data.json').exists():
    DATA_FILE = ROOT / 'Data' / 'portal_data.json'

MODELS = ['gemini-3.8-flash', 'gemini-3.6-flash', 'gemini-3.5-flash-lite']

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
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}]
    }).encode('utf-8')

    for model in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                res = json.loads(resp.read().decode('utf-8'))
            print(f'Fetched using Gemini model: {model}')
            text = res['candidates'][0]['content']['parts'][0]['text']
            m = re.search(r'\{[\s\S]*\}', text)
            return json.loads(m.group(0)).get('updates', []) if m else []
        except urllib.error.HTTPError as e:
            if e.code in (404, 429, 503):
                continue
            raise
    return None

def classify_target(title):
    t = title.lower()
    if 'correction' in t or 'edit window' in t:
        return 'correction', 'EDIT'
    if 'last date' in t or 'closing' in t or 'extended' in t:
        return 'lastDate', 'LAST DATE'
    if 'admit card' in t or 'hall ticket' in t or 'city slip' in t:
        return 'admit', 'ADMIT CARD'
    if 'answer key' in t or 'objection' in t:
        return 'answer', 'KEY OUT'
    if 'result' in t or 'score card' in t or 'merit list' in t:
        return 'result', 'RESULT'
    if 'apprentice' in t or 'iti' in t or 'diploma' in t:
        return 'diploma', 'ITI/DIPLOMA'
    if 'scholarship' in t:
        return 'verification', 'SCHOLARSHIP'
    if 'admission' in t or 'jee' in t or 'neet' in t or 'cuet' in t:
        return 'admission', 'ADMISSION'
    return 'jobs', 'NEW'

def fetch_updates_via_rss():
    queries = [
        'SSC OR RRB OR BPSC OR UPSSSC Admit Card Result Answer Key 2026',
        'Sarkari Naukri Latest Govt Jobs Recruitment Notification 2026 India'
    ]
    updates = []
    for q in queries:
        rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=en-IN&gl=IN&ceid=IN:en"
        req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=20) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)
        for item in root.findall('./channel/item')[:6]:
            raw_title = (item.findtext('title') or '').split(' - ')[0].strip()
            link = (item.findtext('link') or 'https://india.gov.in/').strip()
            pub_date = (item.findtext('pubDate') or 'Today')[:16]
            if not raw_title:
                continue
            target, badge = classify_target(raw_title)
            updates.append({
                'target': target,
                'title': raw_title,
                'badge': badge,
                'shortInfo': f"{raw_title}. Published {pub_date}. Check the official notice link below for full details.",
                'startDate': pub_date,
                'lastDate': 'Check Official Notice',
                'examDate': 'As per Schedule',
                'fee': 'As per Official Notice',
                'age': 'As per Govt Rules',
                'vacancies': 'See Notification',
                'officialUrl': link,
                'primaryUrl': link
            })
    print(f'Fetched {len(updates)} items via Google News RSS fallback.')
    return updates

def main():
    data = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    existing_titles = set()
    for k in ('LAST_DATE_ITEMS', 'CORRECTION_ITEMS', 'HIGHLIGHTS'):
        for it in data.get(k, []):
            existing_titles.add(it['title'].lower())
    for sec in data.get('SECTIONS', []):
        for it in sec.get('items', []):
            existing_titles.add(it['title'].lower())

    updates = None
    api_key = os.environ.get('GEMINI_API_KEY', '').strip()
    if api_key:
        try:
            updates = fetch_updates_via_gemini(api_key)
        except Exception as e:
            print('Gemini warning, switching to RSS:', e)
    if not updates:
        try:
            updates = fetch_updates_via_rss()
        except Exception as e:
            print('RSS warning (continuing build):', e)
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
