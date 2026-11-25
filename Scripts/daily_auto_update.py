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

OFFICIAL_PORTALS = [
    (['ssc', 'chsl', 'cgl', 'mts', 'ssc gd', 'ssc je', 'cpo'], 'https://ssc.gov.in/', 'https://ssc.gov.in/login'),
    (['upsc', 'nda', 'cds', 'ias', 'cse', 'cisf'], 'https://www.upsc.gov.in/', 'https://upsconline.nic.in/'),
    (['rrb', 'railway', 'ntpc', 'alp', 'group d', 'paramedical', 'station master'], 'https://indianrailways.gov.in/', 'https://www.rrbapply.gov.in/'),
    (['ibps'], 'https://www.ibps.in/', 'https://www.ibps.in/'),
    (['sbi'], 'https://sbi.co.in/web/careers', 'https://sbi.co.in/web/careers'),
    (['bpsc'], 'https://bpsc.bihar.gov.in/', 'https://onlinebpsc.bihar.gov.in/'),
    (['bssc'], 'https://bssc.bihar.gov.in/', 'https://bssc.bihar.gov.in/'),
    (['csbc', 'bihar police'], 'https://csbc.bihar.gov.in/', 'https://csbc.bihar.gov.in/'),
    (['bseb', 'bihar board'], 'https://biharboardonline.bihar.gov.in/', 'https://biharboardonline.bihar.gov.in/'),
    (['pms', 'post matric'], 'https://pmsonline.bihar.gov.in/', 'https://scstpmsonline.bihar.gov.in/'),
    (['upsssc'], 'https://upsssc.gov.in/', 'https://upsssc.gov.in/'),
    (['uppsc'], 'https://uppsc.up.nic.in/', 'https://uppsc.up.nic.in/CandidatePages/Notifications.aspx'),
    (['upessc'], 'https://upessc.up.gov.in/', 'https://upessc.up.gov.in/'),
    (['up police', 'upprpb'], 'https://uppbpb.gov.in/', 'https://uppbpb.gov.in/'),
    (['up scholarship'], 'https://scholarship.up.gov.in/', 'https://scholarship.up.gov.in/'),
    (['dsssb'], 'https://dsssb.delhi.gov.in/', 'https://dsssb.delhi.gov.in/'),
    (['jee main'], 'https://jeemain.nta.nic.in/', 'https://jeemain.nta.nic.in/online-application-form-for-jee-main-2027-session-1/'),
    (['neet'], 'https://neet.nta.nic.in/', 'https://neet.nta.nic.in/'),
    (['ugc net'], 'https://ugcnet.nta.ac.in/', 'https://ugcnet.nta.ac.in/'),
    (['nta', 'cuet', 'cmat', 'nift', 'aissee'], 'https://nta.ac.in/', 'https://nta.ac.in/NoticeBoardArchive'),
    (['ctet'], 'https://ctet.nic.in/', 'https://ctet.nic.in/'),
    (['nielit', 'ccc'], 'https://student.nielit.gov.in/', 'https://student.nielit.gov.in/'),
    (['iocl'], 'https://iocl.com/', 'https://iocl.com/'),
]

def resolve_official_url(title, target):
    t = title.lower()
    for keywords, home_url, deep_url in OFFICIAL_PORTALS:
        if any(k in t for k in keywords):
            if 'ssc' in keywords and target == 'result':
                return home_url, 'https://ssc.gov.in/home/candidate-result'
            return home_url, deep_url
    return 'https://www.ncs.gov.in/', 'https://www.india.gov.in/'

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
        '- "officialUrl": ONLY official .gov.in or .nic.in or department URL (NEVER a blog/news site)\n'
        '- "primaryUrl": exact official apply/admit-card/result/answer-key/PDF page URL'
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
        'UPSC OR IBPS OR SBI OR NTA Recruitment Notification 2026 India'
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
            pub_date = (item.findtext('pubDate') or 'Today')[:16]
            if not raw_title:
                continue
            target, badge = classify_target(raw_title)
            official_url, primary_url = resolve_official_url(raw_title, target)
            updates.append({
                'target': target,
                'title': raw_title,
                'badge': badge,
                'shortInfo': f"{raw_title}. Published {pub_date}. Visit the official government portal below for direct apply, admit card, result, or notice links.",
                'startDate': pub_date,
                'lastDate': 'Check Official Notice',
                'examDate': 'As per Schedule',
                'fee': 'As per Official Notice',
                'age': 'As per Govt Rules',
                'vacancies': 'See Notification',
                'officialUrl': official_url,
                'primaryUrl': primary_url,
                'secondaryUrl': official_url
            })
    print(f'Fetched {len(updates)} items via RSS with exact official portals.')
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
        target = u.get('target', 'jobs')
        fallback_home, fallback_deep = resolve_official_url(title, target)
        official_url = u.get('officialUrl') or fallback_home
        primary_url = u.get('primaryUrl') or fallback_deep
        secondary_url = u.get('secondaryUrl') or official_url
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
            'officialUrl': official_url,
            'primaryUrl': primary_url,
            'secondaryUrl': secondary_url
        }
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
