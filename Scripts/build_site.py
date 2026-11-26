#!/usr/bin/env python3
import html as html_lib
import json
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / 'data' if (ROOT / 'data').exists() else ROOT / 'Data'
TPL_DIR = ROOT / 'templates' if (ROOT / 'templates').exists() else ROOT / 'Templates'
DATA_FILE = DATA_DIR / 'portal_data.json'
INDEX_TPL = TPL_DIR / 'index_template.html'
POST_TPL = TPL_DIR / 'post_template.html'
POSTS_DIR = ROOT / 'posts'
POSTS_DIR.mkdir(parents=True, exist_ok=True)

SITE_BASE_URL = 'https://latestjobalert.pages.dev'
IST_TZ = timezone(timedelta(hours=5, minutes=30))
NOW_IST = datetime.now(IST_TZ)
TODAY_STR = NOW_IST.strftime('%Y-%m-%d')
UPDATED_LABEL_IST = NOW_IST.strftime('%d %b %Y, %I:%M %p IST')

DEFAULT_SYLLABUS = {
    'syl-1': {
        'pattern': 'CHSL Tier-I: 100 Q, 200 Marks, 60 Min (-0.50 Negative) | JE Paper-I: 200 Q, 200 Marks, 120 Min (-0.25 Negative).',
        'rows': [
            ('English Language', '25 Q / 50 Marks', 'Spot the Error, Fill in the Blanks, Synonyms/Antonyms, Idioms, Cloze Test, Active/Passive'),
            ('General Intelligence & Reasoning', '25 Q / 50 Marks (JE: 50 Q)', 'Analogy, Series, Coding-Decoding, Venn Diagrams, Syllogism, Embedded Figures'),
            ('Quantitative Aptitude', '25 Q / 50 Marks', 'Percentage, Ratio, Profit & Loss, SI/CI, Time & Work, Mensuration, Geometry, Trigonometry, DI'),
            ('General Awareness & Science', '25 Q / 50 Marks (JE: 50 Q)', 'History, Polity, Geography, Economy, General Science, Current Affairs & Static GK'),
            ('SSC JE Engineering (Civil/Elec/Mech)', '100 Q / 100 Marks', 'Building Materials, Surveying, Soil Mechanics, Hydraulics, Electrical Machines, Thermodynamics, SOM')
        ]
    },
    'syl-2': {
        'pattern': 'CBT-1: 100 Q (100 Marks, 90 Min) | CBT-2: 120 Q (120 Marks, 90 Min) | Negative: 1/3rd | Plus CBAT Psycho Test for Station Master.',
        'rows': [
            ('Mathematics', 'CBT-1: 30 Q | CBT-2: 35 Q', 'Number System, LCM/HCF, Ratio, Percentage, Mensuration, Time & Distance, Profit & Loss, Algebra, Geometry'),
            ('General Intelligence & Reasoning', 'CBT-1: 30 Q | CBT-2: 35 Q', 'Analogies, Series, Coding-Decoding, Mathematical Operations, Syllogism, Data Sufficiency, Statement-Conclusion'),
            ('General Awareness', 'CBT-1: 40 Q | CBT-2: 50 Q', 'Current Affairs, Games & Sports, General Science (10th CBSE), Indian Polity, Railways & Economy')
        ]
    },
    'syl-3': {
        'pattern': 'UP TGT: 125 MCQs, 500 Marks, 2 Hours, No Negative Marking | PRT: 150 Q, 150 Marks, 2.5 Hours.',
        'rows': [
            ('TGT Concerned Subject (Hindi/Maths/Sci/SST/Eng)', '125 Q / 500 Marks', 'Graduation-level subject knowledge in the opted teaching subject'),
            ('PRT Language (Hindi, English, Sanskrit)', '40 Marks', 'व्याकरण, अपठित गद्यांश, Grammar, Comprehension & Vocabulary'),
            ('PRT Science, Maths & Environment', '40 Marks', 'Number System, Percentage, Profit-Loss, Daily Science, Indian Geography & Constitution'),
            ('PRT Teaching Methodology & Child Psychology', '20 Marks', 'शिक्षण कौशल, बाल मनोविज्ञान, समावेशी शिक्षा, NEP 2020 & Learning Theories'),
            ('PRT General Knowledge & Current Affairs', '30 Marks', 'UP Special GK, National/International Current Affairs, Art & Culture')
        ]
    },
    'syl-4': {
        'pattern': '150 Questions, 150 Marks, 2 Hours 30 Minutes, No Negative Marking. Part I (30 Marks) is Qualifying (min 30%).',
        'rows': [
            ('Part I: Language (Qualifying)', '30 Q / 30 Marks', 'English (8 Q) + Hindi / Urdu / Bangla (22 Q) — Basic Grammar & Comprehension'),
            ('Part II: General Studies (GS)', '40 Q / 40 Marks (1–5: 120 Q)', 'Elementary Maths, Reasoning, GA, Science, Social Science, National Movement & Bihar GK'),
            ('Part III: Concerned Subject (6–8, 9–10, 11–12)', '80 Q / 80 Marks', 'SCERT / NCERT curriculum based Maths & Science, Social Science, Hindi, English, Computer Science')
        ]
    },
    'syl-5': {
        'pattern': 'Written CBT: 100 Q, 100 Marks, 2 Hours (No Negative) + Physical Efficiency Test (PET): 100 Marks.',
        'rows': [
            ('General Knowledge & Reasoning', '40 Marks', 'MP State GK, History, Geography, Polity, Logical Reasoning, Analogy, Coding-Decoding'),
            ('Intellectual Ability & Mental Aptitude', '30 Marks', 'Data Interpretation, Syllogism, Venn Diagrams, Number Series, Decision Making'),
            ('Science & Simple Arithmetic', '30 Marks', 'Physics, Chemistry, Biology (10th level), Percentage, Ratio, Average, Time & Work'),
            ('Physical Efficiency Test (PET)', '100 Marks', '800m Run (40 Marks), Long Jump (30 Marks), Shot Put (30 Marks)')
        ]
    }
}

