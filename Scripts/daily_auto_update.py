#!/usr/bin/env python3
import json
import os
import re
import time
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / 'data' / 'portal_data.json'
if not DATA_FILE.exists() and (ROOT / 'Data' / 'portal_data.json').exists():
    DATA_FILE = ROOT / 'Data' / 'portal_data.json'

MODELS = ['gemini-3.5-flash-lite', 'gemini-3.1-flash-lite', 'gemini-3.6-flash', 'gemini-3.8-flash']
OFFICIAL_DOMAINS = ('.gov.in', '.nic.in', '.ac.in', 'ibps.in', 'rrbapply.gov.in', 'cdn.digialm.com', 'iocl.com', 'sbi.co.in')
SKIP_KEYWORDS = (
    'previous year question', 'repeated question', 'most important question',
    'mock test', 'practice set', 'model paper', 'preparation tips', 'study plan',
    'salary structure', 'cut off expected', 'book list'
)

def clean_title(t):
    return re.sub(r'^(sarkari\s*jobs?|latest\s*news|breaking)\s*[:\-–]\s*', '', t, flags=re.IGNORECASE).strip()

def is_valid_portal_item(title):
    t = title.lower()
    if not title or any(bad in t for bad in SKIP_KEYWORDS):
        return False
    valid_signals = (
        'recruitment', 'vacancy', 'vacancies', 'online form', 'apply', 'notification',
        'admit card', 'hall ticket', 'city slip', 'exam city', 'exam date', 'schedule',
        'result', 'score card', 'merit list', 'answer key', 'objection', 'syllabus',
        'correction', 'edit window', 'extended', 'last date', 'apprentice', 'scholarship',
        'admission', 'counselling', 'interview', 'call letter'
    )
    return any(sig in t for sig in valid_signals)

def is_official_url(u):
    u_low = (u or '').lower()
    return u_low.startswith('https://') and any(d in u_low for d in OFFICIAL_DOMAINS)

def discover_official_links(title):
    found = []
    try:
        q = f"{title} official site:gov.in OR site:nic.in OR filetype:pdf"
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(q)}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = resp.read().decode('utf-8', errors='ignore')
        for enc in re.findall(r'uddg=([^&"]+)', body):
            decoded = urllib.parse.unquote(enc)
            if is_official_url(decoded) and decoded not in found:
                found.append(decoded)
            if len(found) >= 5:
                break
    except Exception:
        pass
    return found

def classify_target(title):
    t = title.lower()
    if 'correction' in t or 'edit window' in t:
        return 'correction', 'EDIT'
    if 'extended' in t or 'last date' in t or 'closing' in t:
        return 'lastDate', 'EXTENDED' if 'extended' in t else 'LAST DATE'
    if 'admit card' in t or 'hall ticket' in t or 'city slip' in t or 'call letter' in t:
        return 'admit', 'ADMIT CARD'
    if 'answer key' in t or 'objection' in t:
        return 'answer', 'KEY OUT'
    if 'result' in t or 'score card' in t or 'merit list' in t:
        return 'result', 'RESULT'
    if 'syllabus' in t or 'exam pattern' in t:
        return 'syllabus', 'SYLLABUS'
    if 'apprentice' in t or 'iti' in t or 'diploma' in t:
        return 'diploma', 'ITI/DIPLOMA'
    if 'scholarship' in t:
        return 'verification', 'SCHOLARSHIP'
    if 'admission' in t or 'jee' in t or 'neet' in t or 'cuet' in t:
        return 'admission', 'ADMISSION'
    return 'jobs', 'NEW'

def call_gemini(api_key, prompt):
    payload = json.dumps({"contents": [{"parts": [{"text": prompt}]}]}).encode('utf-8')
    for model in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
        for attempt in range(2):
            req = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=60) as resp:
                    res = json.loads(resp.read().decode('utf-8'))
                return res['candidates'][0]['content']['parts'][0]['text'], model
            except Exception as e:
                print(f'{model} attempt {attempt + 1} skipped ({e})')
                time.sleep(2)
    return '', ''

def gather_raw_signals():
    queries = [
        'SSC OR RRB OR BPSC OR UPSSSC Admit Card Result Answer Key 2026',
        'UPSC OR IBPS OR SBI OR NTA OR UPTET Recruitment Notification 2026 India'
    ]
    raw_list = []
    for q in queries:
        rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}&hl=en-IN&gl=IN&ceid=IN:en"
        req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=20) as resp:
            xml_data = resp.read()
        root = ET.fromstring(xml_data)
        for item in root.findall('./channel/item')[:6]:
            t = clean_title((item.findtext('title') or '').split(' - ')[0])
            d = (item.findtext('pubDate') or 'Today')[:16]
            if is_valid_portal_item(t):
                raw_list.append((t, d, discover_official_links(t)))
    return raw_list

