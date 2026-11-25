#!/usr/bin/env python3
import json
import os
import re
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / 'data' if (ROOT / 'data').exists() else ROOT / 'Data'
DATA_FILE = DATA_DIR / 'portal_data.json'

MODELS = ['gemini-3.8-flash', 'gemini-3.6-flash', 'gemini-3.5-flash-lite']

def fetch_syllabus_details(topic):
    prompt = (
        f"Provide a structured exam pattern and syllabus breakdown for '{topic}'. "
        "Return ONLY a JSON object with keys 'pattern' (brief string) and 'rows' (array of arrays, "
        "each having [Subject/Paper, Marks/Questions, Detailed Topics]). If unknown, return empty pattern and rows."
    )
    payload = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "tools": [{"google_search": {}}]
    }).encode('utf-8')
    
    api_key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not api_key:
        return None

    for model in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                res = json.loads(resp.read().decode('utf-8'))
            text = res['candidates'][0]['content']['parts'][0]['text']
            m = re.search(r'\{[\s\S]*\}', text)
            if m:
                return json.loads(m.group(0))
        except Exception:
            continue
    return None

def fetch_automated_updates(api_key):
    today = datetime.now(timezone.utc).strftime('%d %B %Y')
    prompt = (
        f"Find the latest verified Indian Government Job notifications, Admit Cards, Results, "
        f"Answer Keys, Last Date Alerts, Form Correction Windows, Admissions, Scholarships, and "
        f"ITI/Apprentice updates released around {today}.\n"
        'Return ONLY a valid JSON object (no markdown fences) with key "updates" as an array of objects, each having:\n'
'Write completely original summaries in simple language.'
        '- "target": one of ["lastDate", "correction", "result", "admit", "jobs", "answer", "syllabus", "admission", "verification", "diploma", "outsourcing"]\n'
        '- "title": concise, accurate exam/post title in English\n'
        '- "badge": short pill (e.g. "NEW", "OUT", "LAST DATE", "LINK")\n'
        '- "shortInfo": 1-2 sentence verified summary\n'
        '- "startDate": string\n'
        '- "lastDate": string\n'
        '- "examDate": string\n'
        '- "fee": string\n'
        '- "age": string\n'
        '- "vacancies": string\n'
        '- "primaryUrl": exact official direct URL for applying, downloading admit card, result PDF, answer key PDF, or correction portal (MUST be a direct deep link if available, otherwise official homepage)\n'
        '- "secondaryUrl": alternative official URL or notification notice URL\n'
        '- "officialUrl": main department official website homepage\n'
        '- "examPattern": (optional) string describing exam scheme if target is syllabus\n'
        '- "syllabusDetails": (optional) array of objects [{"subject": "...", "weight": "...", "topics": "..."}] if target is syllabus'
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
            text = res['candidates'][0]['content']['parts'][0]['text']
            m = re.search(r'\{[\s\S]*\}', text)
            if m:
                return json.loads(m.group(0)).get('updates', [])
        except urllib.error.HTTPError as e:
            if e.code in (404, 429, 503):
                continue
            raise
    return None

def main():
    if not DATA_FILE.exists():
        print(f"Data file not found at {DATA_FILE}")
        return

    data = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    existing_titles = set()
    for k in ('LAST_DATE_ITEMS', 'CORRECTION_ITEMS', 'HIGHLIGHTS'):
        for it in data.get(k, []):
            existing_titles.add(it['title'].lower())
    for sec in data.get('SECTIONS', []):
        for it in sec.get('items', []):
            existing_titles.add(it['title'].lower())

    api_key = os.environ.get('GEMINI_API_KEY', '').strip()
    if not api_key:
        print("No GEMINI_API_KEY provided.")
        return

    updates = fetch_automated_updates(api_key)
    if not updates:
        print("Failed to fetch updates via Gemini.")
        return

    added = 0
    now_str = datetime.now(timezone.utc).strftime('%Y%m%d%H%M')

    for idx, u in enumerate(updates):
        title = (u.get('title') or '').strip()
        if not title or title.lower() in existing_titles:
            continue
        existing_titles.add(title.lower())
        
        target = u.get('target', 'jobs')
        primary_url = u.get('primaryUrl') or 'https://india.gov.in/'
        secondary_url = u.get('secondaryUrl') or primary_url
        official_url = u.get('officialUrl') or primary_url

        item = {
            'id': f"auto-{now_str}-{idx}",
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
            'officialUrl': official_url,
            'primaryUrl': primary_url,
            'secondaryUrl': secondary_url
        }

        if target == 'syllabus':
            pattern = u.get('examPattern', '')
            syl_rows = u.get('syllabusDetails')
            if not syl_rows:
                fetched = fetch_syllabus_details(title)
                if fetched:
                    pattern = fetched.get('pattern', pattern)
                    syl_rows = fetched.get('rows', [])
            item['examPattern'] = pattern
            item['syllabusDetails'] = syl_rows

        if target == 'lastDate':
            data['LAST_DATE_ITEMS'].insert(0, item)
        elif target == 'correction':
            data['CORRECTION_ITEMS'].insert(0, item)
        else:
            inserted = False
            for sec in data['SECTIONS']:
                if sec['id'] == target:
                    sec['items'].insert(0, item)
                    inserted = True
                    break
            if not inserted:
                if 'SECTIONS' in data and len(data['SECTIONS']) > 0:
                    data['SECTIONS'][0]['items'].insert(0, item)
        added += 1

    if added:
        DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
        print(f"Successfully added {added} automated items with dynamic deep links.")

if __name__ == '__main__':
    main()