def slugify(text, item_id):
    s = re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-')
    s = re.sub(r'-+', '-', s)[:60].strip('-')
    return f"{s}-{item_id}"

def format_post_time_ist(it):
    dt = None
    if it.get('addedAt'):
        try:
            dt = datetime.fromisoformat(it['addedAt'].replace('Z', '+00:00'))
        except Exception:
            dt = None
    if dt is None and it.get('id'):
        m = re.match(r'^auto-(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})', it['id'])
        if m:
            dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)), tzinfo=timezone.utc)
    if dt is None:
        return UPDATED_LABEL_IST
    return dt.astimezone(IST_TZ).strftime('%d %b %Y, %I:%M %p IST')

def build_article_block(it, cat_title):
    custom_html = (it.get('detailedArticle') or '').strip()
    if custom_html:
        return f'''<div class="rounded-xl border border-slate-200 p-5 bg-white space-y-3 prose max-w-none text-sm text-slate-700 leading-relaxed">
          <h2 class="text-base font-extrabold text-slate-900 border-b pb-2">Complete Details &amp; Candidate Guide</h2>
          {custom_html}
        </div>'''

    title_esc = html_lib.escape(it['title'])
    cat_esc = html_lib.escape(cat_title)
    short_esc = html_lib.escape(it.get('shortInfo') or it['title'])
    dates = it.get('dates') or {}
    last_d = html_lib.escape(dates.get('lastDate', 'Check Official Portal'))
    return f'''<div class="rounded-xl border border-slate-200 p-5 bg-white space-y-3 text-xs sm:text-sm text-slate-700 leading-relaxed">
      <h2 class="text-base font-extrabold text-slate-900 border-b pb-2">Complete Overview &amp; Candidate Guide — {title_esc}</h2>
      <p>{short_esc} Aspirants following the <strong>{cat_esc}</strong> schedule should review all official instructions carefully before taking the next step.</p>
      <h3 class="font-bold text-slate-900 pt-1">Key Instructions &amp; Document Checklist</h3>
      <ul class="list-disc list-inside space-y-1">
        <li>Verify your name, father's name, and date of birth against your Class 10th marksheet before submitting or downloading.</li>
        <li>Keep scanned passport photo (20KB–50KB), signature (10KB–20KB), and ID/category certificates ready in PDF format.</li>
        <li>Always check the official portal before the deadline (<strong>{last_d}</strong>) to avoid last-minute server traffic.</li>
      </ul>
      <h3 class="font-bold text-slate-900 pt-1">Frequently Asked Questions (FAQs)</h3>
      <p><strong>Q1. Where is the official link for {title_esc}?</strong><br/>You can access the direct official action link and department homepage in the Important Official Links table below.</p>
      <p><strong>Q2. What is the deadline or exam window?</strong><br/>The active window listed in the notification is <strong>{last_d}</strong>. Always confirm updates on the official website.</p>
    </div>'''