def create_posts_with_gemini(api_key, raw_list):
    today = datetime.now(timezone.utc).strftime('%d %B %Y')
    lines = [f"- {t} ({d}) | URLs: {', '.join(links) if links else 'None'}" for t, d, links in raw_list]
    prompt = (
        f"Today is {today}. Headlines:\n" + "\n".join(lines) + "\n\n"
        "Select up to 4 genuine Indian Govt Job notifications, Admit Cards, Results, Answer Keys, Extended Notices, Syllabus, or Corrections. "
        "Exclude question papers, mock tests, or 'SARKARI JOBS:' prefix.\n"
        "Pick primaryUrl, secondaryUrl (.pdf if any), and officialUrl ONLY from the official URLs listed.\n"
        'Return ONLY valid JSON: {"updates": [{"target":"jobs|admit|result|answer|lastDate|correction|syllabus|admission|verification|diploma|outsourcing","isMajor":true,"title":"...","badge":"NEW","shortInfo":"...","startDate":"...","lastDate":"...","examDate":"...","fee":"...","age":"...","vacancies":"...","primaryUrl":"...","secondaryUrl":"...","officialUrl":"..."}]}'
    )
    text, model = call_gemini(api_key, prompt)
    if not text:
        return []
    print(f'Selected updates using {model}')
    m = re.search(r'\{[\s\S]*\}', text)
    updates = json.loads(m.group(0)).get('updates', []) if m else []

    # Generate separate 800-1000 word article per post (reliable, never breaks JSON!)
    for u in updates:
        art_prompt = (
            f"Write an 800-1000 word, 100% original, plagiarism-free, SEO-friendly guide in clean HTML (<p>, <h3>, <ul>, <li>) for Indian exam aspirants on:\n"
            f"Title: {u.get('title')}\nSummary: {u.get('shortInfo')}\nDates: {u.get('startDate')} to {u.get('lastDate')}, Exam: {u.get('examDate')}\n"
            "Include: 1) Detailed Overview, 2) Key Highlights, 3) Eligibility & Selection Process, 4) Step-by-Step How to Apply/Download, 5) Document Preparation Tips, and 6) 5 Helpful FAQs. Return ONLY HTML tags (no markdown fences)."
        )
        art_html, _ = call_gemini(api_key, art_prompt)
        art_html = re.sub(r'^```html|```$', '', art_html.strip(), flags=re.IGNORECASE).strip()
        u['detailedArticle'] = art_html
    return updates

def build_original_fallback(raw_list):
    updates = []
    for t, d, links in raw_list[:4]:
        target, badge = classify_target(t)
        pdf_link = next((l for l in links if '.pdf' in l.lower()), '')
        deep_link = next((l for l in links if '.pdf' not in l.lower()), '') or pdf_link or 'https://www.india.gov.in/'
        home_link = links[0] if links else 'https://www.india.gov.in/'
        updates.append({
            'target': target,
            'isMajor': any(k in t.lower() for k in ('ssc', 'rrb', 'upsc', 'bpsc', 'upsssc', 'ibps', 'extended')),
            'title': t,
            'badge': badge,
            'shortInfo': f"{t} update released on {d}. Candidates can check official dates, eligibility, and direct portal links below.",
            'startDate': d,
            'lastDate': 'Check Official Notice',
            'examDate': 'As per Official Schedule',
            'fee': 'As per Official Notice',
            'age': 'As per Govt Rules',
            'vacancies': 'See Official Notification',
            'primaryUrl': deep_link,
            'secondaryUrl': pdf_link or home_link,
            'officialUrl': home_link,
            'detailedArticle': ''
        })
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

    try:
        raw_list = gather_raw_signals()
    except Exception as e:
        print('Signal fetch warning:', e)
        return

    api_key = os.environ.get('GEMINI_API_KEY', '').strip()
    updates = create_posts_with_gemini(api_key, raw_list) if api_key else []
    if not updates:
        updates = build_original_fallback(raw_list)

    added = 0
    for idx, u in enumerate(updates):
        title = clean_title(u.get('title') or '')
        if not is_valid_portal_item(title) or title.lower() in existing_titles:
            continue
        existing_titles.add(title.lower())
        target = u.get('target', 'jobs')
        p_url = u.get('primaryUrl') if is_official_url(u.get('primaryUrl')) else 'https://www.india.gov.in/'
        s_url = u.get('secondaryUrl') if is_official_url(u.get('secondaryUrl')) else p_url
        o_url = u.get('officialUrl') if is_official_url(u.get('officialUrl')) else p_url
        item = {
            'id': f"auto-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}-{idx}",
            'title': title,
            'badge': u.get('badge', 'NEW'),
            'tag': u.get('badge', 'NEW'),
            'filter': ['all'],
            'shortInfo': u.get('shortInfo', title),
            'detailedArticle': u.get('detailedArticle', ''),
            'dates': {
                'start': u.get('startDate', 'Check Portal'),
                'lastDate': u.get('lastDate', 'Check Portal'),
                'examDate': u.get('examDate', 'Notified Soon')
            },
            'fee': u.get('fee', 'As per Official Notice'),
            'age': u.get('age', 'As per Govt Rules'),
            'vacancies': u.get('vacancies', 'See Notification'),
            'officialUrl': o_url,
            'primaryUrl': p_url,
            'secondaryUrl': s_url
        }

        if target == 'lastDate':
            data['LAST_DATE_ITEMS'].insert(0, item)
            for sec in data['SECTIONS']:
                if sec['id'] == 'jobs':
                    sec['items'].insert(0, item)
        elif target == 'correction':
            data['CORRECTION_ITEMS'].insert(0, item)
        else:
            for sec in data['SECTIONS']:
                if sec['id'] == target:
                    sec['items'].insert(0, item)
                    break

        if u.get('isMajor') and target in ('jobs', 'lastDate'):
            hl_item = dict(item)
            hl_item['subtitle'] = f"{item['badge']} • Apply / Check"
            hl_item['colorClass'] = 'from-red-600 to-rose-700'
            hl_item['tags'] = ['all']
            hl_list = [h for h in data.get('HIGHLIGHTS', []) if h.get('id') != 'hl-8']
            hl_list.insert(0, hl_item)
            hl_timer = [h for h in data.get('HIGHLIGHTS', []) if h.get('id') == 'hl-8']
            data['HIGHLIGHTS'] = hl_list[:7] + hl_timer

        added += 1

    if added:
        DATA_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'Added {added} new updates with full articles.')

if __name__ == '__main__':
    main()
    