def build_syllabus_block(it):
    syl_rows = []
    pattern = it.get('examPattern', '')
    if it.get('syllabusDetails'):
        for r in it['syllabusDetails']:
            syl_rows.append((r.get('subject', ''), r.get('weight', ''), r.get('topics', '')))
    elif it.get('id') in DEFAULT_SYLLABUS:
        pattern = DEFAULT_SYLLABUS[it['id']]['pattern']
        syl_rows = DEFAULT_SYLLABUS[it['id']]['rows']
    if not syl_rows:
        return ''

    trs = '\n'.join(
        f'<tr class="hover:bg-slate-50"><td class="px-3.5 py-2.5 font-bold text-slate-900">{html_lib.escape(s)}</td>'
        f'<td class="px-3.5 py-2.5 font-semibold text-indigo-700 whitespace-nowrap">{html_lib.escape(w)}</td>'
        f'<td class="px-3.5 py-2.5 text-slate-600">{html_lib.escape(t)}</td></tr>'
        for s, w, t in syl_rows
    )
    pat_html = f'<div class="px-4 py-2.5 bg-indigo-50 text-xs font-semibold text-indigo-900 border-b border-indigo-200">{html_lib.escape(pattern)}</div>' if pattern else ''
    return f'''<div class="rounded-xl border border-indigo-200 overflow-hidden">
      <div class="bg-indigo-700 text-white px-4 py-2.5 text-xs font-bold uppercase tracking-wide">Exam Pattern &amp; Subject-Wise Syllabus</div>
      {pat_html}
      <div class="overflow-x-auto">
        <table class="w-full text-left text-xs sm:text-sm">
          <thead class="bg-slate-100 text-slate-700 text-xs uppercase">
            <tr><th class="px-3.5 py-2.5">Subject / Paper</th><th class="px-3.5 py-2.5">Marks / Qs</th><th class="px-3.5 py-2.5">Detailed Topics</th></tr>
          </thead>
          <tbody class="divide-y divide-slate-200">{trs}</tbody>
        </table>
      </div>
    </div>'''

def build_link_rows(it, sec_id):
    official_url = it.get('officialUrl') or 'https://india.gov.in/'
    p_url = it.get('primaryUrl') or official_url
    s_url = it.get('secondaryUrl') or official_url
    domain = official_url.replace('https://', '').replace('http://', '').strip('/')

    r1_label, r1_btn, r2_label, r2_btn = 'Apply Online', 'Apply Now', 'Download Official Notification', 'Click Here'
    if sec_id == 'admit':
        r1_label, r1_btn, r2_label = 'Download Admit Card / Exam City Slip', 'Download Admit Card', 'Exam Date & Instructions Notice'
    elif sec_id == 'result':
        r1_label, r1_btn, r2_label = 'Download Result / Score Card', 'Check Result', 'Cut-Off / Merit List PDF'
    elif sec_id == 'answer':
        r1_label, r1_btn, r2_label, r2_btn = 'Download Answer Key / Response Sheet', 'Download Answer Key', 'Raise Objection / Challenge Key', 'Objection Link'
    elif sec_id == 'correction':
        r1_label, r1_btn, r2_label, r2_btn = 'Form Correction / Edit / Finalize Link', 'Edit / Correct Form', 'Correction Window Notice', 'Click Here'
    elif sec_id == 'syllabus':
        r1_label, r1_btn, r2_label = 'Download Syllabus & Exam Pattern PDF', 'Download Syllabus', 'Official Exam Portal'
    elif sec_id == 'verification':
        r1_label, r1_btn, r2_label = 'Online Registration / Verification Portal', 'Open Portal', 'Check Application Status / Guidelines'

    return (
        f'<div class="flex items-center justify-between gap-2 px-4 py-3">'
        f'<span class="font-semibold text-xs sm:text-sm">{html_lib.escape(r1_label)}</span>'
        f'<a href="{html_lib.escape(p_url)}" target="_blank" rel="noopener noreferrer" class="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-bold text-xs shrink-0 transition">{html_lib.escape(r1_btn)} ↗</a>'
        f'</div>'
        f'<div class="flex items-center justify-between gap-2 px-4 py-3">'
        f'<span class="font-semibold text-xs sm:text-sm">{html_lib.escape(r2_label)}</span>'
        f'<a href="{html_lib.escape(s_url)}" target="_blank" rel="noopener noreferrer" class="px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-700 text-white font-bold text-xs shrink-0 transition">{html_lib.escape(r2_btn)} ↗</a>'
        f'</div>'
        f'<div class="flex items-center justify-between gap-2 px-4 py-3">'
        f'<span class="font-semibold text-xs sm:text-sm">Official Website</span>'
        f'<a href="{html_lib.escape(official_url)}" target="_blank" rel="noopener noreferrer" class="text-red-700 font-bold text-xs sm:text-sm hover:underline">{html_lib.escape(domain)}</a>'
        f'</div>'
    )

def main():
    data = json.loads(DATA_FILE.read_text(encoding='utf-8'))
    all_posts = []
    seen = set()

    def reg(it, cat_title, sec_id):
        if it.get('id') == 'hl-8':
            return
        slug = slugify(it['title'], it['id'])
        url = f"posts/{slug}.html"
        if it['id'] not in seen:
            seen.add(it['id'])
            all_posts.append((it, cat_title, sec_id, slug, url))

    for it in data.get('LAST_DATE_ITEMS', []):
        reg(it, 'Last Date Alert', 'lastDate')
    for it in data.get('CORRECTION_ITEMS', []):
        reg(it, 'Correction Date / Edit Form', 'correction')
    for it in data.get('HIGHLIGHTS', []):
        reg(it, 'Trending Form', 'jobs')
    for sec in data.get('SECTIONS', []):
        for it in sec.get('items', []):
            reg(it, sec['title'], sec['id'])

    post_url_map = {it['id']: url for it, _, _, _, url in all_posts}

    idx_html = INDEX_TPL.read_text(encoding='utf-8')
    idx_html = idx_html.replace('{{PORTAL_DATA_JSON}}', json.dumps(data, ensure_ascii=False))
    idx_html = idx_html.replace('{{POST_URL_MAP_JSON}}', json.dumps(post_url_map, ensure_ascii=False))
    idx_html = idx_html.replace('{{UPDATED_LABEL}}', UPDATED_LABEL_IST)
    (ROOT / 'index.html').write_text(idx_html, encoding='utf-8')

    post_tpl_str = POST_TPL.read_text(encoding='utf-8')
    for it, cat_title, sec_id, slug, url in all_posts:
        dates = it.get('dates') or {}
        related = [x for x in all_posts if x[0]['id'] != it['id'] and x[2] == sec_id][:6]
        rel_html = '\n'.join(
            f'<li class="px-4 py-3 hover:bg-slate-50"><a href="{x[3]}.html" class="text-xs sm:text-sm font-medium text-slate-800 hover:text-red-700 flex items-center justify-between"><span>• {html_lib.escape(x[0]["title"])}</span><span>›</span></a></li>'
            for x in related
        ) or '<li class="px-4 py-3 text-xs text-slate-500">More updates coming soon.</li>'

        json_ld = json.dumps({
            '@context': 'https://schema.org',
            '@type': 'NewsArticle',
            'headline': it['title'],
            'datePublished': TODAY_STR,
            'dateModified': TODAY_STR,
            'author': {'@type': 'Organization', 'name': 'Latest Job Alert'}
        })

        p_html = (
            post_tpl_str
            .replace('{{TITLE}}', html_lib.escape(it['title']))
            .replace('{{META_DESC}}', html_lib.escape((it.get('shortInfo') or it['title'])[:155]))
            .replace('{{CATEGORY}}', html_lib.escape(cat_title))
            .replace('{{UPDATED_DATE}}', TODAY_STR)
            .replace('{{POST_TIME_IST}}', format_post_time_ist(it))
            .replace('{{DETAILED_ARTICLE_BLOCK}}', build_article_block(it, cat_title))
            .replace('{{SHORT_INFO}}', html_lib.escape(it.get('shortInfo') or it['title']))
            .replace('{{DATE_START}}', html_lib.escape(dates.get('start', 'Check Portal')))
            .replace('{{DATE_LAST}}', html_lib.escape(dates.get('lastDate', 'Check Portal')))
            .replace('{{DATE_EXAM}}', html_lib.escape(dates.get('examDate', 'Notified Soon')))
            .replace('{{FEE}}', html_lib.escape(it.get('fee') or 'As per Official Notice'))
            .replace('{{AGE}}', html_lib.escape(it.get('age') or 'As per Govt Rules'))
            .replace('{{VACANCIES}}', html_lib.escape(it.get('vacancies') or 'See Notification'))
            .replace('{{SYLLABUS_BLOCK}}', build_syllabus_block(it))
            .replace('{{OFFICIAL_LINK_ROWS}}', build_link_rows(it, sec_id))
            .replace('{{RELATED_ITEMS_HTML}}', rel_html)
            .replace('{{JSON_LD}}', json_ld)
        )
        (POSTS_DIR / f"{slug}.html").write_text(p_html, encoding='utf-8')

    legal = {
        'about.html': ('About Us — Latest Job Alert', 'Latest Job Alert is an independent Indian government job, admit card, result, and exam notification portal with direct official .gov.in / .nic.in links and GreenPix Labs tools.'),
        'contact.html': ('Contact Us — Latest Job Alert', 'Reach out via our official YouTube channel (@officiallatestjobalert) or community channels.'),
        'privacy.html': ('Privacy Policy — Latest Job Alert', 'Bookmarks are stored locally in your browser. Advertising partners such as Google AdSense may use cookies to serve relevant ads.'),
        'disclaimer.html': ('Disclaimer — Latest Job Alert', 'Latest Job Alert is not affiliated with any government body. Always verify details on the official government website before applying.')
    }
    # Do NOT overwrite custom/full legal pages if they already exist in ROOT
    for fname, (ptitle, pbody) in legal.items():
        target_file = ROOT / fname
        if not target_file.exists():
            target_file.write_text(
                f'<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{ptitle}</title><script src="https://cdn.tailwindcss.com/3.4.17"></script></head><body class="bg-slate-50 text-slate-900 p-6 font-sans"><div class="max-w-3xl mx-auto bg-white rounded-2xl border p-6 shadow-sm space-y-3"><a href="index.html" class="text-xs font-bold text-red-700">← Back to Home</a><h1 class="text-2xl font-extrabold">{ptitle}</h1><p class="text-sm text-slate-700 leading-relaxed">{pbody}</p></div></body></html>',
                encoding='utf-8'
            )

    urls = ['index.html', 'about.html', 'contact.html', 'privacy.html', 'disclaimer.html'] + [u for _, _, _, _, u in all_posts]
    sitemap_entries = '\n'.join(f'  <url><loc>{SITE_BASE_URL}/{u}</loc><lastmod>{TODAY_STR}</lastmod></url>' for u in urls)
    (ROOT / 'sitemap.xml').write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n{sitemap_entries}\n</urlset>\n', encoding='utf-8')
    (ROOT / 'robots.txt').write_text(f'User-agent: *\nAllow: /\nSitemap: {SITE_BASE_URL}/sitemap.xml\n', encoding='utf-8')
    print(f'Built index.html + {len(all_posts)} SEO post pages + sitemap.xml!')

if __name__ == '__main__':
    main()
    
